"""Latest successful nightly batch, as seen by the API (cached: it changes once a day)."""

import time
from datetime import UTC, datetime

from .cycle import STALE_AFTER, current_cutoff, iso, next_cutoff
from .db import service_tx
from .inference.artifact import STAGES, Model

TTL = 60.0
_cache: dict = {"at": -TTL, "run": None}


def latest_run() -> dict | None:
    now = time.monotonic()
    if now - _cache["at"] >= TTL:
        with service_tx() as conn:
            _cache["run"] = conn.execute(
                """select cutoff_at, chart_version, stage, participants, map is not null as has_map
                   from app.batch_runs where status = 'succeeded'
                   order by cutoff_at desc limit 1"""
            ).fetchone()
        _cache["at"] = now
    return _cache["run"]


def at_least(stage: str, minimum: str) -> bool:
    return STAGES.index(stage) >= STAGES.index(minimum)


def chart_state(model: Model) -> dict:
    """Version/stage/counts shown to users: those of the last nightly batch, not of the repo.
    Before the first batch, fall back to the deployed model's metadata."""
    run = latest_run()
    now = datetime.now(UTC)
    return {
        "version": run["chart_version"] if run else model.version,
        "stage": run["stage"] if run else model.stage,
        "participants": run["participants"] if run else 0,
        "updated_at": run["cutoff_at"] if run else None,
        "next_update_at": next_cutoff(now),
        "stale": bool(run) and now - run["cutoff_at"] > STALE_AFTER,
        "current_window_done": bool(run) and run["cutoff_at"] >= current_cutoff(now),
        "has_map": bool(run and run["has_map"]),
    }


def timestamps(state: dict) -> dict:
    return {
        "updated_at": iso(state["updated_at"]),
        "next_update_at": iso(state["next_update_at"]),
    }
