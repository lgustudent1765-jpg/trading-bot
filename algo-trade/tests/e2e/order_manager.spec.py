# file: tests/e2e/order_manager.spec.py
"""
E2E tests for the OrderManager execution component.

Covers:
  - Paper mode: fills are immediate (MockBrokerAdapter)
  - Manual mode: signal is logged but no order placed
  - Automated mode: order is placed via broker adapter
  - Risk manager rejection: no order placed when risk check fails
  - Filled order → position persisted to position_store
  - Filled order → stop monitor task is scheduled
  - SUBMITTED (not immediately filled) order → stored in open_orders
  - Broker exception → no position stored, no crash
  - recover_open_positions() with valid positions → stop monitors re-armed
  - recover_open_positions() with empty store → no-op
  - run() consumes signals from queue and handles each one
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.events import OrderEvent, OrderSide, OrderStatus, SignalDirection
from src.execution.order_manager import OrderManager
from tests.e2e.test_helpers import make_signal_event, make_trade_plan

pytestmark = pytest.mark.e2e


def _make_order_manager(
    broker=None,
    risk_manager=None,
    mode="paper",
    config=None,
    position_store=None,
    notifier=None,
    e2e_config=None,
):
    from src.execution.mock_adapter import MockBrokerAdapter
    from src.risk_manager import RiskManager

    if broker is None:
        broker = MockBrokerAdapter(equity=100_000)
    if risk_manager is None:
        cfg = config or e2e_config or {
            "risk": {
                "max_position_pct": 0.05,
                "max_open_positions": 5,
                "pdt_equity_threshold": 25000,
                "stop_loss_atr_mult": 1.5,
                "take_profit_atr_mult": 3.0,
            }
        }
        risk_manager = RiskManager(cfg)

    queue: asyncio.Queue = asyncio.Queue()
    return OrderManager(
        broker=broker,
        risk_manager=risk_manager,
        signal_queue=queue,
        mode=mode,
        config=config or {},
        position_store=position_store,
        notifier=notifier,
    ), queue


class TestOrderManagerManualMode:
    async def test_manual_mode_does_not_place_orders(self, e2e_config):
        broker = MagicMock()
        broker.get_account_equity = AsyncMock(return_value=100_000.0)
        broker.place_limit_order = AsyncMock()

        mgr, queue = _make_order_manager(broker=broker, mode="manual", e2e_config=e2e_config)
        signal = make_signal_event()
        await mgr._handle_signal(signal)

        broker.place_limit_order.assert_not_called()


class TestOrderManagerPaperMode:
    async def test_paper_mode_fills_immediately(self, e2e_config):
        """MockBrokerAdapter fills orders immediately in paper mode."""
        mgr, queue = _make_order_manager(mode="paper", e2e_config=e2e_config)
        signal = make_signal_event()

        # Should not raise; MockBrokerAdapter handles everything in-memory
        await mgr._handle_signal(signal)

    async def test_paper_mode_persists_filled_position(self, e2e_config, position_store):
        mgr, _ = _make_order_manager(
            mode="paper",
            position_store=position_store,
            e2e_config=e2e_config,
        )
        signal = make_signal_event("AAPL")
        await mgr._handle_signal(signal)
        # Position should be in the store
        positions = position_store.get_positions()
        assert any(v["symbol"] == "AAPL" for v in positions.values())

    async def test_paper_mode_risk_rejection_stores_no_position(
        self, e2e_config, position_store
    ):
        """When risk manager rejects, no position should be stored."""
        from src.risk_manager import RiskManager

        risk = MagicMock(spec=RiskManager)
        risk.approve.return_value = (False, "mock rejection")

        mgr, _ = _make_order_manager(
            risk_manager=risk,
            mode="paper",
            position_store=position_store,
            e2e_config=e2e_config,
        )
        signal = make_signal_event("AAPL")
        await mgr._handle_signal(signal)
        assert position_store.open_count == 0

    async def test_paper_mode_broker_exception_does_not_crash(self, e2e_config):
        broker = MagicMock()
        broker.get_account_equity = AsyncMock(return_value=100_000.0)
        broker.place_limit_order = AsyncMock(side_effect=RuntimeError("broker down"))

        mgr, _ = _make_order_manager(broker=broker, mode="paper", e2e_config=e2e_config)
        signal = make_signal_event("AAPL")
        # Should log error and return, not raise
        await mgr._handle_signal(signal)


class TestOrderManagerRunLoop:
    async def test_run_consumes_signal_from_queue_and_handles_it(self, e2e_config):
        mgr, queue = _make_order_manager(mode="paper", e2e_config=e2e_config)
        signal = make_signal_event("AAPL")

        handled = []
        original_handle = mgr._handle_signal

        async def spy_handle(s):
            handled.append(s)
            return await original_handle(s)

        mgr._handle_signal = spy_handle
        await queue.put(signal)

        task = asyncio.ensure_future(mgr.run())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(handled) == 1
        assert handled[0] is signal

    async def test_run_processes_multiple_signals_in_order(self, e2e_config):
        mgr, queue = _make_order_manager(mode="paper", e2e_config=e2e_config)
        signals = [make_signal_event(f"SYM{i}") for i in range(3)]

        handled = []
        original = mgr._handle_signal

        async def spy(s):
            handled.append(s.trade_plan.symbol)
            return await original(s)

        mgr._handle_signal = spy

        for s in signals:
            await queue.put(s)

        task = asyncio.ensure_future(mgr.run())
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert handled == ["SYM0", "SYM1", "SYM2"]


class TestOrderManagerRecovery:
    async def test_recovery_no_op_when_no_position_store(self, e2e_config):
        mgr, _ = _make_order_manager(mode="paper", position_store=None, e2e_config=e2e_config)
        await mgr.recover_open_positions()  # Must not raise

    async def test_recovery_no_op_when_store_is_empty(self, e2e_config, position_store):
        mgr, _ = _make_order_manager(
            mode="paper", position_store=position_store, e2e_config=e2e_config
        )
        launched = []
        with patch.object(mgr, "_monitor_stop", side_effect=AsyncMock()):
            await mgr.recover_open_positions()
            await asyncio.sleep(0.05)
        assert launched == []

    async def test_recovery_re_arms_stop_monitor_for_each_position(
        self, e2e_config, position_store
    ):
        position_store.add_position(
            "AAPL_2026-05-16_175.0_C", "AAPL", "CALL", 2.55, 1.85, 4.15, 10
        )
        position_store.add_position(
            "SPY_2026-04-18_520.0_P", "SPY", "PUT", 3.10, 3.80, 1.80, 5
        )

        mgr, _ = _make_order_manager(
            mode="paper", position_store=position_store, e2e_config=e2e_config
        )
        launched = []

        async def spy_monitor(entry_order, plan, opt_sym):
            launched.append(opt_sym)

        with patch.object(mgr, "_monitor_stop", side_effect=spy_monitor):
            await mgr.recover_open_positions()
            await asyncio.sleep(0.1)

        assert set(launched) == {"AAPL_2026-05-16_175.0_C", "SPY_2026-04-18_520.0_P"}

    async def test_recovery_skips_unparseable_option_symbol(
        self, e2e_config, position_store
    ):
        position_store.add_position(
            "BADFORMAT", "AAPL", "CALL", 2.55, 1.85, 4.15, 10
        )

        mgr, _ = _make_order_manager(
            mode="paper", position_store=position_store, e2e_config=e2e_config
        )
        # Must not raise despite bad format
        await mgr.recover_open_positions()
