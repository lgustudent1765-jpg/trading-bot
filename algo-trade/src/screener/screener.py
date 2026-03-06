# file: src/screener/screener.py
"""
Market screener — produces top-N gainers and losers every poll_interval seconds.

Publishes CandidateEvent objects to an asyncio.Queue for downstream consumers
(options_fetcher, strategy_engine).

Architecture note: The Screener wraps poll_loop and a MarketDataAdapter;
swap the adapter to change the data source without touching this class.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from src.events import CandidateEvent
from src.logger import get_logger
from src.market_adapter.base import MarketDataAdapter
from src.market_adapter.poller import poll_loop

log = get_logger(__name__)


class Screener:
    """
    Polls a MarketDataAdapter and publishes CandidateEvent objects.

    Parameters
    ----------
    adapter          : concrete MarketDataAdapter implementation.
    candidate_queue  : asyncio.Queue[CandidateEvent] consumed by downstream.
    config           : application configuration dict.
    """

    def __init__(
        self,
        adapter: MarketDataAdapter,
        candidate_queue: "asyncio.Queue[CandidateEvent]",
        config: Dict[str, Any],
    ) -> None:
        self._adapter = adapter
        self._queue = candidate_queue
        scr_cfg = config.get("screener", {})
        self._top_n: int = int(scr_cfg.get("top_n", 10))
        self._interval: float = float(scr_cfg.get("poll_interval_seconds", 60))

    async def _fetch(self) -> CandidateEvent:
        """Fetch gainers/losers and package them as a CandidateEvent."""
        gainers, losers = await asyncio.gather(
            self._adapter.get_top_gainers(self._top_n),
            self._adapter.get_top_losers(self._top_n),
        )
        event = CandidateEvent(gainers=gainers, losers=losers)
        log.info(
            "screener update",
            gainers=[q.symbol for q in gainers],
            losers=[q.symbol for q in losers],
        )
        return event

    async def run(self) -> None:
        """Start the polling loop; runs indefinitely until cancelled."""
        log.info(
            "screener started",
            top_n=self._top_n,
            interval_secs=self._interval,
        )
        await poll_loop(
            fetch_fn=self._fetch,
            queue=self._queue,
            interval=self._interval,
            name="screener",
        )
