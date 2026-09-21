from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from ..config import CONSENT_VERSIONS, REQUIRED_CONSENTS, get_settings
from ..cycle import next_cutoff
from ..db import service_tx
from ..errors import api_error
from ..runs import chart_state, timestamps

router = APIRouter()

PENDING_BATCH_MAX_AGE = 300  # today's batch not finished yet: re-check every 5 minutes


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.get("/v1/meta")
def meta(request: Request, response: Response):
    s = get_settings()
    state = chart_state(request.app.state.model)
    response.headers["Cache-Control"] = "public, max-age=60"
    return {
        "chart": {"version": state["version"], "stage": state["stage"]},
        "participants": state["participants"],
        **timestamps(state),
        "stale": state["stale"],
        "emergency_level": s.emergency_level,
        "signup_enabled": s.signup_enabled,
        "survey_write_enabled": s.writes_enabled,
        "consent_versions": CONSENT_VERSIONS,
        "consent_required": list(REQUIRED_CONSENTS),
    }


@router.get("/v1/chart/current")
def chart(request: Request, response: Response):
    """Aggregated density grid from the last nightly batch; CDN-cacheable until it can change."""
    state = chart_state(request.app.state.model)
    if not state["has_map"]:
        raise api_error(404, "chart_not_ready")
    with service_tx() as conn:
        run = conn.execute(
            "select cutoff_at, chart_version, stage, map from app.batch_runs where cutoff_at = %s",
            (state["updated_at"],),
        ).fetchone()
    now = datetime.now(UTC)
    max_age = (
        int((next_cutoff(now) - now).total_seconds())
        if state["current_window_done"]
        else PENDING_BATCH_MAX_AGE
    )
    response.headers["Cache-Control"] = f"public, max-age={max_age}"
    return {
        "chart": {"version": run["chart_version"], "stage": run["stage"]},
        **timestamps(state),
        "map": run["map"],
    }
