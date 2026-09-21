import time

from fastapi import APIRouter, Request, Response

from ..config import CONSENT_VERSIONS, get_settings
from ..db import service_tx

router = APIRouter()

STATS_TTL = 60.0
_stats: dict = {"at": -STATS_TTL, "value": {"participants": 0}}


def public_stats() -> dict:
    """Aggregate-only stats, cached in memory for 60 s."""
    now = time.monotonic()
    if now - _stats["at"] >= STATS_TTL:
        with service_tx() as conn:
            _stats["value"] = conn.execute("select app.public_stats() as s").fetchone()["s"]
        _stats["at"] = now
    return _stats["value"]


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.get("/v1/meta")
def meta(request: Request, response: Response):
    s = get_settings()
    model = request.app.state.model
    response.headers["Cache-Control"] = "public, max-age=60"
    return {
        "chart": {"version": model.version, "stage": model.stage},
        "participants": public_stats()["participants"],
        "emergency_level": s.emergency_level,
        "signup_enabled": s.signup_enabled,
        "survey_write_enabled": s.writes_enabled,
        "consent_versions": CONSENT_VERSIONS,
    }
