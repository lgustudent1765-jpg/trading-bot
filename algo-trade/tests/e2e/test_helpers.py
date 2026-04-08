# file: tests/e2e/test_helpers.py
"""
Shared test utilities — builders, seed helpers, async wait functions.

Import these in spec files instead of duplicating logic.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Dict, Optional

from src.events import (
    CandidateEvent,
    MarketQuote,
    OptionChainEvent,
    OptionContract,
    SignalDirection,
    SignalEvent,
    TradePlan,
)


# ---------------------------------------------------------------------------
# Event builders
# ---------------------------------------------------------------------------

def make_market_quote(
    symbol: str = "AAPL",
    price: float = 174.50,
    change_pct: float = 3.2,
    volume: int = 5_000_000,
) -> MarketQuote:
    """Return a MarketQuote with the given (or default) values."""
    return MarketQuote(symbol=symbol, price=price, change_pct=change_pct, volume=volume)


def make_candidate_event(gainers=None, losers=None) -> CandidateEvent:
    """Build a CandidateEvent with configurable gainers/losers lists."""
    if gainers is None:
        gainers = [make_market_quote("AAPL", change_pct=4.5)]
    if losers is None:
        losers = [make_market_quote("META", change_pct=-3.2)]
    return CandidateEvent(gainers=gainers, losers=losers)


def make_option_contract(
    symbol: str = "AAPL",
    strike: float = 175.0,
    option_type: str = "call",
    bid: float = 2.40,
    ask: float = 2.50,
    volume: int = 3000,
    open_interest: int = 12000,
    iv: float = 0.32,
    delta: float = 0.48,
    underlying_price: float = 174.50,
    dte: int = 14,
) -> OptionContract:
    expiry = (date.today() + timedelta(days=dte)).isoformat()
    return OptionContract(
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        option_type=option_type,
        bid=bid,
        ask=ask,
        volume=volume,
        open_interest=open_interest,
        implied_volatility=iv,
        delta=delta,
        underlying_price=underlying_price,
    )


def make_chain_event(
    symbol: str = "AAPL",
    contracts: Optional[list] = None,
) -> OptionChainEvent:
    if contracts is None:
        contracts = [
            make_option_contract(symbol=symbol, option_type="call"),
            make_option_contract(symbol=symbol, option_type="put", delta=-0.42),
        ]
    return OptionChainEvent(symbol=symbol, contracts=contracts)


def make_trade_plan(
    symbol: str = "AAPL",
    direction: SignalDirection = SignalDirection.CALL,
    entry_limit: float = 2.55,
    stop_loss: float = 1.85,
    take_profit: float = 4.15,
    position_size: int = 10,
    rsi: float = 72.3,
    macd_hist: float = 0.082,
) -> TradePlan:
    contract = make_option_contract(symbol=symbol)
    return TradePlan(
        symbol=symbol,
        direction=direction,
        contract=contract,
        entry_limit=entry_limit,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        rsi=rsi,
        macd_hist=macd_hist,
        rationale=f"RSI={rsi:.1f}, MACD_hist={macd_hist:.4f}",
    )


def make_signal_event(
    symbol: str = "AAPL",
    direction: SignalDirection = SignalDirection.CALL,
) -> SignalEvent:
    return SignalEvent(trade_plan=make_trade_plan(symbol=symbol, direction=direction))


# ---------------------------------------------------------------------------
# Signal dict builder (for SignalStore)
# ---------------------------------------------------------------------------

def make_signal_dict(
    symbol: str = "AAPL",
    direction: str = "CALL",
    rsi: float = 72.0,
) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "direction": direction,
        "strike": 175.0,
        "expiry": (date.today() + timedelta(days=14)).isoformat(),
        "option_type": "call" if direction == "CALL" else "put",
        "entry": 2.55,
        "stop": 1.85,
        "target": 4.15,
        "size": 10,
        "rsi": rsi,
        "macd_hist": 0.082,
        "delta": 0.48,
        "iv": 0.32,
        "underlying_price": 174.50,
        "bid": 2.40,
        "ask": 2.50,
        "volume": 3000,
        "open_interest": 12000,
        "rationale": f"RSI={rsi:.1f}",
        "ts": "2026-04-07T09:35:00+00:00",
    }


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

async def drain_queue(queue: asyncio.Queue, expected: int = 1, timeout: float = 2.0) -> list:
    """
    Pull *expected* items from *queue* within *timeout* seconds.
    Returns whatever was collected (may be fewer than expected on timeout).
    """
    collected = []
    deadline = asyncio.get_event_loop().time() + timeout
    while len(collected) < expected:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            item = await asyncio.wait_for(queue.get(), timeout=remaining)
            collected.append(item)
        except asyncio.TimeoutError:
            break
    return collected


async def run_one_iteration(coro, *, timeout: float = 2.0):
    """
    Start *coro* as a task, let it run for *timeout* seconds, then cancel it.
    Returns the task so callers can inspect its result if desired.
    """
    task = asyncio.ensure_future(coro)
    await asyncio.sleep(timeout)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return task
