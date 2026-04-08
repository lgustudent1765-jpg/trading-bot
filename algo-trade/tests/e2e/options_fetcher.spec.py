# file: tests/e2e/options_fetcher.spec.py
"""
E2E tests for the OptionsFetcher pipeline component.

OptionsFetcher.run() consumes CandidateEvents from candidate_queue,
calls broker.get_option_chain() for each symbol concurrently,
applies the liquidity filter, and publishes OptionChainEvents to chain_queue.

Covers:
  - A CandidateEvent with gainers → OptionChainEvents appear in chain_queue
  - A CandidateEvent with losers → their symbols are also processed
  - All gainers + losers are processed concurrently (multiple chain events)
  - Contracts that fail the liquidity filter are excluded from chain events
  - No chain event is emitted when every contract is filtered out
  - Broker exception per symbol is swallowed; other symbols still proceed
  - OptionChainEvent.symbol matches the queried symbol
  - OptionChainEvent.contracts contains only liquid contracts
  - run() exits cleanly on asyncio.CancelledError
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.events import CandidateEvent, MarketQuote, OptionChainEvent, OptionContract
from src.options_fetcher.fetcher import OptionsFetcher
from tests.e2e.test_helpers import drain_queue, make_market_quote

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_liquid_contract(
    symbol: str = "AAPL",
    option_type: str = "call",
    strike: float = 175.0,
    underlying_price: float = 174.50,
    dte: int = 14,
) -> OptionContract:
    """Return a contract that passes all default liquidity checks."""
    expiry = (date.today() + timedelta(days=dte)).isoformat()
    return OptionContract(
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        option_type=option_type,
        bid=2.40,
        ask=2.50,
        volume=5000,
        open_interest=20000,
        implied_volatility=0.32,
        delta=0.48,
        underlying_price=underlying_price,
    )


def _make_illiquid_contract(symbol: str = "AAPL") -> OptionContract:
    """Return a contract that fails the volume liquidity check."""
    expiry = (date.today() + timedelta(days=14)).isoformat()
    return OptionContract(
        symbol=symbol,
        expiry=expiry,
        strike=175.0,
        option_type="call",
        bid=2.40,
        ask=2.50,
        volume=5,           # below min_volume=100
        open_interest=20000,
        implied_volatility=0.32,
        underlying_price=174.50,
    )


def _make_broker(contracts_by_symbol: dict) -> MagicMock:
    """Return a mock broker whose get_option_chain returns per-symbol contracts."""
    broker = MagicMock()

    async def _get_chain(symbol, underlying_price=None):
        return contracts_by_symbol.get(symbol, [])

    broker.get_option_chain = _get_chain
    return broker


def _make_fetcher(broker, candidate_q, chain_q, config=None):
    cfg = config or {
        "options_filter": {
            "min_volume": 100,
            "min_open_interest": 500,
            "max_spread_pct": 0.10,
            "max_dte": 30,
            "min_dte": 1,
            "max_otm_pct": 0.15,
        }
    }
    return OptionsFetcher(broker, candidate_q, chain_q, cfg)


def _candidate_event(*symbols, price=174.50, as_gainers=True):
    quotes = [make_market_quote(sym, price=price, change_pct=3.5) for sym in symbols]
    if as_gainers:
        return CandidateEvent(gainers=quotes, losers=[])
    return CandidateEvent(gainers=[], losers=quotes)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOptionsFetcherSingleSymbol:
    async def test_liquid_gainer_produces_chain_event(self):
        """A single gainer with liquid contracts → one OptionChainEvent emitted."""
        contract = _make_liquid_contract("AAPL", underlying_price=174.50)
        broker = _make_broker({"AAPL": [contract]})
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        await candidate_q.put(_candidate_event("AAPL"))

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=1, timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(events) == 1
        assert events[0].symbol == "AAPL"

    async def test_chain_event_symbol_matches_queried_symbol(self):
        contract = _make_liquid_contract("SPY", underlying_price=520.0, strike=520.0)
        broker = _make_broker({"SPY": [contract]})
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        await candidate_q.put(_candidate_event("SPY", price=520.0))

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=1, timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert events[0].symbol == "SPY"

    async def test_chain_event_contracts_are_liquid(self):
        """Contracts in the emitted event must have passed the liquidity filter."""
        liquid = _make_liquid_contract("AAPL")
        broker = _make_broker({"AAPL": [liquid]})
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        await candidate_q.put(_candidate_event("AAPL"))

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=1, timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(events[0].contracts) >= 1
        for c in events[0].contracts:
            assert c.volume >= 100  # passed min_volume


class TestOptionsFetcherFiltering:
    async def test_all_illiquid_contracts_produces_no_chain_event(self):
        """When every contract fails liquidity checks, no OptionChainEvent is emitted."""
        illiquid = _make_illiquid_contract("AAPL")
        broker = _make_broker({"AAPL": [illiquid]})
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        await candidate_q.put(_candidate_event("AAPL"))

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=1, timeout=0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(events) == 0

    async def test_mixed_chain_only_liquid_contracts_in_event(self):
        """When a chain has liquid + illiquid contracts, only liquid ones appear."""
        liquid = _make_liquid_contract("AAPL", option_type="call")
        illiquid = _make_illiquid_contract("AAPL")
        broker = _make_broker({"AAPL": [liquid, illiquid]})
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        await candidate_q.put(_candidate_event("AAPL"))

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=1, timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(events) == 1
        assert len(events[0].contracts) == 1
        assert events[0].contracts[0].volume == liquid.volume

    async def test_empty_broker_response_produces_no_chain_event(self):
        """When broker returns an empty list, no event is emitted."""
        broker = _make_broker({"AAPL": []})
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        await candidate_q.put(_candidate_event("AAPL"))

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=1, timeout=0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(events) == 0


class TestOptionsFetcherMultipleSymbols:
    async def test_gainers_and_losers_both_processed(self):
        """Both gainers and losers in a CandidateEvent are processed."""
        gainer_contract = _make_liquid_contract("AAPL", strike=175.0, underlying_price=174.50)
        loser_contract = _make_liquid_contract("SPY", option_type="put", strike=520.0, underlying_price=521.0)
        broker = _make_broker({"AAPL": [gainer_contract], "SPY": [loser_contract]})
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        event = CandidateEvent(
            gainers=[make_market_quote("AAPL", price=174.50, change_pct=4.2)],
            losers=[make_market_quote("SPY", price=521.0, change_pct=-2.1)],
        )
        await candidate_q.put(event)

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=2, timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        symbols = {e.symbol for e in events}
        assert "AAPL" in symbols
        assert "SPY" in symbols

    async def test_three_gainers_produce_three_chain_events(self):
        """Each gainer symbol with liquid contracts results in one OptionChainEvent."""
        symbols = ["AAPL", "TSLA", "NVDA"]
        contracts = {
            s: [_make_liquid_contract(s, strike=175.0, underlying_price=174.0)]
            for s in symbols
        }
        broker = _make_broker(contracts)
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        await candidate_q.put(_candidate_event(*symbols, price=174.0))

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=3, timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(events) == 3
        assert {e.symbol for e in events} == set(symbols)


class TestOptionsFetcherErrorHandling:
    async def test_broker_exception_for_one_symbol_does_not_block_others(self):
        """When broker raises for one symbol, other symbols still get processed."""
        good_contract = _make_liquid_contract("TSLA", strike=260.0, underlying_price=258.70)
        error_symbol = "FAIL_ME"

        failing_broker = MagicMock()

        async def _get_chain(symbol, underlying_price=None):
            if symbol == error_symbol:
                raise RuntimeError("broker API timeout")
            return [good_contract]

        failing_broker.get_option_chain = _get_chain

        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(failing_broker, candidate_q, chain_q)

        event = CandidateEvent(
            gainers=[
                make_market_quote("TSLA", price=258.70, change_pct=3.1),
                make_market_quote(error_symbol, price=100.0, change_pct=5.0),
            ],
            losers=[],
        )
        await candidate_q.put(event)

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=1, timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # TSLA should have produced an event; the failing symbol should not
        assert any(e.symbol == "TSLA" for e in events)
        assert not any(e.symbol == error_symbol for e in events)

    async def test_run_exits_cleanly_on_cancellation(self):
        """CancelledError propagation should not raise beyond the task boundary."""
        broker = _make_broker({})
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        task = asyncio.ensure_future(fetcher.run())
        await asyncio.sleep(0.05)
        task.cancel()

        # Must not raise anything other than CancelledError
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_multiple_consecutive_candidate_events_all_processed(self):
        """Sending two CandidateEvents in sequence results in two sets of chain events."""
        contract = _make_liquid_contract("AAPL")
        broker = _make_broker({"AAPL": [contract]})
        candidate_q: asyncio.Queue = asyncio.Queue()
        chain_q: asyncio.Queue = asyncio.Queue()
        fetcher = _make_fetcher(broker, candidate_q, chain_q)

        await candidate_q.put(_candidate_event("AAPL"))
        await candidate_q.put(_candidate_event("AAPL"))

        task = asyncio.ensure_future(fetcher.run())
        events = await drain_queue(chain_q, expected=2, timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(events) == 2
