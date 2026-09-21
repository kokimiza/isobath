"""In-process token bucket per (user, endpoint) (NFR-RL-01)."""

import time
from threading import Lock

from fastapi import Depends, Request

from .auth import current_claims
from .errors import api_error

# endpoint -> (capacity, refill per second)
LIMITS = {
    "position": (60, 1.0),
    "history": (30, 0.5),
    "survey_read": (30, 0.5),
    "answers": (20, 0.2),
    "survey_create": (5, 0.01),
    "account": (5, 0.01),
}

# ponytail: in-memory, single worker. Move to Redis etc. if running multiple instances.
_buckets: dict[tuple[str, str], tuple[float, float]] = {}
_lock = Lock()


def take(key: tuple[str, str], capacity: int, rate: float, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    with _lock:
        tokens, last = _buckets.get(key, (capacity, now))
        tokens = min(capacity, tokens + (now - last) * rate)
        if tokens < 1:
            _buckets[key] = (tokens, now)
            return False
        _buckets[key] = (tokens - 1, now)
        return True


def limit(endpoint: str):
    capacity, rate = LIMITS[endpoint]

    def dep(request: Request, claims: dict = Depends(current_claims)) -> dict:
        if not take((claims["sub"], endpoint), capacity, rate):
            raise api_error(429, "rate_limited")
        return claims

    return dep
