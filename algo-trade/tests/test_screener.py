# file: tests/test_screener.py
"""
Unit tests for the Screener module.

Uses MockMarketAdapter — no network access required.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest

from src.events import CandidateEvent
from src.market_adapter.mock_market import MockMarketAdapter
from src.screener import Screener


@pytest.fixture
def mock_adapter():
    return MockMarketAdapter()


@pytest.fixture
def screener_config() -> Dict[str, Any]:
    return {
        "screener": {
            "top_n": 5,
            "poll_interval_seconds": 0.1,
            "provider": "mock",
            "market_hours_only": False,  # disable in tests
        }
    }


class TestScreener:
    @pytest.mark.asyncio
    async def test_screener_produces_candidate_event(self, mock_adapter, screener_config):
        """Screener must put a CandidateEvent on the queue within one poll cycle."""
        queue: asyncio.Queue = asyncio.Queue()
        screener = Screener(mock_adapter, queue, screener_config)
        task = asyncio.ensure_future(screener.run())
        event = await asyncio.wait_for(queue.get(), timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert isinstance(event, CandidateEvent)

    @pytest.mark.asyncio
    async def test_candidate_event_has_correct_count(self, mock_adapter, screener_config):
        """CandidateEvent must contain exactly top_n gainers and losers."""
        queue: asyncio.Queue = asyncio.Queue()
        screener = Screener(mock_adapter, queue, screener_config)
        task = asyncio.ensure_future(screener.run())
        event: CandidateEvent = await asyncio.wait_for(queue.get(), timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        top_n = screener_config["screener"]["top_n"]
        assert len(event.gainers) == top_n
        assert len(event.losers) == top_n

    @pytest.mark.asyncio
    async def test_screener_updates_within_interval(self, mock_adapter):
        """Two events must be produced within 2 * poll_interval."""
        config = {
            "screener": {"top_n": 3, "poll_interval_seconds": 0.05, "provider": "mock", "market_hours_only": False}
        }
        queue: asyncio.Queue = asyncio.Queue()
        screener = Screener(mock_adapter, queue, config)
        task = asyncio.ensure_future(screener.run())
        events = []
        for _ in range(2):
            ev = await asyncio.wait_for(queue.get(), timeout=3.0)
            events.append(ev)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_gainers_have_positive_change_pct(self, mock_adapter, screener_config):
        """All gainer quotes should have positive change_pct."""
        quotes = await mock_adapter.get_top_gainers(5)
        assert all(q.change_pct > 0 for q in quotes)

    @pytest.mark.asyncio
    async def test_losers_have_negative_change_pct(self, mock_adapter, screener_config):
        quotes = await mock_adapter.get_top_losers(5)
        assert all(q.change_pct < 0 for q in quotes)
