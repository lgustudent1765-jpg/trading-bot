# file: src/market_adapter/mock_market.py
"""
Mock market-data adapter for tests and paper-trade demos.

Returns deterministic synthetic data; no network access required.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from src.events import MarketQuote
from src.market_adapter.base import MarketDataAdapter

_GAINER_SYMBOLS = ["TSLA", "NVDA", "AMD", "META", "AMZN",
                   "GOOGL", "MSFT", "AAPL", "CRM", "NFLX"]
_LOSER_SYMBOLS  = ["F", "GM", "BA", "GE", "XOM",
                   "CVX", "T", "VZ", "PFE", "MRK"]


def _synthetic_bars(symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Generate OHLCV bars with a trend bias to reliably trigger RSI signals.

    Uses a random trend direction (+/-) per call so RSI(14) reliably reaches
    overbought (>70) or oversold (<30) territory within the lookback window,
    ensuring the strategy engine generates CALL or PUT signals.
    """
    base = 150.0
    bars = []
    ts = datetime.utcnow() - timedelta(minutes=limit)
    # Random trend: +0.35 (uptrend → RSI > 70) or -0.35 (downtrend → RSI < 30)
    trend = random.choice([0.35, -0.35])
    for i in range(limit):
        change = random.gauss(trend, 0.4)
        open_ = base
        close_ = max(1.0, base + change)
        high = max(open_, close_) + abs(random.gauss(0, 0.2))
        low = min(open_, close_) - abs(random.gauss(0, 0.2))
        vol = int(random.uniform(100_000, 500_000))
        bars.append({
            "datetime": (ts + timedelta(minutes=i)).isoformat(),
            "open": round(open_, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close_, 2),
            "volume": vol,
        })
        base = close_
    return bars


class MockMarketAdapter(MarketDataAdapter):
    """Deterministic mock adapter for testing and paper-trade demos."""

    async def get_top_gainers(self, limit: int = 10) -> List[MarketQuote]:
        return [
            MarketQuote(
                symbol=sym,
                price=round(150 + i * 5.0, 2),
                change_pct=round(3.0 + i * 0.5, 2),
                volume=500_000 + i * 10_000,
            )
            for i, sym in enumerate(_GAINER_SYMBOLS[:limit])
        ]

    async def get_top_losers(self, limit: int = 10) -> List[MarketQuote]:
        return [
            MarketQuote(
                symbol=sym,
                price=round(50 - i * 2.0, 2),
                change_pct=round(-3.0 - i * 0.5, 2),
                volume=300_000 + i * 5_000,
            )
            for i, sym in enumerate(_LOSER_SYMBOLS[:limit])
        ]

    async def get_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(
            symbol=symbol,
            price=150.0,
            change_pct=2.5,
            volume=400_000,
        )

    async def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "1min",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return _synthetic_bars(symbol, limit)
