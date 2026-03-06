# file: src/market_adapter/base.py
"""
Abstract base class for market-data adapters.

Concrete implementations: FMPMarketAdapter (production), MockMarketAdapter (tests).
Factory function: create_market_adapter(config) -> MarketDataAdapter
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List

from src.events import MarketQuote


class MarketDataAdapter(abc.ABC):
    """Protocol for fetching real-time market data."""

    @abc.abstractmethod
    async def get_top_gainers(self, limit: int = 10) -> List[MarketQuote]:
        """Return the top *limit* intraday gaining stocks."""

    @abc.abstractmethod
    async def get_top_losers(self, limit: int = 10) -> List[MarketQuote]:
        """Return the top *limit* intraday losing stocks."""

    @abc.abstractmethod
    async def get_quote(self, symbol: str) -> MarketQuote:
        """Return the current quote for *symbol*."""

    @abc.abstractmethod
    async def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "1min",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Return intraday OHLCV bars.

        Each dict must contain keys: open, high, low, close, volume, datetime.
        """

    async def close(self) -> None:
        """Release any held resources (e.g., HTTP sessions)."""


def create_market_adapter(config: Dict[str, Any]) -> MarketDataAdapter:
    """
    Factory that returns the correct adapter based on *config['screener']['provider']*.

    Providers:
        'fmp'  -> FMPMarketAdapter  (FinancialModelingPrep)
        'mock' -> MockMarketAdapter (tests / offline demo)
    """
    provider = config.get("screener", {}).get("provider", "mock").lower()
    if provider == "fmp":
        from src.market_adapter.fmp_adapter import FMPMarketAdapter
        return FMPMarketAdapter(config)
    from src.market_adapter.mock_market import MockMarketAdapter
    return MockMarketAdapter()
