# file: tests/test_execution.py
"""
Integration tests for the execution layer.

Tests the full lifecycle: signal -> risk check -> order placement -> fill -> stop monitor.
Uses MockBrokerAdapter — no network access required.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Dict

import pytest

from src.events import (
    OptionContract,
    OrderStatus,
    SignalDirection,
    SignalEvent,
    TradePlan,
)
from src.execution.mock_adapter import MockBrokerAdapter
from src.execution.order_manager import OrderManager
from src.risk_manager import RiskManager


def _make_config() -> Dict[str, Any]:
    return {
        "risk": {
            "max_position_pct": 0.10,
            "max_open_positions": 5,
            "pdt_equity_threshold": 25000,
            "stop_loss_atr_mult": 1.5,
            "take_profit_atr_mult": 3.0,
        }
    }


def _make_put_signal(entry: float = 2.10, stop: float = 1.05, target: float = 4.20) -> SignalEvent:
    """PUT signal with correct long-option layout: stop < entry < target."""
    expiry = (date.today() + timedelta(days=14)).isoformat()
    contract = OptionContract(
        symbol="AAPL",
        expiry=expiry,
        strike=150.0,
        option_type="put",
        bid=2.00,
        ask=2.10,
        volume=1000,
        open_interest=5000,
        implied_volatility=0.35,
        underlying_price=150.0,
    )
    plan = TradePlan(
        symbol="AAPL",
        direction=SignalDirection.PUT,
        contract=contract,
        entry_limit=entry,
        stop_loss=stop,
        take_profit=target,
        position_size=1,
    )
    return SignalEvent(trade_plan=plan)


def _make_call_signal(entry: float = 2.10, stop: float = 1.50, target: float = 3.50) -> SignalEvent:
    expiry = (date.today() + timedelta(days=14)).isoformat()
    contract = OptionContract(
        symbol="AAPL",
        expiry=expiry,
        strike=150.0,
        option_type="call",
        bid=2.00,
        ask=2.10,
        volume=1000,
        open_interest=5000,
        implied_volatility=0.35,
        underlying_price=150.0,
    )
    plan = TradePlan(
        symbol="AAPL",
        direction=SignalDirection.CALL,
        contract=contract,
        entry_limit=entry,
        stop_loss=stop,
        take_profit=target,
        position_size=1,
    )
    return SignalEvent(trade_plan=plan)


class TestMockBrokerAdapter:
    @pytest.mark.asyncio
    async def test_place_and_fill_order(self):
        broker = MockBrokerAdapter(equity=100_000)
        order = await broker.place_limit_order("AAPL_CALL", "BUY", 2, 2.10)
        assert order.status == OrderStatus.FILLED
        assert order.filled_qty == 2
        assert order.avg_fill_price > 0

    @pytest.mark.asyncio
    async def test_cancel_unfilled_order(self):
        """Cancel a PENDING order directly — should succeed."""
        from src.events import OrderEvent, OrderSide
        import uuid
        broker = MockBrokerAdapter()
        order = OrderEvent(
            order_id=str(uuid.uuid4())[:8],
            symbol="AAPL",
            option_symbol="AAPL_CALL",
            side=OrderSide.BUY,
            quantity=1,
            limit_price=2.10,
        )
        broker._orders[order.order_id] = order
        result = await broker.cancel_order(order.order_id)
        assert result is True
        assert broker._orders[order.order_id].status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_filled_order_fails(self):
        broker = MockBrokerAdapter()
        order = await broker.place_limit_order("AAPL_CALL", "BUY", 1, 2.10)
        result = await broker.cancel_order(order.order_id)
        assert result is False  # cannot cancel a filled order

    @pytest.mark.asyncio
    async def test_get_order_status(self):
        broker = MockBrokerAdapter()
        order = await broker.place_limit_order("AAPL_CALL", "BUY", 1, 2.10)
        status_order = await broker.get_order_status(order.order_id)
        assert status_order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_get_account_equity(self):
        broker = MockBrokerAdapter(equity=50_000.0)
        equity = await broker.get_account_equity()
        assert equity == 50_000.0

    @pytest.mark.asyncio
    async def test_option_chain_returns_contracts(self):
        broker = MockBrokerAdapter()
        contracts = await broker.get_option_chain("AAPL")
        assert len(contracts) > 0
        assert all(isinstance(c, OptionContract) for c in contracts)


class TestRiskManager:
    def test_approves_valid_plan(self):
        config = _make_config()
        rm = RiskManager(config)
        signal = _make_call_signal()
        approved, _ = rm.approve(signal.trade_plan, equity=100_000)
        assert approved is True
        assert signal.trade_plan.position_size >= 1

    def test_rejects_when_max_positions_reached(self):
        config = {
            "risk": {
                "max_position_pct": 0.10,
                "max_open_positions": 1,
                "pdt_equity_threshold": 25000,
                "stop_loss_atr_mult": 1.5,
                "take_profit_atr_mult": 3.0,
            }
        }
        rm = RiskManager(config)
        rm.register_open("AAPL_CALL_1")  # fills the single slot
        signal = _make_call_signal()
        approved, _ = rm.approve(signal.trade_plan, equity=100_000)
        assert approved is False

    def test_rejects_inverted_sl_tp(self):
        config = _make_config()
        rm = RiskManager(config)
        # stop must be < entry < target — invert them intentionally.
        signal = _make_call_signal(entry=2.10, stop=3.50, target=1.50)
        approved, _ = rm.approve(signal.trade_plan, equity=100_000)
        assert approved is False

    def test_approves_valid_put_plan(self):
        """PUT plan with stop < entry < target must be approved (long option layout)."""
        config = _make_config()
        rm = RiskManager(config)
        signal = _make_put_signal(entry=2.10, stop=1.05, target=4.20)
        approved, reason = rm.approve(signal.trade_plan, equity=100_000)
        assert approved is True, f"PUT plan rejected: {reason}"

    def test_rejects_put_with_old_inverted_layout(self):
        """PUT plan with old inverted layout (stop > entry) must be rejected."""
        config = _make_config()
        rm = RiskManager(config)
        # Old buggy layout: stop=3.15 > entry=2.10, tp=0.0 < entry
        signal = _make_put_signal(entry=2.10, stop=3.15, target=0.01)
        approved, _ = rm.approve(signal.trade_plan, equity=100_000)
        assert approved is False

    def test_position_sized_correctly(self):
        """position_size = floor(equity * 10% / (entry * 100))."""
        config = _make_config()
        rm = RiskManager(config)
        signal = _make_call_signal(entry=2.10)
        rm.approve(signal.trade_plan, equity=100_000)
        expected = int((100_000 * 0.10) // (2.10 * 100))
        assert signal.trade_plan.position_size == expected


class TestCheckExitTrigger:
    """Unit tests for the static helper — no I/O needed."""

    def test_stop_hit_returns_stop_loss(self):
        from types import SimpleNamespace
        plan = SimpleNamespace(stop_loss=1.00, take_profit=4.00)
        result = OrderManager._check_exit_trigger(0.99, plan)
        assert result == "STOP_LOSS"

    def test_at_stop_boundary_returns_stop_loss(self):
        from types import SimpleNamespace
        plan = SimpleNamespace(stop_loss=1.00, take_profit=4.00)
        assert OrderManager._check_exit_trigger(1.00, plan) == "STOP_LOSS"

    def test_target_hit_returns_take_profit(self):
        from types import SimpleNamespace
        plan = SimpleNamespace(stop_loss=1.00, take_profit=4.00)
        assert OrderManager._check_exit_trigger(4.00, plan) == "TAKE_PROFIT"

    def test_above_target_returns_take_profit(self):
        from types import SimpleNamespace
        plan = SimpleNamespace(stop_loss=1.00, take_profit=4.00)
        assert OrderManager._check_exit_trigger(5.00, plan) == "TAKE_PROFIT"

    def test_between_stop_and_target_returns_none(self):
        from types import SimpleNamespace
        plan = SimpleNamespace(stop_loss=1.00, take_profit=4.00)
        assert OrderManager._check_exit_trigger(2.50, plan) is None


class TestClosePosition:
    @pytest.mark.asyncio
    async def test_close_position_records_pnl(self):
        """Closing a position calculates exit - entry PnL (long option)."""
        from src.events import OrderEvent, OrderSide
        import uuid

        config = _make_config()
        broker = MockBrokerAdapter(equity=100_000)
        rm = RiskManager(config)
        action_store: list = []
        signal_q: asyncio.Queue = asyncio.Queue()
        mgr = OrderManager(
            broker, rm, signal_q, mode="paper", config=config,
            action_store=action_store,
        )

        expiry = (date.today() + timedelta(days=14)).isoformat()
        entry_order = OrderEvent(
            order_id=str(uuid.uuid4())[:8],
            symbol="AAPL",
            option_symbol="AAPL_{}_150.0_C".format(expiry),
            side=OrderSide.BUY,
            quantity=2,
            limit_price=2.00,
            status=OrderStatus.FILLED,
            filled_qty=2,
            avg_fill_price=2.00,
        )

        from types import SimpleNamespace
        plan = SimpleNamespace(
            symbol="AAPL",
            stop_loss=1.00,
            take_profit=4.00,
            strategy_name="test_strat",
        )

        option_symbol = "AAPL_{}_150.0_C".format(expiry)
        rm.register_open(option_symbol)
        await mgr._close_position(entry_order, plan, option_symbol, "TAKE_PROFIT", mid=4.00)

        assert any(a["event"] == "POSITION_CLOSED" for a in action_store)
        close_action = next(a for a in action_store if a["event"] == "POSITION_CLOSED")
        assert close_action["data"]["reason"] == "TAKE_PROFIT"
        assert close_action["data"]["pnl"] > 0  # profitable exit (long option)


class TestOrderManagerIntegration:
    @pytest.mark.asyncio
    async def test_signal_to_fill_lifecycle_paper_mode(self):
        """Full lifecycle: signal -> risk check -> order place -> fill logged."""
        config = _make_config()
        broker = MockBrokerAdapter(equity=100_000)
        rm = RiskManager(config)
        signal_q: asyncio.Queue = asyncio.Queue()
        mgr = OrderManager(broker, rm, signal_q, mode="paper", config=config)

        signal = _make_call_signal()
        await signal_q.put(signal)

        task = asyncio.ensure_future(mgr.run())
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert rm.open_position_count >= 1

    @pytest.mark.asyncio
    async def test_manual_mode_does_not_place_orders(self):
        """In manual mode, no orders should be placed."""
        config = _make_config()
        broker = MockBrokerAdapter(equity=100_000)
        rm = RiskManager(config)
        signal_q: asyncio.Queue = asyncio.Queue()
        mgr = OrderManager(broker, rm, signal_q, mode="manual", config=config)

        signal = _make_call_signal()
        await signal_q.put(signal)

        task = asyncio.ensure_future(mgr.run())
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(broker._orders) == 0  # no orders placed in manual mode
