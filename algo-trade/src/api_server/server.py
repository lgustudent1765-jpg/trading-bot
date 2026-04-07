# file: src/api_server/server.py
"""
Read-only HTTP API server (aiohttp).

Endpoints:
    GET /health     — liveness + market-hours status
    GET /signals    — recent signal events
    GET /positions  — live open positions from persistence store
    GET /metrics    — counts and uptime
    GET /           — HTML dashboard
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from aiohttp import web

from src.config import get_config
from src.logger import get_logger
from src.market_hours import is_market_open, now_et

log = get_logger(__name__)

_START_TIME = time.time()
_MAX_SIGNALS = 100


def create_app(
    risk_manager: Any,
    signal_store: List[Dict],
    position_store: Optional[Any] = None,
) -> web.Application:

    async def health(request: web.Request) -> web.Response:
        cfg = get_config()
        return web.json_response({
            "status": "ok",
            "uptime_s": round(time.time() - _START_TIME, 1),
            "market_open": is_market_open(),
            "market_time_et": now_et().strftime("%Y-%m-%d %H:%M:%S ET"),
            "mode": cfg.get("mode", "paper"),
            "broker": cfg.get("broker", {}).get("name", "mock"),
        })

    async def get_signals(request: web.Request) -> web.Response:
        limit = int(request.rel_url.query.get("limit", _MAX_SIGNALS))
        return web.json_response(signal_store[-limit:])

    async def get_positions(request: web.Request) -> web.Response:
        if position_store:
            positions = position_store.get_positions()
        else:
            positions = {}
        return web.json_response({
            "open_positions": positions,
            "count": len(positions),
        })

    async def get_metrics(request: web.Request) -> web.Response:
        open_count = position_store.open_count if position_store else 0
        return web.json_response({
            "uptime_s": round(time.time() - _START_TIME, 1),
            "signal_count": len(signal_store),
            "open_positions": open_count,
            "market_open": is_market_open(),
        })

    async def dashboard(request: web.Request) -> web.Response:
        open_count = position_store.open_count if position_store else 0
        market_status = "OPEN" if is_market_open() else "CLOSED"
        market_color  = "#00ff00" if is_market_open() else "#ff4444"

        # Build signals table rows
        recent_signals = signal_store[-20:] if signal_store else []
        if recent_signals:
            sig_rows = ""
            for s in reversed(recent_signals):
                _direction = str(s.get("direction", s.get("side", ""))).upper()
                side_color = "#00ff00" if _direction in ("BUY", "CALL") else "#ff4444"
                sig_rows += (
                    f"<tr>"
                    f"<td>{s.get('ts', s.get('timestamp', s.get('time', '—')))}</td>"
                    f"<td><b>{s.get('symbol', '—')}</b></td>"
                    f"<td style='color:{side_color}'>{s.get('direction', s.get('side', s.get('action', '—'))).upper()}</td>"
                    f"<td>{s.get('entry', s.get('price', s.get('entry_price', '—')))}</td>"
                    f"<td>{s.get('size', s.get('quantity', s.get('qty', '—')))}</td>"
                    f"<td style='color:#aaa'>{s.get('rationale', s.get('strategy', s.get('reason', '—')))}</td>"
                    f"</tr>"
                )
            signals_html = f"""
<div class="card">
  <b>Recent Signals</b> <span style="color:#555;font-size:0.8em">(last {len(recent_signals)})</span>
  <table style="margin-top:10px">
    <thead><tr><th>Time</th><th>Symbol</th><th>Side</th><th>Price</th><th>Qty</th><th>Strategy</th></tr></thead>
    <tbody>{sig_rows}</tbody>
  </table>
</div>"""
        else:
            signals_html = '<div class="card"><b>Recent Signals</b><p style="color:#555;margin:8px 0 0">No signals yet.</p></div>'

        # Build positions table rows
        positions = position_store.get_positions() if position_store else {}
        if positions:
            pos_rows = ""
            for sym, pos in positions.items():
                pnl = pos.get("unrealized_pnl", pos.get("pnl", "—"))
                pnl_color = "#00ff00" if isinstance(pnl, (int, float)) and pnl >= 0 else "#ff4444"
                pos_rows += (
                    f"<tr>"
                    f"<td><b>{sym}</b></td>"
                    f"<td>{pos.get('quantity', pos.get('qty', '—'))}</td>"
                    f"<td>{pos.get('entry_price', pos.get('avg_price', '—'))}</td>"
                    f"<td>{pos.get('current_price', pos.get('underlying_price', '—'))}</td>"
                    f"<td style='color:{pnl_color}'>{pnl}</td>"
                    f"</tr>"
                )
            positions_html = f"""
<div class="card">
  <b>Open Positions</b> <span style="color:#555;font-size:0.8em">({len(positions)})</span>
  <table style="margin-top:10px">
    <thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Current</th><th>Unrealized P&L</th></tr></thead>
    <tbody>{pos_rows}</tbody>
  </table>
</div>"""
        else:
            positions_html = '<div class="card"><b>Open Positions</b><p style="color:#555;margin:8px 0 0">No open positions.</p></div>'

        html = f"""<!DOCTYPE html>
<html><head><title>Algo-Trade Dashboard</title>
<meta http-equiv="refresh" content="30">
<style>
  body{{font-family:monospace;background:#0a0a0a;color:#00ff00;padding:20px;max-width:1200px;margin:0 auto;}}
  h2{{color:#00ff00;border-bottom:1px solid #00ff00;padding-bottom:8px;}}
  .card{{background:#111;border:1px solid #333;padding:15px;margin:10px 0;border-radius:4px;}}
  .status{{color:{market_color};font-weight:bold;font-size:1.2em;}}
  a{{color:#00aaff;text-decoration:none;}} a:hover{{text-decoration:underline;}}
  table{{border-collapse:collapse;width:100%;margin-top:8px;}}
  th,td{{border:1px solid #222;padding:6px 12px;text-align:left;font-size:0.9em;}}
  th{{background:#1a1a1a;color:#aaa;}}
  tr:hover td{{background:#161616;}}
  .warn{{color:#ffaa00;padding:10px;border:1px solid #ffaa00;margin:10px 0;border-radius:4px;}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;}}
  @media(max-width:700px){{.grid{{grid-template-columns:1fr;}}}}
</style></head>
<body>
<h2>Algo-Trade Paper-Trade Dashboard</h2>
<div class="warn">&#9888; PAPER TRADE MODE — No real orders are placed</div>
<div class="card">
  <span class="status">Market: {market_status}</span> &nbsp;|&nbsp;
  {now_et().strftime("%Y-%m-%d %H:%M:%S ET")} &nbsp;|&nbsp;
  Open positions: <b>{open_count}</b> &nbsp;|&nbsp;
  Signals: <b>{len(signal_store)}</b> &nbsp;|&nbsp;
  Uptime: {round(time.time() - _START_TIME)}s
</div>
{signals_html}
{positions_html}
<div class="card">
  <b>API Endpoints:</b> &nbsp;
  <a href="/health">/health</a> &nbsp;
  <a href="/signals">/signals</a> &nbsp;
  <a href="/positions">/positions</a> &nbsp;
  <a href="/metrics">/metrics</a>
</div>
<p style="color:#555;font-size:0.8em">Auto-refreshes every 30 seconds.</p>
</body></html>"""
        return web.Response(text=html, content_type="text/html")

    app = web.Application()
    app.router.add_get("/health",    health)
    app.router.add_get("/signals",   get_signals)
    app.router.add_get("/positions", get_positions)
    app.router.add_get("/metrics",   get_metrics)
    app.router.add_get("/",          dashboard)
    return app


async def run_api_server(
    app: web.Application,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> None:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("api_server started", host=host, port=port)
