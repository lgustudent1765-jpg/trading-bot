# file: tests/e2e/persistence.spec.py
"""
E2E tests for PositionStore and signal cooldown persistence.

Covers:
  - add_position() stores and persists a position to disk
  - get_positions() returns all open positions
  - open_count reflects actual number of positions
  - remove_position() deletes position from store and disk
  - symbols() returns list of underlying ticker symbols
  - Positions survive a fresh store load from the same file (restart simulation)
  - set_cooldown() records the current time for a symbol
  - is_on_cooldown() returns True immediately after set_cooldown()
  - is_on_cooldown() returns False for unregistered symbols
  - is_on_cooldown() returns False after cooldown period elapses
  - Multiple positions can be added and independently removed
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.e2e


def _add(store, opt_sym="AAPL_2026-05-16_175.0_C", symbol="AAPL", direction="CALL"):
    store.add_position(
        option_symbol=opt_sym,
        symbol=symbol,
        direction=direction,
        entry_price=2.55,
        stop_loss=1.85,
        take_profit=4.15,
        quantity=10,
        underlying_price=174.50,
    )


class TestPositionStoreAdd:
    def test_add_position_increments_open_count(self, position_store):
        _add(position_store)
        assert position_store.open_count == 1

    def test_add_position_is_retrievable_via_get_positions(self, position_store):
        _add(position_store, "AAPL_2026-05-16_175.0_C")
        positions = position_store.get_positions()
        assert "AAPL_2026-05-16_175.0_C" in positions

    def test_add_position_stores_correct_symbol(self, position_store):
        _add(position_store)
        pos = position_store.get_positions()["AAPL_2026-05-16_175.0_C"]
        assert pos["symbol"] == "AAPL"

    def test_add_position_stores_correct_direction(self, position_store):
        _add(position_store, symbol="AAPL", direction="CALL")
        pos = position_store.get_positions()["AAPL_2026-05-16_175.0_C"]
        assert pos["direction"] == "CALL"

    def test_add_position_stores_entry_price(self, position_store):
        _add(position_store)
        pos = position_store.get_positions()["AAPL_2026-05-16_175.0_C"]
        assert pos["entry_price"] == pytest.approx(2.55)

    def test_add_multiple_positions_all_accessible(self, position_store):
        _add(position_store, "AAPL_2026-05-16_175.0_C", "AAPL", "CALL")
        _add(position_store, "SPY_2026-04-18_520.0_P", "SPY", "PUT")
        assert position_store.open_count == 2

    def test_add_position_is_persisted_to_disk(self, tmp_path):
        """Simulate a restart by creating two stores pointing at the same SQLite file."""
        import src.persistence as pm

        db_url = f"sqlite:///{tmp_path}/test.db"

        with patch("src.persistence.get_config", return_value={"database": {"url": db_url}}):
            store1 = pm.PositionStore()
            store1.add_position(
                "AAPL_2026-05-16_175.0_C", "AAPL", "CALL", 2.55, 1.85, 4.15, 10
            )

        # Reload from the same file (simulates restart)
        with patch("src.persistence.get_config", return_value={"database": {"url": db_url}}):
            store2 = pm.PositionStore()

        assert "AAPL_2026-05-16_175.0_C" in store2.get_positions()


class TestPositionStoreRemove:
    def test_remove_position_decrements_open_count(self, position_store):
        _add(position_store)
        position_store.remove_position("AAPL_2026-05-16_175.0_C")
        assert position_store.open_count == 0

    def test_remove_position_is_not_in_get_positions(self, position_store):
        _add(position_store)
        position_store.remove_position("AAPL_2026-05-16_175.0_C")
        assert "AAPL_2026-05-16_175.0_C" not in position_store.get_positions()

    def test_remove_nonexistent_position_does_not_raise(self, position_store):
        position_store.remove_position("NONEXISTENT_SYMBOL")  # Must not raise

    def test_remove_one_of_multiple_leaves_rest_intact(self, position_store):
        _add(position_store, "AAPL_2026-05-16_175.0_C", "AAPL", "CALL")
        _add(position_store, "SPY_2026-04-18_520.0_P", "SPY", "PUT")
        position_store.remove_position("AAPL_2026-05-16_175.0_C")
        positions = position_store.get_positions()
        assert "SPY_2026-04-18_520.0_P" in positions
        assert position_store.open_count == 1


class TestPositionStoreSymbols:
    def test_symbols_returns_underlying_tickers(self, position_store):
        _add(position_store, "AAPL_2026-05-16_175.0_C", "AAPL")
        _add(position_store, "SPY_2026-04-18_520.0_P", "SPY")
        syms = position_store.symbols()
        assert "AAPL" in syms
        assert "SPY" in syms

    def test_symbols_empty_when_no_positions(self, position_store):
        assert position_store.symbols() == []


class TestCooldowns:
    def test_is_on_cooldown_false_for_unknown_symbol(self, position_store):
        assert not position_store.is_on_cooldown("AAPL")

    def test_set_cooldown_makes_symbol_on_cooldown(self, position_store):
        position_store.set_cooldown("AAPL")
        assert position_store.is_on_cooldown("AAPL", cooldown_minutes=30)

    def test_is_on_cooldown_false_after_cooldown_expires(self, position_store):
        """With a 0-minute cooldown, the symbol is immediately off-cooldown."""
        position_store.set_cooldown("AAPL")
        # cooldown_minutes=0 means any elapsed time is sufficient to expire
        assert not position_store.is_on_cooldown("AAPL", cooldown_minutes=0)

    def test_set_cooldown_is_persisted_to_disk(self, tmp_path):
        """Simulate a restart — cooldown should survive store reload."""
        import src.persistence as pm

        db_url = f"sqlite:///{tmp_path}/test.db"

        with patch("src.persistence.get_config", return_value={"database": {"url": db_url}}):
            store = pm.PositionStore()
            store.set_cooldown("TSLA")

        # Reload from the same DB (simulates restart)
        with patch("src.persistence.get_config", return_value={"database": {"url": db_url}}):
            store2 = pm.PositionStore()

        assert store2.is_on_cooldown("TSLA", cooldown_minutes=30)
