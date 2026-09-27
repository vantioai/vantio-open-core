"""UTC timestamps with three fractional digits, and measured durations."""

import time
from datetime import datetime, timezone


def now_utc():
    return datetime.now(timezone.utc)


def format_utc(moment):
    """Format an aware or naive UTC instant as `YYYY-MM-DDTHH:MM:SS.mmmZ`."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    millis = moment.microsecond // 1000
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{millis:03d}Z"


def duration_ms(started_mono):
    if started_mono is None:
        return None
    return max(0, int((time.perf_counter() - started_mono) * 1000))
