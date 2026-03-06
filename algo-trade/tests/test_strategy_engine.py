# file: tests/test_strategy_engine.py
"""
Unit tests for the StrategyEngine.

Verifies: RSI > 70 + positive MACD hist -> CALL signal with contract & plan.
Uses MockMarketAdapter with synthetic data crafted to cross the thresholds.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from src.events import (
    OptionChainEvent,
    OptionContract,
    SignalDirection,
    SignalEvent,
)
from src.market_adapter.mock_market import MockMarketAdapter
from src.strategy_engine import StrategyEngine


def _make_overbought_bars(n: int = 60) -> List[Dict[str, Any]]:
    """Generate bars where price rises sharply -> RSI > 70."""
    base = 100.0
    bars = []
    for i in range(n):
        close = base + i * 1.0  # monotone uptrend
        bars.append({
            "datetime": f"2024-01-01 {i:02d}:00:00",
            "open": close - 0.2,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": 100_000,
        })
    return bars


def _make_oversold_bars(n: int = 60) -> List[Dict[str, Any]]:
    """Generate bars where price falls sharply -> RSI < 30."""
    base = 200.0
    bars = []
    for i in range(n):
        close = base - i * 1.0
        bars.append({
            "datetime": f"2024-01-01 {i:02d}:00:00",
            "open": close + 0.2,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": 100_000,
        })
    return bars


def _make_chain(symbol: str = "AAPL", spot: float = 150.0) -> OptionChainEvent:
    expiry = (date.today() + timedelta(days=14)).isoformat()
    contracts = [
        OptionContract(
            symbol=symbol,
            expiry=expiry,
            strike=150.0,
            option_type="call",
            bid=2.00,
            ask=2.10,
            volume=1000,
            open_interest=5000,
            implied_volatility=0.35,
            underlying_price=spot,
        ),
        OptionContract(
            symbol=symbol,
            expiry=expiry,
            strike=150.0,
            option_type="put",
            bid=1.90,
            ask=2.00,
            volume=900,
            open_interest=4000,
            implied_volatility=0.33,
            underlying_price=spot,
        ),
    ]
    return OptionChainEvent(symbol=symbol, contracts=contracts)


def _config() -> Dict[str, Any]:
    return {
        "indicators": {
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "atr_period": 14,
            "lookback_bars": 50,
        },
        "risk": {
            "stop_loss_atr_mult": 1.5,
            "take_profit_atr_mult": 3.0,
        },
    }


class TestStrategyEngine:
    async def _run_engine_with_bars(self, bars, chain_event) -> List[SignalEvent]:
        """Helper: run the engine for one chain event and return emitted signals."""
        market = MockMarketAdapter()
        chain_q: asyncio.Queue = asyncio.Queue()
        signal_q: asyncio.Queue = asyncio.Queue()

        with patch.object(market, "get_intraday_bars", new=AsyncMock(return_value=bars)):
            engine = StrategyEngine(market, chain_q, signal_q, _config())
            await chain_q.put(chain_event)
            task = asyncio.ensure_future(engine.run())
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        signals = []
        while not signal_q.empty():
            signals.append(signal_q.get_nowait())
        return signals

    @pytest.mark.asyncio
    async def test_overbought_generates_call_signal(self):
        """RSI > 70 + positive MACD hist -> CALL signal."""
        bars = _make_overbought_bars(60)
        chain = _make_chain("AAPL", spot=150.0)
        signals = await self._run_engine_with_bars(bars, chain)
        assert len(signals) == 1
        plan = signals[0].trade_plan
        assert plan.direction == SignalDirection.CALL
        assert plan.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_oversold_generates_put_signal(self):
        """RSI < 30 + negative MACD hist -> PUT signal."""
        bars = _make_oversold_bars(60)
        chain = _make_chain("AAPL", spot=150.0)
        signals = await self._run_engine_with_bars(bars, chain)
        assert len(signals) == 1
        plan = signals[0].trade_plan
        assert plan.direction == SignalDirection.PUT

    @pytest.mark.asyncio
    async def test_call_signal_has_valid_entry_stop_target(self):
        """For a CALL signal: stop < entry < target."""
        bars = _make_overbought_bars(60)
        chain = _make_chain("AAPL", spot=150.0)
        signals = await self._run_engine_with_bars(bars, chain)
        assert len(signals) == 1
        plan = signals[0].trade_plan
        assert plan.stop_loss < plan.entry_limit < plan.take_profit

    @pytest.mark.asyncio
    async def test_signal_references_correct_contract(self):
        """Signal contract must be of type 'call' for a CALL signal."""
        bars = _make_overbought_bars(60)
        chain = _make_chain("AAPL", spot=150.0)
        signals = await self._run_engine_with_bars(bars, chain)
        assert len(signals) == 1
        plan = signals[0].trade_plan
        assert plan.contract.option_type == "call"

    @pytest.mark.asyncio
    async def test_flat_market_generates_no_signal(self):
        """Flat prices produce neutral RSI/MACD -> no signal."""
        flat_bars = [
            {
                "datetime": f"2024-01-01 {i:02d}:00:00",
                "open": 100.0,
                "high": 100.5,
                "low": 99.5,
                "close": 100.0,
                "volume": 100_000,
            }
            for i in range(60)
        ]
        chain = _make_chain("AAPL", spot=100.0)
        signals = await self._run_engine_with_bars(flat_bars, chain)
        assert len(signals) == 0
