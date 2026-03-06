# file: src/options_fetcher/fetcher.py
"""
Options chain fetcher and liquidity filter.

Responsibilities:
1. Fetch the full option chain for a given symbol from the broker adapter.
2. Apply configurable liquidity filters (volume, OI, spread, DTE, moneyness).
3. Publish OptionChainEvent objects to the downstream queue.

Liquidity filter thresholds (all configurable):
    min_volume         : minimum daily option volume
    min_open_interest  : minimum open interest
    max_spread_pct     : maximum bid-ask spread as a fraction of mid-price
    max_dte            : maximum days-to-expiry (exclude far-dated)
    min_dte            : minimum days-to-expiry (exclude same-day expiry risk)
    max_otm_pct        : maximum fraction OTM (|strike - spot| / spot)
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from src.events import CandidateEvent, OptionChainEvent, OptionContract
from src.execution.base import BrokerAdapter
from src.logger import get_logger

log = get_logger(__name__)


def _days_to_expiry(expiry_str: str) -> int:
    """Return calendar days from today to *expiry_str* (YYYY-MM-DD)."""
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        return max(0, (expiry - date.today()).days)
    except ValueError:
        return 0


def apply_liquidity_filter(
    contracts: List[OptionContract],
    spot: float,
    min_volume: int = 100,
    min_open_interest: int = 500,
    max_spread_pct: float = 0.10,
    max_dte: int = 30,
    min_dte: int = 1,
    max_otm_pct: float = 0.15,
) -> List[OptionContract]:
    """
    Filter option contracts by liquidity and moneyness thresholds.

    Parameters
    ----------
    contracts          : raw option contracts from the broker.
    spot               : current underlying price.
    min_volume         : minimum daily option volume.
    min_open_interest  : minimum open interest.
    max_spread_pct     : max (ask - bid) / mid as a fraction.
    max_dte            : maximum days to expiry.
    min_dte            : minimum days to expiry.
    max_otm_pct        : maximum fraction OTM allowed.

    Returns
    -------
    List[OptionContract] — filtered subset.
    """
    result: List[OptionContract] = []
    for c in contracts:
        # Volume and open-interest checks.
        if c.volume < min_volume:
            continue
        if c.open_interest < min_open_interest:
            continue
        # Bid-ask spread check.
        if c.spread_pct > max_spread_pct:
            continue
        # DTE checks.
        dte = _days_to_expiry(c.expiry)
        if dte < min_dte or dte > max_dte:
            continue
        # OTM check.
        if spot > 0:
            otm = abs(c.strike - spot) / spot
            if otm > max_otm_pct:
                continue
        result.append(c)
    return result


class OptionsFetcher:
    """
    Listens on *candidate_queue*, fetches option chains via *broker*,
    applies liquidity filters, and publishes to *chain_queue*.
    """

    def __init__(
        self,
        broker: BrokerAdapter,
        candidate_queue: "asyncio.Queue[CandidateEvent]",
        chain_queue: "asyncio.Queue[OptionChainEvent]",
        config: Dict[str, Any],
    ) -> None:
        self._broker = broker
        self._candidate_queue = candidate_queue
        self._chain_queue = chain_queue
        flt = config.get("options_filter", {})
        self._min_volume: int = int(flt.get("min_volume", 100))
        self._min_oi: int = int(flt.get("min_open_interest", 500))
        self._max_spread: float = float(flt.get("max_spread_pct", 0.10))
        self._max_dte: int = int(flt.get("max_dte", 30))
        self._min_dte: int = int(flt.get("min_dte", 1))
        self._max_otm: float = float(flt.get("max_otm_pct", 0.15))

    async def _process_candidate(self, symbol: str, spot: float) -> None:
        """Fetch and filter options for a single symbol."""
        try:
            raw_contracts = await self._broker.get_option_chain(symbol)
            filtered = apply_liquidity_filter(
                raw_contracts,
                spot=spot,
                min_volume=self._min_volume,
                min_open_interest=self._min_oi,
                max_spread_pct=self._max_spread,
                max_dte=self._max_dte,
                min_dte=self._min_dte,
                max_otm_pct=self._max_otm,
            )
            if filtered:
                event = OptionChainEvent(symbol=symbol, contracts=filtered)
                await self._chain_queue.put(event)
                log.info(
                    "option chain ready",
                    symbol=symbol,
                    total=len(raw_contracts),
                    filtered=len(filtered),
                )
            else:
                log.debug("no liquid contracts found", symbol=symbol)
        except Exception as exc:
            log.error("options fetch failed", symbol=symbol, error=str(exc))

    async def run(self) -> None:
        """Consume CandidateEvents and emit OptionChainEvents indefinitely."""
        log.info("options_fetcher started")
        while True:
            try:
                event: CandidateEvent = await self._candidate_queue.get()
                # Process all candidates concurrently.
                tasks = []
                all_quotes = event.gainers + event.losers
                for quote in all_quotes:
                    tasks.append(
                        self._process_candidate(quote.symbol, quote.price)
                    )
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                log.info("options_fetcher cancelled")
                return
            except Exception as exc:
                log.error("options_fetcher loop error", error=str(exc))
