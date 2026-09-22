"""Load the item bank from CSV into app.questions (FR-OPS-01). Run as isobath_batch.

    python -m isobath.items            # every items/items-*.csv
    python -m isobath.items FILE ...

Columns (UTF-8, header row):
    id, code, item_set_version, kind, domain, facet, keyed, anchor, block_no, linking,
    status, quality_rule, text_ja, screening, note

Items are immutable once loaded, because answers refer to them. For an existing id only `status`
and `linking` may change; any other difference aborts the whole load. To reword an item, add it
under a new id and retire the old one. Rows are never deleted.

`screening` and `note` record the check in research-data-management.md §2 and are not loaded:
`normal`, or `caution` with the reason and approver in `note`. Excluded items are never added.
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import get_settings

log = logging.getLogger("isobath.items")

LOADED = ("id", "code", "item_set_version", "kind", "domain", "facet", "keyed", "anchor",
          "block_no", "linking", "status", "quality_rule", "text_ja")  # fmt: skip
MUTABLE = ("status", "linking")
BOOLS = {"": False, "true": True, "false": False}


def parse(row: dict) -> dict:
    """One CSV row -> column values. Empty cells are NULL; CHECK constraints do the rest."""
    code = row.get("code") or row.get("id")
    screening = row.get("screening", "")
    if screening not in ("normal", "caution"):
        raise ValueError(f"{code}: screening must be normal or caution, got {screening!r}")
    if screening == "caution" and not row.get("note"):
        raise ValueError(f"{code}: caution needs a note (reason and approver)")
    q = {c: (row.get(c) or "").strip() or None for c in LOADED}
    for c in ("id", "keyed", "block_no"):
        q[c] = int(q[c]) if q[c] is not None else None
    for c in ("anchor", "linking"):
        v = (q[c] or "").lower()
        if v not in BOOLS:
            raise ValueError(f"{code}: {c} must be true or false, got {q[c]!r}")
        q[c] = BOOLS[v]
    q["quality_rule"] = json.loads(q["quality_rule"]) if q["quality_rule"] else None
    return q


def read(paths: list[Path]) -> list[dict]:
    items = []
    files = [f for p in paths for f in (sorted(p.glob("items-*.csv")) if p.is_dir() else [p])]
    for p in files:
        with p.open(encoding="utf-8-sig", newline="") as f:
            items += [parse(r) for r in csv.DictReader(f)]
    return items


def load(conn: psycopg.Connection, items: list[dict]) -> dict:
    """Insert new items and update status/linking, in the caller's transaction."""
    existing = {
        r["id"]: r
        for r in conn.execute(
            f"select {', '.join(LOADED)} from app.questions where id = any(%s)",  # noqa: S608
            ([q["id"] for q in items],),
        )
    }
    changed = [
        f"{q['id']}.{c}"
        for q in items
        if q["id"] in existing
        for c in LOADED
        if c not in MUTABLE and existing[q["id"]][c] != q[c]
    ]
    if changed:
        raise ValueError(f"items are immutable; use a new id and retire the old one: {changed}")
    cols = ", ".join(LOADED)
    counts = {"inserted": 0, "updated": 0, "unchanged": 0}
    for q in items:
        old = existing.get(q["id"])
        if old is None:
            counts["inserted"] += 1
        elif all(old[c] == q[c] for c in MUTABLE):
            counts["unchanged"] += 1
            continue
        else:
            counts["updated"] += 1
        conn.execute(
            f"""insert into app.questions ({cols}) values ({", ".join(f"%({c})s" for c in LOADED)})
                on conflict (id) do update set status = excluded.status, linking = excluded.linking""",  # noqa: S608
            {**q, "quality_rule": Jsonb(q["quality_rule"]) if q["quality_rule"] else None},
        )
    return counts


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="isobath.items")
    parser.add_argument("csv", nargs="*", type=Path, default=[Path("items")])
    args = parser.parse_args(argv)
    s = get_settings()
    items = read(args.csv)
    with psycopg.connect(
        s.nightly_database_url or s.database_url, prepare_threshold=None, row_factory=dict_row
    ) as conn:
        counts = load(conn, items)  # commits on exit; any error rolls back the whole load
    log.info(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
