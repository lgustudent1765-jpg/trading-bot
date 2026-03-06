# file: src/market_adapter/poller.py
"""
Generic asynchronous polling loop with exponential-backoff error handling.

Design:
- fetch_fn is called every *interval* seconds.
- On success the result is placed on *queue* as a typed event.
- On error the failure is logged and the loop sleeps for backoff_secs
  before the next attempt (up to max_backoff_secs).
- The loop runs until the asyncio event loop is stopped.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from src.logger import get_logger

log = get_logger(__name__)


async def poll_loop(
    fetch_fn: Callable[[], Awaitable[Any]],
    queue: "asyncio.Queue[Any]",
    interval: float = 60.0,
    backoff_secs: float = 5.0,
    max_backoff_secs: float = 120.0,
    name: str = "poller",
) -> None:
    """
    Repeatedly call *fetch_fn* and enqueue the result.

    Parameters
    ----------
    fetch_fn        : async callable; must return a value to enqueue.
    queue           : asyncio.Queue where results are placed.
    interval        : nominal seconds between successful polls.
    backoff_secs    : initial sleep on error (doubles on repeated failures).
    max_backoff_secs: cap for exponential backoff.
    name            : label used in log messages.
    """
    current_backoff = backoff_secs
    while True:
        try:
            result = await fetch_fn()
            await queue.put(result)
            current_backoff = backoff_secs  # reset on success
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            log.info("poll_loop cancelled", poller=name)
            return
        except Exception as exc:
            log.error(
                "poll_loop error",
                poller=name,
                error=str(exc),
                next_retry_secs=current_backoff,
            )
            await asyncio.sleep(current_backoff)
            current_backoff = min(current_backoff * 2, max_backoff_secs)
