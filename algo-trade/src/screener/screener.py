# file: src/screener/screener.py
"""
Market screener — produces top-N gainers and losers every poll_interval seconds.

Production features:
  - Market-hours gate: waits for NYSE open before polling (configurable)
  - Publishes CandidateEvent to asyncio.Queue for downstream consumers
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from src.events import CandidateEvent
from src.logger import get_logger
from src.market_adapter.base import MarketDataAdapter
from src.market_hours import is_market_open, wait_for_market_open

log = get_logger(__name__)


class Screener:
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
        self._market_hours_only: bool = bool(scr_cfg.get("market_hours_only", True))

    async def _fetch(self) -> CandidateEvent:
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
        log.info("screener started", top_n=self._top_n, interval_secs=self._interval)
        while True:
            try:
                if self._market_hours_only and not is_market_open():
                    await wait_for_market_open(log)

                event = await self._fetch()
                await self._queue.put(event)
                await asyncio.sleep(self._interval)

            except asyncio.CancelledError:
                log.info("screener cancelled")
                return
            except Exception as exc:
                log.error("screener error", error=str(exc))
                await asyncio.sleep(30)
