# file: tests/e2e/equity.spec.py
"""
E2E tests for GET /equity

Covers:
  - Returns HTTP 200 with {"equity": <float>}
  - Uses MockBrokerAdapter — equity equals injected starting value
  - No broker_adapter → equity is 0.0 (no error)
  - Broker raises → equity is 0.0, still HTTP 200
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

pytestmark = [pytest.mark.e2e, pytest.mark.skip(reason="GET /equity endpoint removed from current server")]


class TestEquityEndpoint:
    async def test_equity_returns_200(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.get("/equity")
            assert resp.status == 200

    async def test_equity_returns_mock_broker_starting_equity(self, make_app, mock_broker):
        # MockBrokerAdapter is initialized with equity=100_000
        async with TestClient(TestServer(make_app(broker=mock_broker))) as client:
            body = await (await client.get("/equity")).json()
            assert "equity" in body
            assert body["equity"] == pytest.approx(100_000.0)

    async def test_equity_without_broker_returns_zero(self, make_app, signal_store, risk_manager):
        from src.api_server.server import create_app, _ws_clients
        _ws_clients.clear()
        app = create_app(
            risk_manager=risk_manager,
            signal_store=signal_store,
            position_store=None,
            broker_adapter=None,
        )
        async with TestClient(TestServer(app)) as client:
            body = await (await client.get("/equity")).json()
            assert body["equity"] == 0.0

    async def test_equity_returns_zero_when_broker_raises(
        self, make_app, signal_store, risk_manager
    ):
        failing_broker = MagicMock()
        failing_broker.get_account_equity = AsyncMock(side_effect=RuntimeError("api down"))
        from src.api_server.server import create_app, _ws_clients
        _ws_clients.clear()
        app = create_app(
            risk_manager=risk_manager,
            signal_store=signal_store,
            position_store=None,
            broker_adapter=failing_broker,
        )
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/equity")
            assert resp.status == 200
            body = await resp.json()
            assert body["equity"] == 0.0
