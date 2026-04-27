# file: src/market_adapter/fmp_adapter.py
"""
FinancialModelingPrep (FMP) market-data adapter.

Implements MarketDataAdapter using the FMP REST API.
API key is read from config['market_data']['fmp_api_key'] (populated from
the FMP_API_KEY environment variable — never hardcoded).

Rate limiting: FMP free tier allows ~250 calls/day.  The screener polls
at most every 60 s; intraday bars are fetched on-demand per symbol.
Circuit breaker: after 3 consecutive failures the adapter raises and lets
the caller retry with exponential backoff.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.events import MarketQuote
from src.logger import get_logger
from src.market_adapter.base import MarketDataAdapter

log = get_logger(__name__)

_BASE = "https://financialmodelingprep.com/api/v3"

# PermissionError (401) is a config problem — never retry it.
_RETRYABLE = (aiohttp.ClientError, TimeoutError, ValueError)


class FMPMarketAdapter(MarketDataAdapter):
    """Adapter for FinancialModelingPrep REST API."""

    def __init__(self, config: Dict[str, Any]) -> None:
        md_cfg = config.get("market_data", {})
        self._api_key: str = md_cfg.get("fmp_api_key", "")
        self._base_url: str = md_cfg.get("base_url", _BASE)
        self._timeout: int = int(md_cfg.get("request_timeout", 10))
        self._retry_max: int = int(md_cfg.get("retry_max", 3))
        self._retry_backoff: float = float(md_cfg.get("retry_backoff", 2.0))
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=True)
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    async def _fetch_once(self, url: str, params: Dict) -> Any:
        """Single HTTP GET — raises on non-2xx; caller handles retries."""
        session = await self._get_session()
        async with session.get(url, params=params) as resp:
            if resp.status == 401:
                raise PermissionError(
                    "FMP API key invalid or endpoint requires a paid plan. "
                    "Check your FMP_API_KEY and account tier at financialmodelingprep.com"
                )
            resp.raise_for_status()
            return await resp.json()

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """GET with exponential-backoff retries via tenacity (skips 401 errors)."""
        url = f"{self._base_url}/{endpoint}"
        p: Dict[str, Any] = {"apikey": self._api_key}
        if params:
            p.update(params)

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._retry_max),
            wait=wait_exponential(multiplier=self._retry_backoff, min=1, max=30),
            reraise=True,
        ):
            with attempt:
                try:
                    return await self._fetch_once(url, p)
                except PermissionError:
                    log.error("FMP auth failed — check FMP_API_KEY and account plan", endpoint=endpoint)
                    raise
                except Exception as exc:
                    log.warning(
                        "FMP request failed",
                        endpoint=endpoint,
                        attempt=attempt.retry_state.attempt_number,
                        error=str(exc),
                    )
                    raise

    @staticmethod
    def _parse_quote(item: Dict[str, Any]) -> MarketQuote:
        return MarketQuote(
            symbol=item.get("symbol", ""),
            price=float(item.get("price", 0)),
            change_pct=float(item.get("changesPercentage", 0)),
            volume=int(item.get("volume", 0)),
            timestamp=datetime.utcnow(),
        )

    async def get_top_gainers(self, limit: int = 10) -> List[MarketQuote]:
        data = await self._get("stock_market/gainers")
        items = data if isinstance(data, list) else []
        return [self._parse_quote(i) for i in items[:limit]]

    async def get_top_losers(self, limit: int = 10) -> List[MarketQuote]:
        data = await self._get("stock_market/losers")
        items = data if isinstance(data, list) else []
        return [self._parse_quote(i) for i in items[:limit]]

    async def get_quote(self, symbol: str) -> MarketQuote:
        data = await self._get(f"quote/{symbol}")
        items = data if isinstance(data, list) else []
        if not items:
            raise ValueError(f"No quote data returned for {symbol}")
        return self._parse_quote(items[0])

    async def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "1min",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch intraday OHLCV bars from FMP.

        Returns list of dicts with keys: open, high, low, close, volume, datetime.
        """
        data = await self._get(
            f"historical-chart/{interval}/{symbol}",
        )
        bars = data if isinstance(data, list) else []
        # FMP returns newest first; reverse to chronological order.
        bars = list(reversed(bars[-limit:]))
        normalised = []
        for b in bars:
            normalised.append({
                "datetime": b.get("date", ""),
                "open": float(b.get("open", 0)),
                "high": float(b.get("high", 0)),
                "low": float(b.get("low", 0)),
                "close": float(b.get("close", 0)),
                "volume": int(b.get("volume", 0)),
            })
        return normalised

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
