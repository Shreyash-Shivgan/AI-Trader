from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

_SESSION_WINDOWS = {
    "asian": (time(0, 0), time(8, 59)),
    "london": (time(7, 0), time(15, 59)),
    "new_york": (time(12, 0), time(20, 59)),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def detect_session(moment: datetime | None = None) -> str:
    current = moment or _utc_now()
    current_time = current.astimezone(timezone.utc).time()
    for session_name, (start, end) in _SESSION_WINDOWS.items():
        if start <= current_time <= end:
            return session_name
    return "off_hours"


def session_bias(moment: datetime | None = None) -> dict[str, str | bool]:
    session = detect_session(moment)
    overlap = (
        session == "new_york"
        and 12 <= (moment or _utc_now()).astimezone(timezone.utc).hour <= 15
    )
    bias = "neutral"
    if session == "asian":
        bias = "mean_reversion"
    elif session == "london":
        bias = "trend_expansion"
    elif session == "new_york":
        bias = "volatility_expansion"
    return {"session": session, "bias": bias, "overlap": overlap}
