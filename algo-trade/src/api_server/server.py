# file: src/api_server/server.py
"""
Minimal read-only HTTP API server (aiohttp).

Endpoints:
    GET /health         — liveness check; returns {"status": "ok"}
    GET /signals        — last N signal events (read-only)
    GET /positions      — current open positions from risk manager
    GET /metrics        — basic metrics (signal count, uptime)

All endpoints are read-only.  No authentication is implemented; restrict
access at the network level (firewall / reverse-proxy) in production.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from aiohttp import web

from src.logger import get_logger

log = get_logger(__name__)

_START_TIME = time.time()
_MAX_SIGNALS = 50  # number of recent signals to keep in memory


def create_app(
    risk_manager: Any,          # RiskManager instance (duck-typed to avoid circular import)
    signal_store: List[Dict],   # shared mutable list of serialised signal dicts
) -> web.Application:
    """
    Factory returning an aiohttp Application.

    Parameters
    ----------
    risk_manager : provides open_position_count and _open_positions.
    signal_store : shared list updated by the signal publisher.
    """

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "uptime_s": round(time.time() - _START_TIME, 1)})

    async def get_signals(request: web.Request) -> web.Response:
        limit = int(request.rel_url.query.get("limit", _MAX_SIGNALS))
        return web.json_response(signal_store[-limit:])

    async def get_positions(request: web.Request) -> web.Response:
        positions = getattr(risk_manager, "_open_positions", [])
        return web.json_response({"open_positions": positions, "count": len(positions)})

    async def get_metrics(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "uptime_s": round(time.time() - _START_TIME, 1),
                "signal_count": len(signal_store),
                "open_positions": getattr(risk_manager, "open_position_count", 0),
            }
        )

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/signals", get_signals)
    app.router.add_get("/positions", get_positions)
    app.router.add_get("/metrics", get_metrics)

    # Serve a minimal static dashboard.
    app.router.add_get("/", _dashboard)

    return app


async def _dashboard(request: web.Request) -> web.Response:
    html = """<!DOCTYPE html>
<html><head><title>Algo-Trade Dashboard</title>
<style>body{font-family:monospace;background:#111;color:#0f0;padding:20px;}
table{border-collapse:collapse;width:100%;}
th,td{border:1px solid #0f0;padding:4px 8px;text-align:left;}
</style></head>
<body>
<h2>Algo-Trade Paper-Trade Dashboard</h2>
<p><a href="/health" style="color:#0f0">/health</a> &nbsp;
   <a href="/signals" style="color:#0f0">/signals</a> &nbsp;
   <a href="/positions" style="color:#0f0">/positions</a> &nbsp;
   <a href="/metrics" style="color:#0f0">/metrics</a></p>
<p>&#9888; This system is for educational/paper-trade use only.</p>
</body></html>"""
    return web.Response(text=html, content_type="text/html")


async def run_api_server(app: web.Application, host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the aiohttp server within an existing asyncio event loop."""
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("api_server started", host=host, port=port)
