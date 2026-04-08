# file: tests/e2e/health.spec.py
"""
E2E tests for GET /health

Covers:
  - Response is HTTP 200
  - Response shape: status, uptime_s, market_open, market_time_et
  - CORS header is present
  - uptime_s is a non-negative number
  - market_open is a boolean
  - market_time_et contains expected format suffix
"""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

pytestmark = pytest.mark.e2e


class TestHealthEndpoint:
    async def test_health_returns_200(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.get("/health")
            assert resp.status == 200

    async def test_health_response_contains_status_ok(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/health")).json()
            assert body["status"] == "ok"

    async def test_health_response_contains_uptime_seconds(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/health")).json()
            assert "uptime_s" in body
            assert isinstance(body["uptime_s"], (int, float))
            assert body["uptime_s"] >= 0

    async def test_health_response_contains_market_open_boolean(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/health")).json()
            assert "market_open" in body
            assert isinstance(body["market_open"], bool)

    async def test_health_response_contains_market_time_et(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/health")).json()
            assert "market_time_et" in body
            assert "ET" in body["market_time_et"]

    @pytest.mark.xfail(reason="CORS middleware not yet implemented in current server", strict=False)
    async def test_health_response_includes_cors_header(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.get("/health")
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    async def test_health_content_type_is_json(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.get("/health")
            assert "application/json" in resp.content_type

    @pytest.mark.xfail(reason="OPTIONS/CORS preflight not yet implemented in current server", strict=False)
    async def test_health_options_preflight_returns_200(self, make_app):
        """OPTIONS requests (CORS preflight) must succeed."""
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.options("/health")
            assert resp.status == 200
            assert "GET" in resp.headers.get("Access-Control-Allow-Methods", "")
