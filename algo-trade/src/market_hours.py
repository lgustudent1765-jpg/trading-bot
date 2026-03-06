# file: src/market_hours.py
"""
NYSE / NASDAQ market-hours enforcement.

Uses Python stdlib only — no pytz dependency.
Handles US Eastern Time (ET) including automatic DST transitions via
zoneinfo (Python 3.9+, included in stdlib).

Observed holidays (NYSE) are hard-coded for the current year and updated
each January.  For a production system consider fetching from a data
provider or using the `trading_calendars` package.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

_MARKET_OPEN  = time(9, 30)
_MARKET_CLOSE = time(16, 0)

# NYSE holidays 2025-2026 (update annually)
_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 20),  # MLK Day
    date(2025, 2, 17),  # Presidents' Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 26),  # Memorial Day
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),   # Independence Day
    date(2025, 9, 1),   # Labor Day
    date(2025, 11, 27), # Thanksgiving
    date(2025, 12, 25), # Christmas
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day
    date(2026, 2, 16),  # Presidents' Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}


def now_et() -> datetime:
    """Return the current datetime in US/Eastern time."""
    return datetime.now(tz=ET)


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """
    Return True if the NYSE is currently open for regular trading.

    Parameters
    ----------
    dt : datetime in any timezone (converted to ET internally).
         Defaults to now.
    """
    if dt is None:
        dt = now_et()
    else:
        dt = dt.astimezone(ET)

    if dt.weekday() >= 5:          # Saturday=5, Sunday=6
        return False
    if dt.date() in _HOLIDAYS:
        return False

    t = dt.time()
    return _MARKET_OPEN <= t < _MARKET_CLOSE


def seconds_until_open(dt: Optional[datetime] = None) -> float:
    """
    Return seconds until the next market open.
    Returns 0 if the market is currently open.
    """
    if dt is None:
        dt = now_et()
    else:
        dt = dt.astimezone(ET)

    if is_market_open(dt):
        return 0.0

    # Find next weekday that isn't a holiday.
    candidate = dt.replace(hour=9, minute=30, second=0, microsecond=0)
    if dt.time() >= _MARKET_CLOSE or dt.weekday() >= 5 or dt.date() in _HOLIDAYS:
        # Move to next calendar day.
        from datetime import timedelta
        candidate = candidate + timedelta(days=1)

    while candidate.weekday() >= 5 or candidate.date() in _HOLIDAYS:
        from datetime import timedelta
        candidate = candidate + timedelta(days=1)

    delta = (candidate - dt).total_seconds()
    return max(0.0, delta)


async def wait_for_market_open(log=None) -> None:
    """
    Async sleep until the NYSE opens.
    Logs a message if a logger is provided.
    """
    wait = seconds_until_open()
    if wait <= 0:
        return

    hours = int(wait // 3600)
    minutes = int((wait % 3600) // 60)
    msg = f"Market closed — waiting {hours}h {minutes}m until open"

    if log:
        log.info(msg)
    else:
        print(msg)

    await asyncio.sleep(wait)
