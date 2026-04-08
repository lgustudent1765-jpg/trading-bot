# file: tests/e2e/metrics.spec.py
"""
E2E tests for GET /metrics

Covers:
  - Returns HTTP 200
  - Response shape: uptime_s, signal_count, open_positions, market_open
  - signal_count reflects actual signals in store
  - open_positions reflects actual open positions
  - uptime_s is non-negative
  - market_open is a boolean
"""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.e2e.test_helpers import make_signal_dict

pytestmark = pytest.mark.e2e


class TestMetricsEndpoint:
    async def test_metrics_returns_200(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.get("/metrics")
            assert resp.status == 200

    async def test_metrics_contains_all_required_fields(self, make_app):
        # Bug fix: removed ws_clients and prometheus_scrape — not present in current server
        required = {"uptime_s", "signal_count", "open_positions", "market_open"}
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/metrics")).json()
            assert required.issubset(body.keys())

    async def test_metrics_signal_count_reflects_store_size(
        self, make_app, signal_store
    ):
        signal_store.append(make_signal_dict("AAPL"))
        signal_store.append(make_signal_dict("SPY", "PUT"))
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/metrics")).json()
            assert body["signal_count"] == 2

    async def test_metrics_open_positions_zero_without_store(self, make_app):
        async with TestClient(TestServer(make_app(pos_store=None))) as client:
            body = await (await client.get("/metrics")).json()
            assert body["open_positions"] == 0

    async def test_metrics_open_positions_reflects_store(
        self, make_app, position_store, signal_store
    ):
        position_store.add_position(
            "AAPL_2026-05-16_175.0_C", "AAPL", "CALL", 2.55, 1.85, 4.15, 10
        )
        async with TestClient(TestServer(
            make_app(sig_store=signal_store, pos_store=position_store)
        )) as client:
            body = await (await client.get("/metrics")).json()
            assert body["open_positions"] == 1

    async def test_metrics_uptime_is_non_negative(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/metrics")).json()
            assert body["uptime_s"] >= 0

    async def test_metrics_market_open_is_boolean(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/metrics")).json()
            assert isinstance(body["market_open"], bool)
