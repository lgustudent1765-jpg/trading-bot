# file: tests/e2e/risk_manager.spec.py
"""
E2E tests for RiskManager.

The existing unit tests in tests/test_execution.py cover basic approve() scenarios.
This spec adds coverage for:
  - check_pdt(): returns True when equity >= threshold
  - check_pdt(): returns True (with warning) when equity < threshold but trades remain
  - check_pdt(): returns False when equity < threshold AND day_trades_used >= 3
  - register_open() increments open_position_count
  - register_close() decrements open_position_count
  - register_close() is idempotent (removing non-existent symbol does not raise)
  - open_position_count is accurate after mixed register_open/close calls
  - approve() rejects when max open positions already reached
  - approve() rejects when contract_cost is zero or negative
  - approve() rejects when position_size < 1 (equity too small)
  - approve() correctly sizes position: floor(equity * pct / (entry * 100))
  - approve() rejects CALL plan with inverted stop/target (stop > entry)
  - approve() rejects PUT plan with inverted stop/target (target > entry)
  - approve() accepts valid PUT plan (target < entry < stop)
  - Approving multiple plans up to max_open_positions all succeed
  - The (max_open_positions + 1)th approval fails
"""

from __future__ import annotations

import pytest

from src.events import SignalDirection, TradePlan
from src.risk_manager import RiskManager
from tests.e2e.test_helpers import make_option_contract, make_trade_plan

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _rm(
    max_open=5,
    max_pos_pct=0.05,
    pdt_threshold=25_000,
    sl_mult=1.5,
    tp_mult=3.0,
) -> RiskManager:
    return RiskManager({
        "risk": {
            "max_position_pct": max_pos_pct,
            "max_open_positions": max_open,
            "pdt_equity_threshold": pdt_threshold,
            "stop_loss_atr_mult": sl_mult,
            "take_profit_atr_mult": tp_mult,
        }
    })


def _call_plan(entry=2.50, stop=1.80, target=4.20) -> TradePlan:
    return make_trade_plan(
        symbol="AAPL",
        direction=SignalDirection.CALL,
        entry_limit=entry,
        stop_loss=stop,
        take_profit=target,
    )


def _put_plan(entry=3.00, stop=4.50, target=1.50) -> TradePlan:
    return make_trade_plan(
        symbol="SPY",
        direction=SignalDirection.PUT,
        entry_limit=entry,
        stop_loss=stop,   # for PUT: stop > entry is correct
        take_profit=target,  # for PUT: target < entry is correct
    )


# ---------------------------------------------------------------------------
# PDT rule
# ---------------------------------------------------------------------------

class TestCheckPdt:
    def test_equity_above_threshold_always_returns_true(self):
        rm = _rm(pdt_threshold=25_000)
        assert rm.check_pdt(equity=100_000) is True

    def test_equity_exactly_at_threshold_returns_true(self):
        rm = _rm(pdt_threshold=25_000)
        assert rm.check_pdt(equity=25_000) is True

    def test_equity_below_threshold_with_trades_remaining_returns_true(self):
        """Below PDT threshold but still has day-trades available → allowed with warning."""
        rm = _rm(pdt_threshold=25_000)
        # day_trades_used=1 means 2 remaining: allowed
        result = rm.check_pdt(equity=20_000, day_trades_used=1)
        assert result is True

    def test_equity_below_threshold_no_trades_remaining_returns_false(self):
        """Below PDT threshold and all 3 day-trades used → blocked."""
        rm = _rm(pdt_threshold=25_000)
        result = rm.check_pdt(equity=20_000, day_trades_used=3)
        assert result is False

    def test_equity_below_threshold_two_trades_used_returns_true(self):
        """2 trades used → 1 remaining → still allowed."""
        rm = _rm(pdt_threshold=25_000)
        result = rm.check_pdt(equity=10_000, day_trades_used=2)
        assert result is True

    def test_equity_zero_with_no_day_trades_returns_false(self):
        rm = _rm(pdt_threshold=25_000)
        assert rm.check_pdt(equity=0, day_trades_used=3) is False


# ---------------------------------------------------------------------------
# Open position tracking
# ---------------------------------------------------------------------------

class TestPositionTracking:
    def test_initial_open_count_is_zero(self):
        rm = _rm()
        assert rm.open_position_count == 0

    def test_register_open_increments_count(self):
        rm = _rm()
        rm.register_open("AAPL_CALL_175_2026-05-16")
        assert rm.open_position_count == 1

    def test_register_open_multiple_increments_correctly(self):
        rm = _rm()
        rm.register_open("AAPL_CALL_175_2026-05-16")
        rm.register_open("SPY_PUT_520_2026-04-18")
        assert rm.open_position_count == 2

    def test_register_close_decrements_count(self):
        rm = _rm()
        opt_sym = "AAPL_CALL_175_2026-05-16"
        rm.register_open(opt_sym)
        rm.register_close(opt_sym)
        assert rm.open_position_count == 0

    def test_register_close_nonexistent_symbol_does_not_raise(self):
        rm = _rm()
        rm.register_close("NONEXISTENT_SYMBOL")  # Must not raise

    def test_register_close_only_removes_one_occurrence(self):
        rm = _rm()
        rm.register_open("SYM_A")
        rm.register_open("SYM_B")
        rm.register_close("SYM_A")
        assert rm.open_position_count == 1

    def test_open_count_accurate_after_mixed_operations(self):
        rm = _rm(max_open=10)
        syms = [f"SYM_{i}" for i in range(5)]
        for s in syms:
            rm.register_open(s)
        rm.register_close("SYM_0")
        rm.register_close("SYM_2")
        assert rm.open_position_count == 3


# ---------------------------------------------------------------------------
# approve() — CALL direction
# ---------------------------------------------------------------------------

class TestApproveCall:
    def test_valid_call_plan_is_approved(self):
        rm = _rm()
        plan = _call_plan(entry=2.50, stop=1.80, target=4.20)
        assert rm.approve(plan, equity=100_000)[0] is True

    def test_valid_call_sets_position_size(self):
        """position_size = floor(equity * max_pos_pct / (entry * 100))."""
        rm = _rm(max_pos_pct=0.05)
        plan = _call_plan(entry=2.50)
        rm.approve(plan, equity=100_000)
        expected = int((100_000 * 0.05) // (2.50 * 100))
        assert plan.position_size == expected

    def test_call_inverted_sl_above_entry_rejected(self):
        """CALL: stop must be < entry. Inverted stop (stop > entry) → rejected."""
        rm = _rm()
        plan = _call_plan(entry=2.50, stop=3.50, target=4.20)  # stop > entry: invalid
        assert rm.approve(plan, equity=100_000)[0] is False

    def test_call_inverted_target_below_entry_rejected(self):
        """CALL: target must be > entry. Inverted target → rejected."""
        rm = _rm()
        plan = _call_plan(entry=2.50, stop=1.80, target=1.50)  # target < entry: invalid
        assert rm.approve(plan, equity=100_000)[0] is False

    def test_max_positions_reached_call_rejected(self):
        rm = _rm(max_open=2)
        rm.register_open("SYM_A")
        rm.register_open("SYM_B")
        plan = _call_plan()
        assert rm.approve(plan, equity=100_000)[0] is False

    def test_insufficient_equity_for_minimum_size_rejected(self):
        """When equity is too small to buy even one contract, reject."""
        rm = _rm(max_pos_pct=0.001)  # 0.1% of $100 = $0.10 — far too small
        plan = _call_plan(entry=50.0)  # one contract costs $5000
        assert rm.approve(plan, equity=100)[0] is False

    def test_zero_entry_price_rejected(self):
        """entry_limit=0 means contract_cost=0 → rejected."""
        rm = _rm()
        plan = _call_plan(entry=0.0, stop=0.0, target=0.0)
        assert rm.approve(plan, equity=100_000)[0] is False


# ---------------------------------------------------------------------------
# approve() — PUT direction
# ---------------------------------------------------------------------------

class TestApprovePut:
    def test_valid_put_plan_is_approved(self):
        """For PUT: target < entry < stop is the correct relationship."""
        rm = _rm()
        plan = _put_plan(entry=3.00, stop=4.50, target=1.50)
        assert rm.approve(plan, equity=100_000)[0] is True

    def test_valid_put_sets_position_size(self):
        rm = _rm(max_pos_pct=0.05)
        plan = _put_plan(entry=3.00, stop=4.50, target=1.50)
        rm.approve(plan, equity=100_000)
        expected = int((100_000 * 0.05) // (3.00 * 100))
        assert plan.position_size == expected

    def test_put_inverted_stop_below_entry_rejected(self):
        """PUT: stop must be > entry. Inverted stop (stop < entry) → rejected."""
        rm = _rm()
        plan = _put_plan(entry=3.00, stop=2.00, target=1.50)  # stop < entry: invalid
        assert rm.approve(plan, equity=100_000)[0] is False

    def test_put_inverted_target_above_entry_rejected(self):
        """PUT: target must be < entry. Inverted target (target > entry) → rejected."""
        rm = _rm()
        plan = _put_plan(entry=3.00, stop=4.50, target=4.00)  # target > entry: invalid
        assert rm.approve(plan, equity=100_000)[0] is False


# ---------------------------------------------------------------------------
# approve() — capacity limits
# ---------------------------------------------------------------------------

class TestApproveCapacity:
    def test_fills_all_positions_up_to_max(self):
        """Approving max_open_positions plans in sequence all succeed."""
        max_open = 3
        rm = _rm(max_open=max_open)
        for i in range(max_open):
            plan = _call_plan(entry=2.50)
            approved, _ = rm.approve(plan, equity=100_000)
            assert approved is True, f"Plan {i} should be approved"
            rm.register_open(f"SYM_{i}")

    def test_exceeding_max_positions_is_rejected(self):
        """The (max+1)th approval is rejected when all slots are occupied."""
        max_open = 3
        rm = _rm(max_open=max_open)
        for i in range(max_open):
            rm.register_open(f"SYM_{i}")

        plan = _call_plan()
        assert rm.approve(plan, equity=100_000)[0] is False

    def test_after_close_capacity_is_freed(self):
        """After closing a position, the slot is freed and a new plan is approved."""
        rm = _rm(max_open=1)
        rm.register_open("SYM_A")
        assert rm.approve(_call_plan(), equity=100_000)[0] is False  # full

        rm.register_close("SYM_A")
        assert rm.approve(_call_plan(), equity=100_000)[0] is True   # slot freed
