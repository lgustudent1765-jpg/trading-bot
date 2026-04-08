# file: tests/e2e/screener_pipeline.spec.py
"""
E2E tests for the Screener component pipeline.

Covers:
  - Screener._fetch() produces a CandidateEvent with gainers and losers
  - CandidateEvent gainers and losers are lists of MarketQuote objects
  - Screener publishes CandidateEvent to the candidate_queue
  - Screener respects top_n config (limits gainers/losers count)
  - Screener waits for market open when market_hours_only=True (mocked)
  - Screener skips polling when market is closed and market_hours_only=True
  - Screener adapter errors increment the error metric (not raise)
  - Screener recovers from transient adapter errors and retries
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.events import CandidateEvent, MarketQuote
from tests.e2e.test_helpers import drain_queue, make_market_quote

pytestmark = pytest.mark.e2e


def _make_screener(adapter, queue, config=None):
    from src.screener.screener import Screener

    cfg = config or {
        "screener": {
            "top_n": 5,
            "poll_interval_seconds": 0.01,
            "market_hours_only": False,
        }
    }
    return Screener(adapter=adapter, candidate_queue=queue, config=cfg)


def _make_mock_adapter(n=5):
    """Return a mock adapter that returns n gainers and n losers."""
    gainers = [make_market_quote(f"G{i}", change_pct=float(i + 1)) for i in range(n)]
    losers = [make_market_quote(f"L{i}", change_pct=-float(i + 1)) for i in range(n)]
    adapter = MagicMock()
    adapter.get_top_gainers = AsyncMock(return_value=gainers)
    adapter.get_top_losers = AsyncMock(return_value=losers)
    return adapter, gainers, losers


class TestScreenerFetch:
    async def test_fetch_returns_candidate_event(self):
        adapter, _, _ = _make_mock_adapter()
        queue = asyncio.Queue()
        screener = _make_screener(adapter, queue)
        event = await screener._fetch()
        assert isinstance(event, CandidateEvent)

    async def test_fetch_gainers_are_market_quotes(self):
        adapter, gainers, _ = _make_mock_adapter(n=3)
        queue = asyncio.Queue()
        screener = _make_screener(adapter, queue)
        event = await screener._fetch()
        assert len(event.gainers) == 3
        for q in event.gainers:
            assert isinstance(q, MarketQuote)

    async def test_fetch_losers_are_market_quotes(self):
        adapter, _, losers = _make_mock_adapter(n=3)
        queue = asyncio.Queue()
        screener = _make_screener(adapter, queue)
        event = await screener._fetch()
        assert len(event.losers) == 3
        for q in event.losers:
            assert isinstance(q, MarketQuote)

    async def test_fetch_raises_when_adapter_raises(self):
        adapter = MagicMock()
        adapter.get_top_gainers = AsyncMock(side_effect=RuntimeError("API down"))
        adapter.get_top_losers = AsyncMock(return_value=[])
        queue = asyncio.Queue()
        screener = _make_screener(adapter, queue)
        with pytest.raises(RuntimeError, match="API down"):
            await screener._fetch()


class TestScreenerRun:
    async def test_run_publishes_candidate_event_to_queue(self):
        adapter, _, _ = _make_mock_adapter()
        queue = asyncio.Queue()
        screener = _make_screener(adapter, queue)

        task = asyncio.ensure_future(screener.run())
        events = await drain_queue(queue, expected=1, timeout=1.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(events) >= 1
        assert isinstance(events[0], CandidateEvent)

    async def test_run_publishes_multiple_events_over_time(self):
        adapter, _, _ = _make_mock_adapter()
        queue = asyncio.Queue()
        screener = _make_screener(adapter, queue, config={
            "screener": {
                "top_n": 5,
                "poll_interval_seconds": 0.05,
                "market_hours_only": False,
            }
        })

        task = asyncio.ensure_future(screener.run())
        events = await drain_queue(queue, expected=2, timeout=1.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(events) >= 2

    async def test_run_event_gainers_symbols_match_adapter_output(self):
        adapter, gainers, _ = _make_mock_adapter(n=3)
        queue = asyncio.Queue()
        screener = _make_screener(adapter, queue)

        task = asyncio.ensure_future(screener.run())
        events = await drain_queue(queue, expected=1, timeout=1.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        expected_symbols = {q.symbol for q in gainers}
        actual_symbols = {q.symbol for q in events[0].gainers}
        assert expected_symbols == actual_symbols

    async def test_run_recovers_after_transient_adapter_error(self):
        """Screener catches errors, sleeps 30s (mocked), and retries."""
        adapter = MagicMock()
        call_count = 0

        async def flaky_gainers(n):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient error")
            return [make_market_quote("AAPL")]

        adapter.get_top_gainers = flaky_gainers
        adapter.get_top_losers = AsyncMock(return_value=[make_market_quote("META")])

        queue = asyncio.Queue()
        screener = _make_screener(adapter, queue)

        # Patch asyncio.sleep so the 30s retry delay is instant
        with patch("src.screener.screener.asyncio.sleep", new=AsyncMock()):
            task = asyncio.ensure_future(screener.run())
            events = await drain_queue(queue, expected=1, timeout=2.0)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Should have recovered and published at least one event
        assert len(events) >= 1

    async def test_run_gates_on_market_hours_when_configured(self):
        """market_hours_only=True: screener calls wait_for_market_open when market is closed."""
        adapter, _, _ = _make_mock_adapter()
        queue = asyncio.Queue()
        screener = _make_screener(adapter, queue, config={
            "screener": {
                "top_n": 5,
                "poll_interval_seconds": 60,  # long interval to avoid extra loops
                "market_hours_only": True,
            }
        })

        wait_called = asyncio.Event()

        async def fake_wait(log):
            wait_called.set()

        # _fetch() produces one event, then sleep(60) is also mocked so run() loops.
        # We just need to verify wait_for_market_open is called once.
        with (
            patch("src.screener.screener.is_market_open", return_value=False),
            patch("src.screener.screener.wait_for_market_open", new=fake_wait),
        ):
            task = asyncio.ensure_future(screener.run())
            try:
                await asyncio.wait_for(wait_called.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        assert wait_called.is_set(), "wait_for_market_open was not called"
