# file: src/market_adapter/yahoo_adapter.py
"""
Yahoo Finance market-data adapter.

Uses Yahoo Finance's JSON endpoints directly via aiohttp.
No API key required. No pandas dependency.

Rate limits: Yahoo Finance allows ~2,000 requests/hour per IP on the
free tier. The screener polls at most every 60 s, so this is well within limits.

Endpoints used:
  Screener : query1.finance.yahoo.com/v1/finance/screener/predefined/saved
  Chart    : query1.finance.yahoo.com/v8/finance/chart/{symbol}
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from src.events import MarketQuote
from src.logger import get_logger
from src.market_adapter.base import MarketDataAdapter

log = get_logger(__name__)

_BASE_SCREENER = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
_BASE_CHART    = "https://query1.finance.yahoo.com/v8/finance/chart"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Yahoo Finance interval strings
_INTERVAL_MAP = {
    "1min":  "1m",
    "5min":  "5m",
    "15min": "15m",
    "1h":    "60m",
    "1d":    "1d",
}


class YahooFinanceAdapter(MarketDataAdapter):
    """
    Market-data adapter backed by Yahoo Finance JSON endpoints.
    No API key or paid subscription required.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        md_cfg = config.get("market_data", {})
        self._timeout: int = int(md_cfg.get("request_timeout", 10))
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=True)
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(
                connector=connector, timeout=timeout, headers=_HEADERS
            )
        return self._session

    async def _get(self, url: str, params: Dict[str, Any]) -> Any:
        session = await self._get_session()
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _fetch_screener(self, scr_id: str, limit: int) -> List[MarketQuote]:
        """Fetch a predefined Yahoo Finance screener by ID."""
        try:
            data = await self._get(
                _BASE_SCREENER,
                {"scrIds": scr_id, "count": limit, "formatted": "false"},
            )
            quotes_raw = (
                data.get("finance", {})
                    .get("result", [{}])[0]
                    .get("quotes", [])
            )
            result = []
            for q in quotes_raw[:limit]:
                result.append(MarketQuote(
                    symbol=q.get("symbol", ""),
                    price=float(q.get("regularMarketPrice", 0)),
                    change_pct=float(q.get("regularMarketChangePercent", 0)),
                    volume=int(q.get("regularMarketVolume", 0)),
                    timestamp=datetime.now(timezone.utc),
                ))
            return result
        except Exception as exc:
            log.error("Yahoo screener fetch failed", scr_id=scr_id, error=str(exc))
            return []

    async def get_top_gainers(self, limit: int = 10) -> List[MarketQuote]:
        return await self._fetch_screener("day_gainers", limit)

    async def get_top_losers(self, limit: int = 10) -> List[MarketQuote]:
        return await self._fetch_screener("day_losers", limit)

    async def get_quote(self, symbol: str) -> MarketQuote:
        data = await self._get(f"{_BASE_CHART}/{symbol}", {"interval": "1d", "range": "1d"})
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        return MarketQuote(
            symbol=symbol,
            price=float(meta.get("regularMarketPrice", 0)),
            change_pct=float(meta.get("regularMarketChangePercent", 0)),
            volume=int(meta.get("regularMarketVolume", 0)),
            timestamp=datetime.now(timezone.utc),
        )

    async def _fetch_bars_for_range(
        self,
        symbol: str,
        yf_interval: str,
        range_str: str,
    ) -> List[Dict[str, Any]]:
        data = await self._get(
            f"{_BASE_CHART}/{symbol}",
            {"interval": yf_interval, "range": range_str, "includePrePost": "false"},
        )
        result_block = data.get("chart", {}).get("result", [])
        if not result_block:
            return []
        block      = result_block[0]
        timestamps = block.get("timestamp", [])
        quote_data = block.get("indicators", {}).get("quote", [{}])[0]
        opens   = quote_data.get("open",   [])
        highs   = quote_data.get("high",   [])
        lows    = quote_data.get("low",    [])
        closes  = quote_data.get("close",  [])
        volumes = quote_data.get("volume", [])
        bars = []
        for i, ts in enumerate(timestamps):
            try:
                o = opens[i];  h = highs[i]
                l = lows[i];   c = closes[i]
                v = volumes[i]
                if None in (o, h, l, c):
                    continue
                bars.append({
                    "datetime": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                    "open":   float(o),
                    "high":   float(h),
                    "low":    float(l),
                    "close":  float(c),
                    "volume": int(v) if v is not None else 0,
                })
            except (IndexError, TypeError):
                continue
        return bars

    async def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "1min",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch intraday OHLCV bars from Yahoo Finance.

        Tries today's data first (1d range). If fewer than `limit` bars are
        returned — e.g. early in the session, weekends, or illiquid stocks —
        falls back to the last 5 trading days of 1-minute bars. Yahoo Finance
        keeps up to 7 days of 1-minute history.
        """
        yf_interval = _INTERVAL_MAP.get(interval, "1m")
        try:
            bars = await self._fetch_bars_for_range(symbol, yf_interval, "1d")
            if len(bars) < limit:
                # Not enough bars from today — pull the last 5 trading days.
                bars = await self._fetch_bars_for_range(symbol, yf_interval, "5d")
            return bars[-limit:]
        except Exception as exc:
            log.error("Yahoo intraday bars failed", symbol=symbol, error=str(exc))
            return []

    async def get_historical_bars(
        self,
        symbol: str,
        range_str: str = "1d",
        interval: str = "1m",
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV bars for any range/interval combination supported by Yahoo Finance.

        range_str: "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"
        interval:  "1m", "2m", "5m", "15m", "30m", "60m", "1d", "1wk"
        """
        try:
            data = await self._get(
                f"{_BASE_CHART}/{symbol}",
                {"interval": interval, "range": range_str, "includePrePost": "false"},
            )
            result_block = data.get("chart", {}).get("result", [])
            if not result_block:
                return []

            block      = result_block[0]
            timestamps = block.get("timestamp", [])
            quote_data = block.get("indicators", {}).get("quote", [{}])[0]
            opens   = quote_data.get("open",   [])
            highs   = quote_data.get("high",   [])
            lows    = quote_data.get("low",    [])
            closes  = quote_data.get("close",  [])
            volumes = quote_data.get("volume", [])

            bars = []
            for i, ts in enumerate(timestamps):
                try:
                    o = opens[i];  h = highs[i]
                    l = lows[i];   c = closes[i]
                    v = volumes[i]
                    if None in (o, h, l, c):
                        continue
                    bars.append({
                        "datetime": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                        "open":   float(o),
                        "high":   float(h),
                        "low":    float(l),
                        "close":  float(c),
                        "volume": int(v) if v is not None else 0,
                    })
                except (IndexError, TypeError):
                    continue
            return bars
        except Exception as exc:
            log.error("Yahoo historical bars failed", symbol=symbol, range=range_str, error=str(exc))
            return []

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
