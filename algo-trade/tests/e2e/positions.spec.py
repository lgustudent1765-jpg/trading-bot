# file: tests/e2e/positions.spec.py
"""
E2E tests for GET /positions

Covers:
  - No position_store → returns empty dict with count 0
  - Empty position_store → returns empty dict with count 0
  - Position added → reflected in response
  - Response shape: open_positions dict + count int
  - Count matches len(open_positions)
  - Position contains required fields
  - Removed position is no longer in response
"""

from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

pytestmark = pytest.mark.e2e


def _add_position(store, opt_sym="AAPL_2026-05-16_175.0_C"):
    store.add_position(
        option_symbol=opt_sym,
        symbol="AAPL",
        direction="CALL",
        entry_price=2.55,
        stop_loss=1.85,
        take_profit=4.15,
        quantity=10,
        underlying_price=174.50,
    )


class TestPositionsEndpoint:
    async def test_positions_returns_200_without_position_store(self, make_app):
        async with TestClient(TestServer(make_app(pos_store=None))) as client:
            resp = await client.get("/positions")
            assert resp.status == 200

    async def test_positions_no_store_returns_empty_dict_with_count_zero(self, make_app):
        async with TestClient(TestServer(make_app(pos_store=None))) as client:
            body = await (await client.get("/positions")).json()
            assert body["open_positions"] == {}
            assert body["count"] == 0

    async def test_positions_empty_store_returns_count_zero(
        self, make_app, position_store
    ):
        async with TestClient(TestServer(make_app(pos_store=position_store))) as client:
            body = await (await client.get("/positions")).json()
            assert body["count"] == 0

    async def test_positions_with_one_position_returns_count_one(
        self, make_app, position_store
    ):
        _add_position(position_store)
        async with TestClient(TestServer(make_app(pos_store=position_store))) as client:
            body = await (await client.get("/positions")).json()
            assert body["count"] == 1

    async def test_positions_count_matches_open_positions_length(
        self, make_app, position_store
    ):
        _add_position(position_store, "AAPL_2026-05-16_175.0_C")
        _add_position(position_store, "SPY_2026-04-18_520.0_P")
        async with TestClient(TestServer(make_app(pos_store=position_store))) as client:
            body = await (await client.get("/positions")).json()
            assert body["count"] == len(body["open_positions"])

    async def test_positions_response_contains_correct_symbol(
        self, make_app, position_store
    ):
        _add_position(position_store)
        async with TestClient(TestServer(make_app(pos_store=position_store))) as client:
            body = await (await client.get("/positions")).json()
            pos = next(iter(body["open_positions"].values()))
            assert pos["symbol"] == "AAPL"

    async def test_positions_response_contains_required_fields(
        self, make_app, position_store
    ):
        _add_position(position_store)
        required = {"symbol", "direction", "entry_price", "stop_loss", "take_profit", "quantity"}
        async with TestClient(TestServer(make_app(pos_store=position_store))) as client:
            body = await (await client.get("/positions")).json()
            pos = next(iter(body["open_positions"].values()))
            assert required.issubset(pos.keys())

    async def test_positions_removed_position_not_in_response(
        self, make_app, position_store
    ):
        opt_sym = "AAPL_2026-05-16_175.0_C"
        _add_position(position_store, opt_sym)
        position_store.remove_position(opt_sym)
        async with TestClient(TestServer(make_app(pos_store=position_store))) as client:
            body = await (await client.get("/positions")).json()
            assert opt_sym not in body["open_positions"]
            assert body["count"] == 0
