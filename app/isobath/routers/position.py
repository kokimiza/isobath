from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from psycopg import sql

from ..cycle import current_cutoff, iso
from ..db import user_tx
from ..errors import api_error
from ..ratelimit import limit
from ..runs import at_least, chart_state, timestamps

router = APIRouter(prefix="/v1/me")

SNAPSHOT_COLS = sql.SQL(
    "id, chart_version, stage, map_xy, latent_se, confidence, memberships, near_boundary, cutoff_at"
)
LATEST_SNAPSHOT = sql.SQL("select {} from app.position_snapshots order by id desc limit 1").format(
    SNAPSHOT_COLS
)
SNAPSHOT_PAGE = sql.SQL(
    """select {} from app.position_snapshots
       where %(cursor)s::bigint is null or id < %(cursor)s
       order by id desc limit %(n)s"""
).format(SNAPSHOT_COLS)


def _shape(row: dict, with_regions: bool) -> dict:
    out = {
        "chart": {"version": row["chart_version"], "stage": row["stage"]},
        "position": row["map_xy"],
        "se": row["latent_se"],
        "confidence": row["confidence"],
        "at": iso(row["cutoff_at"]),  # the nightly update that produced it
    }
    if with_regions and row["memberships"] is not None:
        out["regions"] = row["memberships"]
        out["near_boundary"] = row["near_boundary"]
    return out


@router.get("/position")
def position(request: Request, claims: dict = Depends(limit("position"))):
    state = chart_state(request.app.state.model)
    with user_tx(claims) as conn:
        profile = conn.execute("select observer_no from app.profiles").fetchone()
        if profile is None:
            raise api_error(404, "profile_not_found")
        sessions = conn.execute(
            "select kind, status, completed_at from app.survey_sessions"
        ).fetchall()
        initial_completed = any(
            s["kind"] == "initial" and s["status"] == "completed" for s in sessions
        )
        window_start = current_cutoff(datetime.now(UTC))
        base = {
            "chart": {"version": state["version"], "stage": state["stage"]},
            "observer_no": profile["observer_no"],
            "participants": state["participants"],
            **timestamps(state),
            "survey": {
                "initial_completed": initial_completed,
                "open_session": any(s["status"] == "open" for s in sessions),
                "open_kind": next((s["kind"] for s in sessions if s["status"] == "open"), None),
                # one continuous survey per nightly window (FR-CON-05)
                "continuous_done_today": any(
                    s["completed_at"] and s["completed_at"] >= window_start for s in sessions
                ),
            },
        }
        if not at_least(state["stage"], "PROTO"):  # FR-POS-06
            return base
        snap = conn.execute(LATEST_SNAPSHOT).fetchone()
        if snap is None:
            return base
        return {**base, **_shape(snap, at_least(state["stage"], "SEED"))}


@router.get("/history")
def history(
    cursor: int | None = Query(default=None, ge=1),
    limit_: int = Query(default=20, ge=1, le=50, alias="limit"),
    claims: dict = Depends(limit("history")),
):
    with user_tx(claims) as conn:
        rows = conn.execute(SNAPSHOT_PAGE, {"cursor": cursor, "n": limit_ + 1}).fetchall()
    items = [{"id": r["id"], **_shape(r, True)} for r in rows[:limit_]]
    return {"items": items, "next_cursor": rows[limit_ - 1]["id"] if len(rows) > limit_ else None}
