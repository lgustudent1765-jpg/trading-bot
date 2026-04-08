# file: tests/e2e/signal_store.spec.py
# SKIPPED: src.signal_store (SignalStore) was removed from the codebase.
# The server now uses a plain list. These tests are preserved for reference
# and should be re-enabled if SignalStore is re-introduced.
"""
E2E tests for SignalStore (SQLite persistence layer)

Covers:
  - Empty store has len == 0 and bool == False
  - append() stores a signal; len increments
  - recent() returns signals oldest-first
  - recent(limit=N) returns at most N signals
  - query(symbol=...) filters by symbol
  - query(direction=...) filters by direction
  - query(symbol=..., direction=...) applies both filters
  - bool(store) is True when store has at least one signal
  - Iteration yields all signals
  - close() does not raise
  - Signals survive multiple append/recent cycles
"""

from __future__ import annotations

import pytest

from tests.e2e.test_helpers import make_signal_dict

pytestmark = [pytest.mark.e2e, pytest.mark.skip(reason="src.signal_store.SignalStore removed; server now uses plain list")]


class TestSignalStoreEmpty:
    def test_empty_store_len_is_zero(self, signal_store):
        assert len(signal_store) == 0

    def test_empty_store_bool_is_false(self, signal_store):
        assert not signal_store

    def test_empty_store_recent_returns_empty_list(self, signal_store):
        assert signal_store.recent() == []

    def test_empty_store_iteration_yields_nothing(self, signal_store):
        assert list(signal_store) == []


class TestSignalStoreAppend:
    def test_append_increments_len(self, signal_store):
        signal_store.append(make_signal_dict("AAPL"))
        assert len(signal_store) == 1

    def test_append_multiple_signals_increments_correctly(self, signal_store):
        for i in range(5):
            signal_store.append(make_signal_dict(f"SYM{i}"))
        assert len(signal_store) == 5

    def test_append_makes_bool_true(self, signal_store):
        signal_store.append(make_signal_dict("AAPL"))
        assert bool(signal_store)

    def test_appended_signal_is_retrievable_via_recent(self, signal_store):
        signal_store.append(make_signal_dict("NVDA", "CALL"))
        results = signal_store.recent()
        assert any(s["symbol"] == "NVDA" for s in results)

    def test_appended_signal_preserves_all_fields(self, signal_store):
        sig = make_signal_dict("MSFT", "CALL", rsi=73.5)
        signal_store.append(sig)
        results = signal_store.recent()
        stored = results[0]
        assert stored["symbol"] == "MSFT"
        assert stored["direction"] == "CALL"
        assert stored["rsi"] == pytest.approx(73.5)


class TestSignalStoreRecent:
    def test_recent_returns_oldest_first(self, signal_store):
        signal_store.append(make_signal_dict("FIRST"))
        signal_store.append(make_signal_dict("SECOND"))
        signal_store.append(make_signal_dict("THIRD"))
        results = signal_store.recent()
        symbols = [s["symbol"] for s in results]
        assert symbols == ["FIRST", "SECOND", "THIRD"]

    def test_recent_limit_one_returns_most_recent(self, signal_store):
        signal_store.append(make_signal_dict("FIRST"))
        signal_store.append(make_signal_dict("SECOND"))
        results = signal_store.recent(limit=1)
        assert len(results) == 1
        assert results[0]["symbol"] == "SECOND"

    def test_recent_limit_larger_than_count_returns_all(self, signal_store):
        for i in range(3):
            signal_store.append(make_signal_dict(f"SYM{i}"))
        results = signal_store.recent(limit=100)
        assert len(results) == 3


class TestSignalStoreQuery:
    def test_query_by_symbol_returns_only_matching(self, signal_store):
        signal_store.append(make_signal_dict("AAPL"))
        signal_store.append(make_signal_dict("AAPL"))
        signal_store.append(make_signal_dict("SPY"))
        results = signal_store.query(symbol="AAPL")
        assert len(results) == 2
        assert all(s["symbol"] == "AAPL" for s in results)

    def test_query_by_direction_call_returns_only_calls(self, signal_store):
        signal_store.append(make_signal_dict("AAPL", "CALL"))
        signal_store.append(make_signal_dict("AAPL", "CALL"))
        signal_store.append(make_signal_dict("SPY", "PUT"))
        results = signal_store.query(direction="CALL")
        assert len(results) == 2
        assert all(s["direction"] == "CALL" for s in results)

    def test_query_by_direction_put_returns_only_puts(self, signal_store):
        signal_store.append(make_signal_dict("AAPL", "CALL"))
        signal_store.append(make_signal_dict("SPY", "PUT"))
        signal_store.append(make_signal_dict("QQQ", "PUT"))
        results = signal_store.query(direction="PUT")
        assert len(results) == 2
        assert all(s["direction"] == "PUT" for s in results)

    def test_query_by_symbol_and_direction(self, signal_store):
        signal_store.append(make_signal_dict("AAPL", "CALL"))
        signal_store.append(make_signal_dict("AAPL", "PUT"))
        signal_store.append(make_signal_dict("SPY", "CALL"))
        results = signal_store.query(symbol="AAPL", direction="CALL")
        assert len(results) == 1
        assert results[0]["symbol"] == "AAPL"
        assert results[0]["direction"] == "CALL"

    def test_query_nonexistent_symbol_returns_empty_list(self, signal_store):
        signal_store.append(make_signal_dict("AAPL"))
        results = signal_store.query(symbol="NONEXISTENT")
        assert results == []

    def test_query_direction_is_case_insensitive(self, signal_store):
        signal_store.append(make_signal_dict("AAPL", "CALL"))
        # The store normalizes to uppercase via direction.upper() in query()
        results = signal_store.query(direction="call")
        assert len(results) == 1


class TestSignalStoreIteration:
    def test_iteration_yields_all_signals(self, signal_store):
        for i in range(4):
            signal_store.append(make_signal_dict(f"SYM{i}"))
        items = list(signal_store)
        assert len(items) == 4

    def test_close_does_not_raise(self, signal_store):
        signal_store.close()  # Must not raise
