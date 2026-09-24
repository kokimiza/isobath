"""Nightly batch (requirements §4.1, design §5.13). Run by GitHub Actions at 01:00 JST.

    python -m isobath.nightly            # process the latest cutoff at or before now
    python -m isobath.nightly --at 2027-03-15T01:00+09:00

Only data completed before the cutoff is used, so a late, repeated or retried run yields the same
result. A cutoff that already succeeded is skipped (FR-BAT-06, FR-BAT-11).
"""

import hashlib
import json
import logging
import sys
from datetime import datetime

import numpy as np
import psycopg
from psycopg.rows import dict_row

from .cycle import current_cutoff, iso
from .inference import artifact
from .inference.project import InferenceConfig, place
from .inference.seas import at_position, sea_field
from .inference.training import training_placement

log = logging.getLogger("isobath.nightly")

GRID_BINS = 24
GRID_EXTENT = 3.0  # map coordinates are roughly standard normal


def cutoff_done(conn, cutoff, *, initialize_unpublished=False, spatial_upgrade=False):
    row = conn.execute(
        """select stage, map is not null as has_map, model_bundle is not null as has_model,
                  map->>'space' as space
           from app.batch_runs where cutoff_at = %s and status = 'succeeded'""",
        (cutoff,),
    ).fetchone()
    if row is None:
        return False
    if spatial_upgrade and row.get("space") != "latent3-v1":
        return False
    # A pre-bootstrap run only counted participants. Allow publishing its missing chart
    # once; never overwrite an already published chart, even when its density is empty.
    return not (
        initialize_unpublished
        and row["stage"] in ("COLLECTING", "UNCHARTED")
        and not row["has_map"]
        and not row["has_model"]
    )


def density_map(points: np.ndarray, k: int, bins: int = GRID_BINS) -> dict:
    """Aggregated 2-D histogram; cells with fewer than k people are suppressed (FR-CHT-04)."""
    edges = np.linspace(-GRID_EXTENT, GRID_EXTENT, bins + 1)
    counts = np.zeros((bins, bins), dtype=int)
    if len(points):
        clipped = np.clip(points, -GRID_EXTENT, GRID_EXTENT - 1e-9)
        counts, _, _ = np.histogram2d(clipped[:, 0], clipped[:, 1], bins=[edges, edges])
        counts = counts.astype(int)
    counts[counts < k] = 0
    result = {
        "bins": bins,
        "extent": [-GRID_EXTENT, GRID_EXTENT, -GRID_EXTENT, GRID_EXTENT],
        "k": k,
        "counts": counts.tolist(),
    }
    if points.shape[1] == 3:
        volume, _ = np.histogramdd(points, bins=[edges] * 3)
        volume[volume < k] = 0
        result.update(
            dimension=3,
            space="latent3-v1",
            volume={
                "bins": bins,
                "bounds": [[-GRID_EXTENT, GRID_EXTENT]] * 3,
                "counts": volume.astype(int).ravel().tolist(),
            },
        )
    return result


def _targets(conn, cutoff: datetime, previous: datetime | None, version: str) -> list:
    """Users with newly completed sessions, or whose last snapshot used another model version."""
    rows = conn.execute(
        """select distinct user_id from app.survey_sessions
           where status = 'completed' and completed_at < %(cutoff)s
             and (%(previous)s::timestamptz is null or completed_at >= %(previous)s
                  or not exists (select 1 from app.position_snapshots ps
                                 where ps.user_id = app.survey_sessions.user_id))
           union
           select user_id from (
             select distinct on (user_id) user_id, chart_version from app.position_snapshots
             order by user_id, cutoff_at desc
           ) latest
           where chart_version <> %(version)s""",
        {"cutoff": cutoff, "previous": previous, "version": version},
    ).fetchall()
    return [r["user_id"] for r in rows]


def _place_users(
    conn, model: artifact.Model, cutoff: datetime, users: list, private_directory=None
) -> int:
    if not users:
        return 0
    answers: dict = {}
    for r in conn.execute(
        """select distinct on (a.user_id, a.question_id) a.user_id, a.question_id, a.value
           from app.answers a
           join app.survey_sessions s on s.id = a.session_id
           where s.status = 'completed' and s.completed_at < %(cutoff)s
             and s.item_set_version = %(item_set_version)s
             and a.user_id = any(%(users)s)
           order by a.user_id, a.question_id, a.answered_at desc""",
        {"cutoff": cutoff, "users": users, "item_set_version": model.item_set_version},
    ):
        answers.setdefault(r["user_id"], {})[r["question_id"]] = r["value"]
    last_session = {
        r["user_id"]: r["id"]
        for r in conn.execute(
            """select distinct on (user_id) user_id, id from app.survey_sessions
               where status = 'completed' and completed_at < %(cutoff)s and user_id = any(%(users)s)
                 and item_set_version = %(item_set_version)s
               order by user_id, completed_at desc""",
            {"cutoff": cutoff, "users": users, "item_set_version": model.item_set_version},
        )
    }
    rows = []
    for uid, ans in answers.items():
        p = None
        if private_directory:
            key = conn.execute("select app.batch_research_key(%s) as key", (uid,)).fetchone()["key"]
            if key is not None:
                p = training_placement(private_directory, model, key, ans)
        seed = int.from_bytes(
            hashlib.sha256(f"{model.version}:{uid}:{cutoff.isoformat()}".encode()).digest()[:8],
            "big",
        )
        if p is None:
            p = place(
                model,
                ans,
                config=InferenceConfig(seed=seed, warmup=32, draws=32, chains=2)
                if model.stage == "PRIOR"
                else InferenceConfig(seed=seed),
                verify=model.meta.get("private_results_required", False),
            )
        uncertainty = p.credible_region
        if model.meta.get("schema_version") == 4:
            uncertainty = {
                **uncertainty,
                "coordinate_system": "latent3-v1",
                "sea_at_mean": at_position(model, p.map_xy),
            }
        rows.append(
            (
                uid,
                last_session[uid],
                cutoff,
                model.version,
                model.stage,
                p.latent.tolist(),
                p.latent_se.tolist(),
                p.map_xy.tolist(),
                p.confidence,
                None if p.memberships is None else json.dumps(p.memberships),
                p.near_boundary,
                json.dumps(uncertainty),
                json.dumps(p.unmatched),
                p.inference_mode,
                p.draws_x.tolist(),
            )
        )
    with conn.cursor() as cur:
        cur.executemany(
            """insert into app.position_snapshots
                 (user_id, session_id, cutoff_at, chart_version, stage, latent, latent_se, map_xy,
                  confidence, memberships, near_boundary, uncertainty, unmatched, inference_mode, draws_x)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s, %s)
               on conflict (user_id, cutoff_at) do update set
                 session_id = excluded.session_id, chart_version = excluded.chart_version,
                 stage = excluded.stage, latent = excluded.latent, latent_se = excluded.latent_se,
                 map_xy = excluded.map_xy, confidence = excluded.confidence,
                 memberships = excluded.memberships, near_boundary = excluded.near_boundary,
                 uncertainty = excluded.uncertainty, unmatched = excluded.unmatched,
                 inference_mode = excluded.inference_mode, draws_x = excluded.draws_x""",
            rows,
        )
    return len(rows)


def _research_points(conn, version, dimension=2) -> np.ndarray:
    """Latest positions of users whose current research consent is a grant."""
    rows = conn.execute(
        """select distinct on (ps.user_id) ps.map_xy
           from app.position_snapshots ps
           where ps.chart_version = %s and ps.user_id in (
             select user_id from (
               select distinct on (user_id) user_id, action, version from app.consent_events
               where document = 'research' and user_id is not null
               order by user_id, id desc
             ) r where action = 'grant' and version = '2'
           )
           order by ps.user_id, ps.cutoff_at desc""",
        (version,),
    ).fetchall()
    return np.array([r["map_xy"] for r in rows], dtype=float).reshape(-1, dimension)


def run(
    dsn: str,
    model: artifact.Model,
    now: datetime,
    k: int,
    *,
    private_directory=None,
    model_bundle=None,
    refit_attempt_at=None,
    initialize_unpublished=False,
) -> dict:
    cutoff = current_cutoff(now)
    # autocommit: each conn.transaction() below is a real transaction, so a failure record
    # survives the rollback of the work it describes
    with psycopg.connect(
        dsn, autocommit=True, prepare_threshold=None, row_factory=dict_row
    ) as conn:
        if cutoff_done(
            conn,
            cutoff,
            initialize_unpublished=initialize_unpublished and model.can_place,
            spatial_upgrade=initialize_unpublished and model.meta.get("schema_version") == 4,
        ):
            return {"cutoff_at": iso(cutoff), "status": "skipped"}
        previous = conn.execute(
            """select max(cutoff_at) as c from app.batch_runs
               where status = 'succeeded' and cutoff_at < %s""",
            (cutoff,),
        ).fetchone()["c"]
        try:
            with conn.transaction():
                placed, chart = 0, None
                if model.can_place:
                    if model.meta.get("private_results_required") and (
                        private_directory is None or not (private_directory / "people").is_dir()
                    ):
                        raise ValueError(
                            "private joint posterior handoff is required for this model"
                        )
                    placed = _place_users(
                        conn,
                        model,
                        cutoff,
                        _targets(conn, cutoff, previous, model.version),
                        private_directory,
                    )
                    chart = density_map(
                        _research_points(conn, model.version, model.arrays["P"].shape[0]), k
                    )
                    if model.meta.get("schema_version") == 4:
                        chart["seas"] = sea_field(model)
                participants = conn.execute(
                    """select count(distinct user_id) as n from app.survey_sessions
                       where kind = 'initial' and status = 'completed' and completed_at < %s""",
                    (cutoff,),
                ).fetchone()["n"]
                conn.execute(
                    """insert into app.batch_runs
                         (cutoff_at, status, chart_version, stage, participants, placed, map,
                          finished_at, model_bundle, refit_attempt_at)
                       values (%s, 'succeeded', %s, %s, %s, %s, %s::jsonb, now(), %s, %s)
                       on conflict (cutoff_at) do update set
                         status = 'succeeded', chart_version = excluded.chart_version,
                         stage = excluded.stage, participants = excluded.participants,
                         placed = excluded.placed, map = excluded.map,
                         finished_at = now(), error = null,
                         model_bundle = excluded.model_bundle,
                         refit_attempt_at = excluded.refit_attempt_at""",
                    (
                        cutoff,
                        model.version,
                        model.stage,
                        participants,
                        placed,
                        None if chart is None else json.dumps(chart),
                        model_bundle,
                        refit_attempt_at,
                    ),
                )
        except Exception as e:
            with conn.transaction():
                conn.execute(
                    """insert into app.batch_runs (cutoff_at, status, chart_version, stage, error,
                                                   finished_at)
                       values (%s, 'failed', %s, %s, %s, now())
                       on conflict (cutoff_at) do update set
                         status = 'failed', error = excluded.error, finished_at = now()
                       where app.batch_runs.status <> 'succeeded'""",
                    (cutoff, model.version, model.stage, type(e).__name__),
                )
            raise
    return {
        "cutoff_at": iso(cutoff),
        "status": "succeeded",
        "chart_version": model.version,
        "stage": model.stage,
        "participants": participants,
        "placed": placed,
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from .scheduled import main as scheduled_main  # noqa: PLC0415 - legacy CLI alias

    return scheduled_main(argv)


if __name__ == "__main__":
    sys.exit(main())
