"""Bounded nightly refit child; uses only privileges already held by isobath_batch."""

import argparse
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from isobath.config import ITEM_SET_VERSION, get_settings

from .bootstrap import design
from .data import from_records
from .run import fit, git_commit
from .sampler import SamplerConfig


def extract_batch(conn, version, cutoff):
    conn.execute("set transaction isolation level repeatable read read only")
    questions = conn.execute(
        "select id, item_set_version, kind, domain, keyed, anchor from app.questions "
        "where item_set_version = %s",
        (version,),
    ).fetchall()
    anchors = design(questions, version)
    # Deletion cascades remove sessions/answers; the bridge filters current v2 consent.
    responses = conn.execute(
        """select app.batch_research_key(a.user_id) as pseudo_id,
                  a.session_id, a.question_id, a.value, a.answered_at, s.item_set_version
           from app.answers a join app.survey_sessions s on s.id = a.session_id
           where s.status = 'completed' and s.completed_at < %s
             and s.item_set_version = %s""",
        (cutoff, version),
    ).fetchall()
    responses = [r for r in responses if r["pseudo_id"] is not None]
    participants = {r["pseudo_id"] for r in responses}
    return from_records(
        responses,
        questions,
        participants,
        [],
        version,
        {q for q, yes in zip(anchors.question_ids, anchors.anchors, strict=True) if yes},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", type=datetime.fromisoformat, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--previous")
    args = parser.parse_args()
    if args.cutoff.tzinfo is None:
        parser.error("cutoff must include a time zone")
    settings = get_settings()
    with psycopg.connect(
        settings.nightly_database_url or settings.database_url,
        row_factory=dict_row,
        prepare_threshold=None,
    ) as conn:
        data = extract_batch(conn, ITEM_SET_VERSION, args.cutoff)
    fit(
        data,
        SamplerConfig(),
        args.version,
        args.root,
        args.private_root,
        commit=git_commit(),
        previous=args.previous,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
