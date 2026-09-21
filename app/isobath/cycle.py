"""Daily cutoff cycle (requirements §4.1).

A window is [01:00 JST, next day 01:00 JST). A session belongs to the window that contains its
server-side `completed_at`; the nightly batch for cutoff C processes everything completed before C.
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")  # no daylight saving
CUTOFF_TIME = time(1, 0)
DAY = timedelta(days=1)
STALE_AFTER = timedelta(hours=26)


def current_cutoff(now: datetime) -> datetime:
    """Latest 01:00 JST at or before `now`, in UTC."""
    local = now.astimezone(JST)
    cutoff = datetime.combine(local.date(), CUTOFF_TIME, tzinfo=JST)
    if local < cutoff:
        cutoff -= DAY
    return cutoff.astimezone(UTC)


def next_cutoff(now: datetime) -> datetime:
    return current_cutoff(now) + DAY


def iso(t: datetime | None) -> str | None:
    return t.astimezone(UTC).isoformat().replace("+00:00", "Z") if t else None
