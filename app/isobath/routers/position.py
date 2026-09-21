from fastapi import APIRouter, Depends, Query, Request
from psycopg import sql

from ..db import user_tx
from ..errors import api_error
from ..ratelimit import limit
from .meta import public_stats

router = APIRouter(prefix="/v1/me")

SNAPSHOT_COLS = sql.SQL(
    "id, chart_version, stage, map_xy, latent_se, confidence, memberships, near_boundary, created_at"
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
        "at": row["created_at"].isoformat(),
    }
    if with_regions and row["memberships"] is not None:
        out["regions"] = row["memberships"]
        out["near_boundary"] = row["near_boundary"]
    return out


@router.get("/position")
def position(request: Request, claims: dict = Depends(limit("position"))):
    model = request.app.state.model
    with user_tx(claims) as conn:
        profile = conn.execute("select observer_no from app.profiles").fetchone()
        if profile is None:
            raise api_error(404, "profile_not_found")
        sessions = conn.execute("select kind, status from app.survey_sessions").fetchall()
        base = {
            "chart": {"version": model.version, "stage": model.stage},
            "observer_no": profile["observer_no"],
            "participants": public_stats()["participants"],
            "survey": {
                "initial_completed": any(
                    s["kind"] == "initial" and s["status"] == "completed" for s in sessions
                ),
                "open_session": any(s["status"] == "open" for s in sessions),
            },
        }
        if not model.at_least("PROTO"):  # FR-POS-06
            return base
        snap = conn.execute(LATEST_SNAPSHOT).fetchone()
        if snap is None:
            return base
        return {**base, **_shape(snap, model.at_least("SEED"))}


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
