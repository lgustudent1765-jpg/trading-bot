# file: tests/e2e/dashboard.spec.py
"""
E2E tests for GET / (HTML dashboard)

Covers:
  - Returns HTTP 200
  - Content-Type is text/html
  - Page contains market status indicator (OPEN or CLOSED)
  - Page contains links to all REST API endpoints
  - Page contains auto-refresh meta tag
  - Page shows correct open position count
"""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

pytestmark = pytest.mark.e2e

# Bug fix: removed /prometheus, /equity, /strategies — those endpoints were
# removed from the current server. Only test links that actually exist.
API_LINKS = ["/health", "/signals", "/positions", "/metrics"]


class TestDashboard:
    async def test_dashboard_returns_200(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.get("/")
            assert resp.status == 200

    async def test_dashboard_content_type_is_html(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.get("/")
            assert "text/html" in resp.content_type

    async def test_dashboard_contains_market_status(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            text = await (await client.get("/")).text()
            assert "OPEN" in text or "CLOSED" in text

    async def test_dashboard_contains_all_api_endpoint_links(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            text = await (await client.get("/")).text()
            for endpoint in API_LINKS:
                assert endpoint in text, f"Dashboard missing link to {endpoint}"

    async def test_dashboard_contains_auto_refresh_meta_tag(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            text = await (await client.get("/")).text()
            assert 'http-equiv="refresh"' in text or "meta http-equiv" in text.lower()

    async def test_dashboard_shows_zero_open_positions_without_store(self, make_app):
        async with TestClient(TestServer(make_app(pos_store=None))) as client:
            text = await (await client.get("/")).text()
            assert "Open positions: <b>0</b>" in text

    async def test_dashboard_shows_correct_position_count_with_store(
        self, make_app, position_store, signal_store
    ):
        position_store.add_position(
            "AAPL_2026-05-16_175.0_C", "AAPL", "CALL", 2.55, 1.85, 4.15, 10
        )
        position_store.add_position(
            "SPY_2026-04-18_520.0_P", "SPY", "PUT", 3.10, 3.80, 1.80, 5
        )
        async with TestClient(TestServer(
            make_app(sig_store=signal_store, pos_store=position_store)
        )) as client:
            text = await (await client.get("/")).text()
            assert "Open positions: <b>2</b>" in text

    async def test_dashboard_contains_algo_trade_title(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            text = await (await client.get("/")).text()
            assert "Algo-Trade" in text or "algo-trade" in text.lower()
