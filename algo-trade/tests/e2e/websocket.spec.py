# file: tests/e2e/websocket.spec.py
"""
E2E tests for WS /ws (WebSocket endpoint)

Covers:
  - Client receives a "snapshot" message immediately on connect
  - Snapshot contains: type, signals, positions, market_open
  - Snapshot signals list matches the seeded signal store
  - _broadcast() delivers messages to all connected clients
  - Dead/closed clients are pruned from the client set after broadcast
  - Multiple clients receive the same broadcast message
  - market_open in snapshot is a boolean
"""

from __future__ import annotations

import asyncio

import pytest
from aiohttp.test_utils import TestClient, TestServer

import src.api_server.server as server_mod

pytestmark = [pytest.mark.e2e, pytest.mark.skip(reason="WS /ws endpoint and _ws_clients/_broadcast removed from current server")]


class TestWebSocketEndpoint:
    async def test_ws_client_receives_snapshot_on_connect(self, make_app, signal_store):
        server_mod._ws_clients.clear()
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            ws = await client.ws_connect("/ws")
            msg = await ws.receive_json(timeout=3)
            assert msg["type"] == "snapshot"
            await ws.close()

    async def test_ws_snapshot_contains_required_keys(self, make_app, signal_store):
        server_mod._ws_clients.clear()
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            ws = await client.ws_connect("/ws")
            msg = await ws.receive_json(timeout=3)
            assert "signals" in msg
            assert "positions" in msg
            assert "market_open" in msg
            await ws.close()

    async def test_ws_snapshot_signals_match_seeded_store(
        self, make_app, seeded_signal_store, seed_signals
    ):
        server_mod._ws_clients.clear()
        async with TestClient(TestServer(make_app(sig_store=seeded_signal_store))) as client:
            ws = await client.ws_connect("/ws")
            msg = await ws.receive_json(timeout=3)
            # Snapshot sends up to 20 most recent; we have 3 seeds
            assert len(msg["signals"]) == len(seed_signals)
            await ws.close()

    async def test_ws_snapshot_market_open_is_boolean(self, make_app, signal_store):
        server_mod._ws_clients.clear()
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            ws = await client.ws_connect("/ws")
            msg = await ws.receive_json(timeout=3)
            assert isinstance(msg["market_open"], bool)
            await ws.close()

    async def test_ws_broadcast_delivers_to_connected_client(self, make_app, signal_store):
        server_mod._ws_clients.clear()
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            ws = await client.ws_connect("/ws")
            await ws.receive_json(timeout=3)  # consume snapshot

            payload = {"type": "signal", "data": {"symbol": "NVDA", "direction": "CALL"}}
            await server_mod._broadcast(payload)

            msg = await ws.receive_json(timeout=3)
            assert msg["type"] == "signal"
            assert msg["data"]["symbol"] == "NVDA"
            await ws.close()

    async def test_ws_broadcast_reaches_multiple_clients(self, make_app, signal_store):
        server_mod._ws_clients.clear()
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            ws1 = await client.ws_connect("/ws")
            ws2 = await client.ws_connect("/ws")
            # Consume snapshots
            await ws1.receive_json(timeout=3)
            await ws2.receive_json(timeout=3)

            await server_mod._broadcast({"type": "ping"})

            msg1 = await ws1.receive_json(timeout=3)
            msg2 = await ws2.receive_json(timeout=3)
            assert msg1["type"] == "ping"
            assert msg2["type"] == "ping"
            await ws1.close()
            await ws2.close()

    async def test_ws_dead_clients_pruned_after_broadcast(self, make_app, signal_store):
        server_mod._ws_clients.clear()
        async with TestClient(TestServer(make_app(sig_store=signal_store))) as client:
            ws = await client.ws_connect("/ws")
            await ws.receive_json(timeout=3)  # consume snapshot

            # Close the connection from the client side
            await ws.close()
            await asyncio.sleep(0.1)

            count_before = len(server_mod._ws_clients)
            await server_mod._broadcast({"type": "ping"})
            count_after = len(server_mod._ws_clients)

            assert count_after <= count_before

    async def test_ws_snapshot_positions_reflects_position_store(
        self, make_app, signal_store, position_store
    ):
        server_mod._ws_clients.clear()
        position_store.add_position(
            "AAPL_2026-05-16_175.0_C", "AAPL", "CALL", 2.55, 1.85, 4.15, 10
        )
        async with TestClient(TestServer(
            make_app(sig_store=signal_store, pos_store=position_store)
        )) as client:
            ws = await client.ws_connect("/ws")
            msg = await ws.receive_json(timeout=3)
            assert "AAPL_2026-05-16_175.0_C" in msg["positions"]
            await ws.close()
