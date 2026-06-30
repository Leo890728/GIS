"""Per-source capture active-window: only capture inside configured hours.

Window config shape (under a source's ``history.active_window``)::

    {
        "timezone": "Asia/Taipei",            # optional, default Asia/Taipei
        "days": ["mon", "tue", ...],          # optional, default every day
        "ranges": [["06:00", "18:00"], ...],  # HH:MM pairs; required to gate
    }

No window (or empty ``ranges``) means "always capture". A range whose start is
later than its end (e.g. ``["22:00", "02:00"]``) spans midnight; for the
after-midnight portion the weekday is matched against the day the window started.
"""

from datetime import time
from zoneinfo import ZoneInfo

_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def window_timezone(window):
    """ZoneInfo for the window (defaults to Asia/Taipei)."""
    name = (window or {}).get("timezone") or "Asia/Taipei"
    return ZoneInfo(name)


def _parse_hhmm(value):
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def is_within_window(now_local, window):
    """True if ``now_local`` falls inside the window (always True without one)."""
    if not window:
        return True
    ranges = window.get("ranges") or []
    if not ranges:
        return True

    days = window.get("days")
    allowed_days = None
    if days:
        allowed_days = {_DAYS[d.lower()] for d in days if d.lower() in _DAYS}

    t = now_local.time()
    weekday = now_local.weekday()

    for start_s, end_s in ranges:
        start = _parse_hhmm(start_s)
        end = _parse_hhmm(end_s)
        if start <= end:
            in_range = start <= t < end
            day_for_check = weekday
        elif t >= start:           # overnight, evening portion -> today
            in_range = True
            day_for_check = weekday
        elif t < end:              # overnight, morning portion -> window's start day
            in_range = True
            day_for_check = (weekday - 1) % 7
        else:
            in_range = False
            day_for_check = weekday

        if in_range and (allowed_days is None or day_for_check in allowed_days):
            return True

    return False
