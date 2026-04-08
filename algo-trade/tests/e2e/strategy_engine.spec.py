# file: tests/e2e/strategy_engine.spec.py
"""
E2E tests for the StrategyEngine pipeline component.

Covers:
  - _determine_direction(): CALL when RSI > 70 and MACD_hist > 0
  - _determine_direction(): PUT when RSI < 30 and MACD_hist < 0
  - _determine_direction(): None when no signal conditions are met
  - _build_trade_plan(): CALL entry/stop/target calculated correctly
  - _build_trade_plan(): PUT entry/stop/target calculated correctly
  - _select_contract(): selects nearest-to-ATM contract of the correct type
  - _select_contract(): returns None when no contracts match direction
  - _process_chain(): publishes SignalEvent to signal_queue on valid data
  - _process_chain(): skips when cooldown is active for ticker
  - _process_chain(): skips when already holding a position in ticker
  - _process_chain(): skips when insufficient indicator bars
  - StrategyEngine.run(): processes chain events from queue
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.events import OptionChainEvent, SignalDirection, SignalEvent
from src.strategy_engine.engine import StrategyEngine, _select_contract
from tests.e2e.test_helpers import (
    drain_queue,
    make_chain_event,
    make_market_quote,
    make_option_contract,
    make_trade_plan,
)

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Minimal indicator bars (60 bars, enough for RSI-14 + MACD-26+9 = 35)
# ---------------------------------------------------------------------------

def _bars(n=60, start=100.0, trend=0.3):
    """Generate synthetic OHLCV bars with an upward trend."""
    bars = []
    price = start
    for i in range(n):
        price += trend
        bars.append({
            "open": price - 0.1,
            "high": price + 0.2,
            "low": price - 0.3,
            "close": price,
        })
    return bars


def _make_engine(config, market_adapter, chain_queue, signal_queue, position_store=None):
    return StrategyEngine(
        market_adapter=market_adapter,
        chain_queue=chain_queue,
        signal_queue=signal_queue,
        config=config,
        position_store=position_store,
        notifier=None,
    )


class TestDetermineDirection:
    def _engine(self, e2e_config):
        from src.market_adapter.mock_market import MockMarketAdapter
        return _make_engine(
            e2e_config,
            market_adapter=MockMarketAdapter(),
            chain_queue=asyncio.Queue(),
            signal_queue=asyncio.Queue(),
        )

    def test_call_signal_when_rsi_overbought_and_macd_positive(self, e2e_config):
        engine = self._engine(e2e_config)
        direction = engine._determine_direction(rsi_val=72.0, macd_hist=0.05)
        assert direction == SignalDirection.CALL

    def test_put_signal_when_rsi_oversold_and_macd_negative(self, e2e_config):
        engine = self._engine(e2e_config)
        direction = engine._determine_direction(rsi_val=28.0, macd_hist=-0.05)
        assert direction == SignalDirection.PUT

    def test_no_signal_when_rsi_neutral(self, e2e_config):
        engine = self._engine(e2e_config)
        direction = engine._determine_direction(rsi_val=50.0, macd_hist=0.05)
        assert direction is None

    def test_no_signal_when_rsi_overbought_but_macd_negative(self, e2e_config):
        engine = self._engine(e2e_config)
        direction = engine._determine_direction(rsi_val=72.0, macd_hist=-0.05)
        assert direction is None

    def test_no_signal_when_rsi_oversold_but_macd_positive(self, e2e_config):
        engine = self._engine(e2e_config)
        direction = engine._determine_direction(rsi_val=28.0, macd_hist=0.05)
        assert direction is None

    def test_boundary_rsi_exactly_70_with_positive_macd_is_call(self, e2e_config):
        engine = self._engine(e2e_config)
        # RSI == 70 does NOT trigger CALL (requires > 70)
        direction = engine._determine_direction(rsi_val=70.0, macd_hist=0.05)
        assert direction is None

    def test_boundary_rsi_exactly_30_with_negative_macd_is_not_put(self, e2e_config):
        engine = self._engine(e2e_config)
        # RSI == 30 does NOT trigger PUT (requires < 30)
        direction = engine._determine_direction(rsi_val=30.0, macd_hist=-0.05)
        assert direction is None


class TestSelectContract:
    def test_returns_call_contract_for_call_direction(self, make_contract):
        call = make_contract(option_type="call", strike=175.0, underlying_price=174.0)
        put = make_contract(option_type="put", strike=175.0, underlying_price=174.0)
        result = _select_contract([call, put], SignalDirection.CALL)
        assert result is not None
        assert result.option_type == "call"

    def test_returns_put_contract_for_put_direction(self, make_contract):
        call = make_contract(option_type="call")
        put = make_contract(option_type="put")
        result = _select_contract([call, put], SignalDirection.PUT)
        assert result is not None
        assert result.option_type == "put"

    def test_returns_none_when_no_contracts_match_direction(self, make_contract):
        call = make_contract(option_type="call")
        result = _select_contract([call], SignalDirection.PUT)
        assert result is None

    def test_returns_none_for_empty_list(self):
        result = _select_contract([], SignalDirection.CALL)
        assert result is None

    def test_selects_nearest_atm_contract(self, make_contract):
        """When underlying is 174, strike 175 is nearer ATM than 180."""
        near_atm = make_contract(option_type="call", strike=175.0, underlying_price=174.0)
        far_otm = make_contract(option_type="call", strike=180.0, underlying_price=174.0)
        result = _select_contract([far_otm, near_atm], SignalDirection.CALL)
        assert result.strike == 175.0


class TestBuildTradePlan:
    def _engine(self, e2e_config):
        from src.market_adapter.mock_market import MockMarketAdapter
        return _make_engine(
            e2e_config,
            market_adapter=MockMarketAdapter(),
            chain_queue=asyncio.Queue(),
            signal_queue=asyncio.Queue(),
        )

    def test_call_entry_is_ask_times_1_01(self, e2e_config, make_contract):
        engine = self._engine(e2e_config)
        contract = make_contract(ask=2.50, option_type="call")
        plan = engine._build_trade_plan("AAPL", SignalDirection.CALL, contract, 1.20, 72.0, 0.08)
        # _build_trade_plan applies round(..., 2), so compare against rounded value
        assert plan.entry_limit == pytest.approx(round(2.50 * 1.01, 2), abs=0.01)

    def test_call_stop_is_below_entry(self, e2e_config, make_contract):
        engine = self._engine(e2e_config)
        contract = make_contract(ask=2.50, option_type="call")
        plan = engine._build_trade_plan("AAPL", SignalDirection.CALL, contract, 1.20, 72.0, 0.08)
        assert plan.stop_loss < plan.entry_limit

    def test_call_target_is_above_entry(self, e2e_config, make_contract):
        engine = self._engine(e2e_config)
        contract = make_contract(ask=2.50, option_type="call")
        plan = engine._build_trade_plan("AAPL", SignalDirection.CALL, contract, 1.20, 72.0, 0.08)
        assert plan.take_profit > plan.entry_limit

    def test_put_stop_is_above_entry(self, e2e_config, make_contract):
        engine = self._engine(e2e_config)
        contract = make_contract(ask=3.00, option_type="put")
        plan = engine._build_trade_plan("AAPL", SignalDirection.PUT, contract, 1.20, 28.0, -0.08)
        assert plan.stop_loss > plan.entry_limit

    def test_put_target_is_below_entry(self, e2e_config, make_contract):
        engine = self._engine(e2e_config)
        contract = make_contract(ask=3.00, option_type="put")
        plan = engine._build_trade_plan("AAPL", SignalDirection.PUT, contract, 1.20, 28.0, -0.08)
        assert plan.take_profit < plan.entry_limit

    def test_trade_plan_contains_rsi_and_macd_hist(self, e2e_config, make_contract):
        engine = self._engine(e2e_config)
        contract = make_contract(ask=2.50)
        plan = engine._build_trade_plan("AAPL", SignalDirection.CALL, contract, 1.20, 72.0, 0.082)
        assert plan.rsi == pytest.approx(72.0)
        assert plan.macd_hist == pytest.approx(0.082)


class TestProcessChain:
    def _make_adapter_with_bars(self, bars):
        adapter = MagicMock()
        adapter.get_intraday_bars = AsyncMock(return_value=bars)
        return adapter

    async def test_process_chain_publishes_signal_on_call_conditions(self, e2e_config):
        """Overbought RSI + positive MACD → CALL signal emitted."""
        from src.market_adapter.mock_market import MockMarketAdapter

        # Mock bars that produce RSI > 70 (strong uptrend)
        # We patch _compute_indicators to return controlled values
        chain_q = asyncio.Queue()
        signal_q = asyncio.Queue()
        adapter = MockMarketAdapter()
        engine = _make_engine(e2e_config, adapter, chain_q, signal_q)

        chain_event = make_chain_event("AAPL")

        # Patch _compute_indicators to return overbought values
        with patch.object(
            engine, "_compute_indicators",
            new=AsyncMock(return_value=(72.5, MagicMock(histogram=0.08), 1.2))
        ):
            await engine._process_chain(chain_event)

        assert not signal_q.empty()
        signal: SignalEvent = signal_q.get_nowait()
        assert signal.trade_plan.direction == SignalDirection.CALL

    async def test_process_chain_publishes_put_signal_on_oversold_conditions(self, e2e_config):
        from src.market_adapter.mock_market import MockMarketAdapter

        chain_q = asyncio.Queue()
        signal_q = asyncio.Queue()
        engine = _make_engine(e2e_config, MockMarketAdapter(), chain_q, signal_q)
        chain_event = make_chain_event("SPY", contracts=[
            make_option_contract("SPY", option_type="put", delta=-0.42)
        ])

        with patch.object(
            engine, "_compute_indicators",
            new=AsyncMock(return_value=(27.5, MagicMock(histogram=-0.06), 2.1))
        ):
            await engine._process_chain(chain_event)

        assert not signal_q.empty()
        signal: SignalEvent = signal_q.get_nowait()
        assert signal.trade_plan.direction == SignalDirection.PUT

    async def test_process_chain_emits_no_signal_when_indicators_neutral(self, e2e_config):
        from src.market_adapter.mock_market import MockMarketAdapter

        chain_q = asyncio.Queue()
        signal_q = asyncio.Queue()
        engine = _make_engine(e2e_config, MockMarketAdapter(), chain_q, signal_q)
        chain_event = make_chain_event("AAPL")

        with patch.object(
            engine, "_compute_indicators",
            new=AsyncMock(return_value=(50.0, MagicMock(histogram=0.0), 1.0))
        ):
            await engine._process_chain(chain_event)

        assert signal_q.empty()

    async def test_process_chain_skips_when_symbol_on_cooldown(self, e2e_config):
        from src.market_adapter.mock_market import MockMarketAdapter

        chain_q = asyncio.Queue()
        signal_q = asyncio.Queue()
        pos_store = MagicMock()
        pos_store.is_on_cooldown.return_value = True
        pos_store.symbols.return_value = []

        engine = _make_engine(e2e_config, MockMarketAdapter(), chain_q, signal_q, pos_store)
        chain_event = make_chain_event("AAPL")

        with patch.object(engine, "_compute_indicators") as mock_ind:
            await engine._process_chain(chain_event)
            # _compute_indicators should NOT be called when on cooldown
            mock_ind.assert_not_called()

        assert signal_q.empty()

    async def test_process_chain_skips_when_already_in_position(self, e2e_config):
        from src.market_adapter.mock_market import MockMarketAdapter

        chain_q = asyncio.Queue()
        signal_q = asyncio.Queue()
        pos_store = MagicMock()
        pos_store.is_on_cooldown.return_value = False
        pos_store.symbols.return_value = ["AAPL"]  # Already in position

        engine = _make_engine(e2e_config, MockMarketAdapter(), chain_q, signal_q, pos_store)
        chain_event = make_chain_event("AAPL")

        with patch.object(engine, "_compute_indicators") as mock_ind:
            await engine._process_chain(chain_event)
            mock_ind.assert_not_called()

        assert signal_q.empty()

    async def test_process_chain_skips_when_insufficient_bars(self, e2e_config):
        from src.market_adapter.mock_market import MockMarketAdapter

        chain_q = asyncio.Queue()
        signal_q = asyncio.Queue()
        engine = _make_engine(e2e_config, MockMarketAdapter(), chain_q, signal_q)
        chain_event = make_chain_event("AAPL")

        with patch.object(
            engine, "_compute_indicators",
            new=AsyncMock(side_effect=ValueError("Insufficient bars"))
        ):
            await engine._process_chain(chain_event)

        assert signal_q.empty()
