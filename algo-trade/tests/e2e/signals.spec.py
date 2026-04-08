# file: tests/e2e/signals.spec.py
"""
E2E tests for GET /signals

Covers:
  - Empty store returns empty list
  - Seeded store returns signals in correct order (oldest-first)
  - ?limit= query parameter is respected
  - Each signal dict contains expected fields
  - Large limit request is capped at store contents, not error
"""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.e2e.test_helpers import make_signal_dict

pytestmark = pytest.mark.e2e


class TestSignalsEndpoint:
    async def test_signals_returns_200(self, make_app, signal_store):
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            resp = await client.get("/signals")
            assert resp.status == 200

    async def test_signals_empty_store_returns_empty_list(self, make_app, signal_store):
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/signals")).json()
            assert body == []

    async def test_signals_seeded_store_returns_all_signals(
        self, make_app, seeded_signal_store, seed_signals
    ):
        async with TestClient(TestServer(make_app(sig_store=seeded_signal_store))) as client:
            body = await (await client.get("/signals")).json()
            assert len(body) == len(seed_signals)

    async def test_signals_ordered_oldest_first(self, make_app, seeded_signal_store):
        async with TestClient(TestServer(make_app(sig_store=seeded_signal_store))) as client:
            body = await (await client.get("/signals")).json()
            timestamps = [s["ts"] for s in body]
            assert timestamps == sorted(timestamps)

    async def test_signals_limit_one_returns_single_signal(
        self, make_app, seeded_signal_store
    ):
        async with TestClient(TestServer(make_app(sig_store=seeded_signal_store))) as client:
            body = await (await client.get("/signals?limit=1")).json()
            assert len(body) == 1

    async def test_signals_limit_larger_than_store_returns_all(
        self, make_app, seeded_signal_store, seed_signals
    ):
        async with TestClient(TestServer(make_app(sig_store=seeded_signal_store))) as client:
            body = await (await client.get("/signals?limit=9999")).json()
            assert len(body) == len(seed_signals)

    async def test_signals_response_contains_expected_fields(
        self, make_app, seeded_signal_store
    ):
        required_fields = {"symbol", "direction", "strike", "expiry", "entry", "rsi", "ts"}
        async with TestClient(TestServer(make_app(sig_store=seeded_signal_store))) as client:
            body = await (await client.get("/signals")).json()
            for sig in body:
                assert required_fields.issubset(sig.keys()), (
                    f"Signal missing fields: {required_fields - sig.keys()}"
                )

    async def test_signals_directions_are_valid_enum_values(
        self, make_app, seeded_signal_store
    ):
        async with TestClient(TestServer(make_app(sig_store=seeded_signal_store))) as client:
            body = await (await client.get("/signals")).json()
            for sig in body:
                assert sig["direction"] in ("CALL", "PUT")

    async def test_signals_appended_after_store_creation_are_returned(
        self, make_app, signal_store
    ):
        signal_store.append(make_signal_dict("NVDA", "CALL"))
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/signals")).json()
            assert any(s["symbol"] == "NVDA" for s in body)
