# file: tests/e2e/strategies.spec.py
"""
E2E tests for GET /strategies

Covers:
  - Returns HTTP 200 with {"strategies": [...]}
  - Empty signal store → endpoint short-circuits to [] (store is falsy when empty)
  - Non-empty signal store → exactly one strategy entry returned
  - Strategy entry contains all required stat fields
  - call/put counts match seeded data
  - avg_rsi_call is computed from call signals only
  - risk_reward field is present and >= 0
  - status field is "active"
"""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.e2e.test_helpers import make_signal_dict

pytestmark = [pytest.mark.e2e, pytest.mark.skip(reason="GET /strategies endpoint removed from current server")]

REQUIRED_STRATEGY_FIELDS = {
    "name", "description", "total_signals", "call_signals", "put_signals",
    "avg_rsi_call", "avg_rsi_put", "avg_delta", "avg_iv",
    "avg_entry", "avg_stop", "avg_target", "risk_reward", "status",
}


class TestStrategiesEndpoint:
    async def test_strategies_returns_200(self, make_app, signal_store):
        signal_store.append(make_signal_dict("AAPL"))
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            resp = await client.get("/strategies")
            assert resp.status == 200

    async def test_strategies_response_contains_strategies_list(self, make_app, signal_store):
        signal_store.append(make_signal_dict("AAPL"))
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/strategies")).json()
            assert "strategies" in body
            assert isinstance(body["strategies"], list)

    async def test_strategies_empty_store_returns_empty_list(self, make_app, signal_store):
        """Empty store is falsy → endpoint returns {"strategies": []}."""
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/strategies")).json()
            assert body["strategies"] == []

    async def test_strategies_has_exactly_one_entry_when_store_has_signals(
        self, make_app, signal_store
    ):
        signal_store.append(make_signal_dict("AAPL", "CALL"))
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/strategies")).json()
            assert len(body["strategies"]) == 1

    async def test_strategies_entry_contains_all_required_fields(self, make_app, signal_store):
        signal_store.append(make_signal_dict("AAPL", "CALL"))
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/strategies")).json()
            strat = body["strategies"][0]
            assert REQUIRED_STRATEGY_FIELDS.issubset(strat.keys())

    async def test_strategies_call_and_put_counts_match_seeded_data(
        self, make_app, signal_store
    ):
        signal_store.append(make_signal_dict("AAPL", "CALL", rsi=72.0))
        signal_store.append(make_signal_dict("AAPL", "CALL", rsi=74.0))
        signal_store.append(make_signal_dict("SPY", "PUT", rsi=28.0))

        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/strategies")).json()
            strat = body["strategies"][0]
            assert strat["total_signals"] == 3
            assert strat["call_signals"] == 2
            assert strat["put_signals"] == 1

    async def test_strategies_avg_rsi_call_excludes_put_signals(
        self, make_app, signal_store
    ):
        signal_store.append(make_signal_dict("AAPL", "CALL", rsi=72.0))
        signal_store.append(make_signal_dict("AAPL", "CALL", rsi=76.0))
        signal_store.append(make_signal_dict("SPY", "PUT", rsi=27.0))

        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/strategies")).json()
            strat = body["strategies"][0]
            # avg_rsi_call should be (72+76)/2 = 74.0, ignoring the PUT's RSI of 27
            assert strat["avg_rsi_call"] == pytest.approx(74.0, rel=1e-3)

    async def test_strategies_status_is_active(self, make_app, signal_store):
        signal_store.append(make_signal_dict("AAPL", "CALL"))
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/strategies")).json()
            assert body["strategies"][0]["status"] == "active"

    async def test_strategies_risk_reward_is_non_negative(self, make_app, signal_store):
        signal_store.append(make_signal_dict("AAPL", "CALL"))
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            body = await (await client.get("/strategies")).json()
            assert body["strategies"][0]["risk_reward"] >= 0
