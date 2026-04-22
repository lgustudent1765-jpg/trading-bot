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

import asyncio
import html as _html
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from aiohttp import web

from src.config import get_config, update_config, deep_merge
from src.logger import get_logger
from src.market_hours import is_market_open, now_et

log = get_logger(__name__)

_START_TIME = time.time()
_MAX_SIGNALS = 100

# C-1: optional API key protecting POST /config (set CONFIG_API_KEY env var to enable)
_CONFIG_API_KEY = os.getenv("CONFIG_API_KEY", "")
_MASK_SENTINEL = "********"

# C-2: validation allowlists / ranges
_ENUM_FIELDS: Dict[str, set] = {
    "mode":                  {"paper", "manual", "automated"},
    "broker_name":           {"mock", "webull"},
    "screener_provider":     {"yahoo", "fmp", "mock"},
    "notify_email_provider": {"smtp", "brevo", "sendgrid", "resend"},
}
_POSITIVE_INT_FIELDS = {
    "screener_poll_interval_seconds",
    "screener_top_n",
    "risk_max_open_positions",
    "risk_pdt_equity_threshold",
    "notify_email_smtp_port",
}
_POSITIVE_FLOAT_FIELDS = {
    "risk_max_position_pct",
    "risk_stop_loss_atr_mult",
    "risk_take_profit_atr_mult",
}
# H-2: permitted webhook domains
_ALLOWED_WEBHOOK_HOSTS = {"discord.com", "discordapp.com", "hooks.slack.com"}


def create_app(
    risk_manager: Any,
    signal_store: List[Dict],
    position_store: Optional[Any] = None,
    market_adapter: Optional[Any] = None,
    action_store: Optional[List[Dict]] = None,
) -> web.Application:
    _action_store: List[Dict] = action_store if action_store is not None else []

    async def health(request: web.Request) -> web.Response:
        cfg = get_config()
        db_ok = position_store.check_connection() if position_store else False
        return web.json_response({
            "status": "ok",
            "uptime_s": round(time.time() - _START_TIME, 1),
            "market_open": is_market_open(),
            "market_time_et": now_et().strftime("%Y-%m-%d %H:%M:%S ET"),
            "mode": cfg.get("mode", "paper"),
            "broker": cfg.get("broker", {}).get("name", "mock"),
            "database_connected": db_ok,
        })

    async def get_signals(request: web.Request) -> web.Response:
        try:
            limit = max(1, min(500, int(request.rel_url.query.get("limit", _MAX_SIGNALS))))
        except (TypeError, ValueError):
            limit = _MAX_SIGNALS
        return web.json_response(signal_store[-limit:])

    async def get_positions(request: web.Request) -> web.Response:
        positions = position_store.get_positions() if position_store else {}
        total_cost = 0.0
        enriched: Dict[str, Any] = {}
        for sym, pos in positions.items():
            entry = float(pos.get("entry_price", 0) or 0)
            qty   = int(pos.get("quantity", 0) or 0)
            cost_basis = round(entry * qty * 100, 2)
            total_cost += cost_basis
            enriched[sym] = {
                **pos,
                "cost_basis": cost_basis,
                "unrealized_pnl": None,
                "unrealized_pnl_pct": None,
            }
        return web.json_response({
            "open_positions": enriched,
            "count": len(enriched),
            "total_cost_basis": round(total_cost, 2),
        })

    async def get_metrics(request: web.Request) -> web.Response:
        open_count = position_store.open_count if position_store else 0
        return web.json_response({
            "uptime_s": round(time.time() - _START_TIME, 1),
            "signal_count": len(signal_store),
            "open_positions": open_count,
            "market_open": is_market_open(),
        })

    async def get_history(request: web.Request) -> web.Response:
        try:
            limit = max(1, min(500, int(request.rel_url.query.get("limit", 50))))
        except (TypeError, ValueError):
            limit = 50
        return web.json_response(list(reversed(_action_store[-limit:])))

    async def get_status(request: web.Request) -> web.Response:
        cfg        = get_config()
        open_count = position_store.open_count if position_store else 0
        db_ok      = position_store.check_connection() if position_store else False
        pnl        = position_store.get_pnl_summary() if position_store else {
            "total_pnl": 0.0, "trade_count": 0, "win_count": 0, "loss_count": 0,
            "win_rate": 0.0, "avg_pnl": 0.0, "best_trade": 0.0, "worst_trade": 0.0,
        }
        paper_capital = float(cfg.get("paper_trading", {}).get("initial_capital", 100.0))
        return web.json_response({
            # system
            "uptime_s":          round(time.time() - _START_TIME, 1),
            "market_open":       is_market_open(),
            "market_time_et":    now_et().strftime("%Y-%m-%d %H:%M:%S ET"),
            "mode":              cfg.get("mode", "paper"),
            "broker":            cfg.get("broker", {}).get("name", "mock"),
            "database_connected": db_ok,
            # live counts
            "open_positions":    open_count,
            "signal_count":      len(signal_store),
            "action_count":      len(_action_store),
            # paper trading capital
            "paper_capital":     paper_capital,
            # p&l
            **pnl,
            # recent activity (newest first)
            "recent_actions":    list(reversed(_action_store[-30:])),
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
                _e = lambda v: _html.escape(str(v))
                sig_rows += (
                    f"<tr>"
                    f"<td>{_e(s.get('ts', s.get('timestamp', s.get('time', '—'))))}</td>"
                    f"<td><b>{_e(s.get('symbol', '—'))}</b></td>"
                    f"<td style='color:{side_color}'>{_e(s.get('direction', s.get('side', s.get('action', '—'))).upper())}</td>"
                    f"<td>{_e(s.get('entry', s.get('price', s.get('entry_price', '—'))))}</td>"
                    f"<td>{_e(s.get('size', s.get('quantity', s.get('qty', '—'))))}</td>"
                    f"<td style='color:#aaa'>{_e(s.get('rationale', s.get('strategy', s.get('reason', '—'))))}</td>"
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

        # Build activity log rows
        recent_actions = list(reversed(_action_store[-30:])) if _action_store else []
        _EVENT_COLORS = {
            "ORDER_FILLED":     "#00ff00",
            "POSITION_CLOSED":  "#ffaa00",
            "SIGNAL_REJECTED":  "#ff4444",
            "SYSTEM_STARTED":   "#00aaff",
            "SYSTEM_STOPPED":   "#888888",
        }
        if recent_actions:
            action_rows = ""
            for a in recent_actions:
                ev = str(a.get("event", ""))
                color = _EVENT_COLORS.get(ev, "#aaaaaa")
                sym = _html.escape(str(a.get("symbol") or "—"))
                ts  = _html.escape(str(a.get("ts", "—"))[:19].replace("T", " "))
                action_rows += (
                    f"<tr>"
                    f"<td style='color:#555'>{ts}</td>"
                    f"<td style='color:{color};font-weight:bold'>{_html.escape(ev)}</td>"
                    f"<td><b>{sym}</b></td>"
                    f"<td style='color:#ccc'>{_html.escape(str(a.get('detail', '—')))}</td>"
                    f"</tr>"
                )
            activity_html = f"""
<div class="card">
  <b>Activity Log</b> <span style="color:#555;font-size:0.8em">(last {len(recent_actions)} events)</span>
  <table style="margin-top:10px">
    <thead><tr><th>Time</th><th>Event</th><th>Symbol</th><th>Detail</th></tr></thead>
    <tbody>{action_rows}</tbody>
  </table>
</div>"""
        else:
            activity_html = '<div class="card"><b>Activity Log</b><p style="color:#555;margin:8px 0 0">No activity yet.</p></div>'

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
  Database: <b>{"CONNECTED" if (position_store.check_connection() if position_store else False) else "DISCONNECTED"}</b> &nbsp;|&nbsp;
  Uptime: {round(time.time() - _START_TIME)}s
</div>
{signals_html}
{positions_html}
{activity_html}
<div class="card">
  <b>API Endpoints:</b> &nbsp;
  <a href="/health">/health</a> &nbsp;
  <a href="/signals">/signals</a> &nbsp;
  <a href="/positions">/positions</a> &nbsp;
  <a href="/metrics">/metrics</a> &nbsp;
  <a href="/history">/history</a>
</div>
<p style="color:#555;font-size:0.8em">Auto-refreshes every 30 seconds.</p>
</body></html>"""
        return web.Response(text=html, content_type="text/html")

    def _mask(value: str) -> str:
        """Return a masked version of a secret string."""
        return ("*" * 8) if value else ""

    async def get_config_endpoint(request: web.Request) -> web.Response:
        # Merge DB overrides (Railway-safe) on top of base config
        base = get_config()
        db_overrides = position_store.get_config_overrides() if position_store else {}
        cfg = deep_merge(base, db_overrides) if db_overrides is not None else base
        broker = cfg.get("broker", {})
        wb = broker.get("webull", {})
        screener = cfg.get("screener", {})
        risk = cfg.get("risk", {})
        market_data = cfg.get("market_data", {})
        notif = cfg.get("notifications", {})
        email = notif.get("email", {})
        webhook = notif.get("webhook", {})
        return web.json_response({
            "mode": cfg.get("mode", "paper"),
            "broker_name": broker.get("name", "mock"),
            "screener_provider": screener.get("provider", "yahoo"),
            "screener_poll_interval_seconds": screener.get("poll_interval_seconds", 60),
            "screener_top_n": screener.get("top_n", 10),
            "screener_market_hours_only": screener.get("market_hours_only", True),
            "fmp_api_key_set": bool(market_data.get("fmp_api_key", "")),
            "risk_max_position_pct": risk.get("max_position_pct", 0.05),
            "risk_max_open_positions": risk.get("max_open_positions", 5),
            "risk_pdt_equity_threshold": risk.get("pdt_equity_threshold", 25000),
            "risk_stop_loss_atr_mult": risk.get("stop_loss_atr_mult", 1.5),
            "risk_take_profit_atr_mult": risk.get("take_profit_atr_mult", 3.0),
            "notify_email_enabled": email.get("enabled", False),
            "notify_email_provider": email.get("provider", "smtp"),
            "notify_email_api_key_set": bool(os.getenv("NOTIFY_EMAIL_API_KEY") or email.get("api_key", "")),
            "notify_email_smtp_host": email.get("smtp_host", "smtp.gmail.com"),
            "notify_email_smtp_port": int(email.get("smtp_port", 587)),
            "notify_email_username": email.get("username", ""),
            "notify_email_password_set": bool(email.get("password", "")),
            "notify_email_recipient": email.get("recipient", ""),
            "notify_webhook_enabled": webhook.get("enabled", False),
            "notify_webhook_url": webhook.get("url", ""),
            "webull_device_id":     _mask(wb.get("device_id", "")),
            "webull_access_token":  _mask(wb.get("access_token", "")),
            "webull_refresh_token": _mask(wb.get("refresh_token", "")),
            "webull_trade_token":   _mask(wb.get("trade_token", "")),
            "webull_account_id_set": bool(wb.get("account_id", "")),
        })

    async def post_config_endpoint(request: web.Request) -> web.Response:
        # C-1: API key auth (enforced only when CONFIG_API_KEY env var is set)
        if _CONFIG_API_KEY:
            if request.headers.get("X-Api-Key", "") != _CONFIG_API_KEY:
                return web.json_response({"error": "unauthorized"}, status=401)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        # C-2: enum allowlist validation
        for field, allowed in _ENUM_FIELDS.items():
            if field in body and body[field] not in allowed:
                return web.json_response(
                    {"error": f"{field} must be one of {sorted(allowed)}"}, status=422
                )

        # C-2: positive integer validation
        for field in _POSITIVE_INT_FIELDS:
            if field in body:
                try:
                    v = int(body[field])
                except (TypeError, ValueError):
                    return web.json_response({"error": f"{field} must be a positive integer"}, status=422)
                if v < 1:
                    return web.json_response({"error": f"{field} must be >= 1"}, status=422)

        # C-2: positive float validation
        for field in _POSITIVE_FLOAT_FIELDS:
            if field in body:
                try:
                    v = float(body[field])
                except (TypeError, ValueError):
                    return web.json_response({"error": f"{field} must be a positive number"}, status=422)
                if v <= 0:
                    return web.json_response({"error": f"{field} must be > 0"}, status=422)

        # H-2: webhook URL must be https:// from an allowed domain
        if "notify_webhook_url" in body:
            url = body["notify_webhook_url"]
            if url and url != _MASK_SENTINEL:
                try:
                    parsed = urlparse(url)
                    host = parsed.netloc.lower().split(":")[0]
                    if parsed.scheme != "https" or not any(
                        host == d or host.endswith("." + d) for d in _ALLOWED_WEBHOOK_HOSTS
                    ):
                        return web.json_response(
                            {"error": "notify_webhook_url must be https:// from discord.com, discordapp.com, or hooks.slack.com"},
                            status=422,
                        )
                except Exception:
                    return web.json_response({"error": "notify_webhook_url is invalid"}, status=422)

        # Build a nested updates dict from the flat payload
        updates: Dict[str, Any] = {}

        def _set(keys: list, val: Any) -> None:
            d = updates
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = val

        mapping = {
            "mode":                         ["mode"],
            "broker_name":                  ["broker", "name"],
            "screener_provider":            ["screener", "provider"],
            "screener_poll_interval_seconds": ["screener", "poll_interval_seconds"],
            "screener_top_n":               ["screener", "top_n"],
            "screener_market_hours_only":   ["screener", "market_hours_only"],
            "fmp_api_key":                  ["market_data", "fmp_api_key"],
            "risk_max_position_pct":        ["risk", "max_position_pct"],
            "risk_max_open_positions":      ["risk", "max_open_positions"],
            "risk_pdt_equity_threshold":    ["risk", "pdt_equity_threshold"],
            "risk_stop_loss_atr_mult":      ["risk", "stop_loss_atr_mult"],
            "risk_take_profit_atr_mult":    ["risk", "take_profit_atr_mult"],
            "notify_email_enabled":         ["notifications", "email", "enabled"],
            "notify_email_provider":        ["notifications", "email", "provider"],
            "notify_email_api_key":         ["notifications", "email", "api_key"],
            "notify_email_smtp_host":       ["notifications", "email", "smtp_host"],
            "notify_email_smtp_port":       ["notifications", "email", "smtp_port"],
            "notify_email_username":        ["notifications", "email", "username"],
            "notify_email_password":        ["notifications", "email", "password"],
            "notify_email_recipient":       ["notifications", "email", "recipient"],
            "notify_webhook_enabled":       ["notifications", "webhook", "enabled"],
            "notify_webhook_url":           ["notifications", "webhook", "url"],
            "webull_device_id":             ["broker", "webull", "device_id"],
            "webull_access_token":          ["broker", "webull", "access_token"],
            "webull_refresh_token":         ["broker", "webull", "refresh_token"],
            "webull_trade_token":           ["broker", "webull", "trade_token"],
            "webull_account_id":            ["broker", "webull", "account_id"],
        }

        for flat_key, path in mapping.items():
            if flat_key in body:
                val = body[flat_key]
                # H-1: skip empty strings and mask sentinels — never overwrite with blank/masked
                if isinstance(val, str) and (val == "" or val == _MASK_SENTINEL):
                    continue
                _set(path, val)

        if not updates:
            return web.json_response({"error": "no recognised fields"}, status=400)

        # 1. Persist to DB (survives Railway redeployments)
        if position_store:
            position_store.merge_config_overrides(updates)

        # 2. Apply to in-memory config immediately (no restart needed)
        update_config(updates)
        return web.json_response({"ok": True})

    # ── Test email endpoint ────────────────────────────────────────────────

    async def test_email_endpoint(request: web.Request) -> web.Response:
        """Send a test email using the current email configuration."""
        import smtplib
        import ssl as _ssl
        import json as _json
        import urllib.request as _urlreq
        from email.mime.text import MIMEText as _MIMEText

        base = get_config()
        db_overrides = position_store.get_config_overrides() if position_store else {}
        cfg   = deep_merge(base, db_overrides) if db_overrides is not None else base
        email = cfg.get("notifications", {}).get("email", {})

        if not email.get("enabled", False):
            return web.json_response({"error": "Email alerts are disabled — enable them first."}, status=400)

        provider  = os.getenv("NOTIFY_EMAIL_PROVIDER") or email.get("provider", "smtp")
        api_key   = os.getenv("NOTIFY_EMAIL_API_KEY") or email.get("api_key", "")
        user      = os.getenv("NOTIFY_EMAIL_USER") or email.get("username", "")
        password  = os.getenv("NOTIFY_EMAIL_PASS") or email.get("password", "")
        recipient = email.get("recipient", "") or user
        smtp_host = email.get("smtp_host", "smtp.gmail.com")
        smtp_port = int(email.get("smtp_port", 587))

        if not user:
            return web.json_response({"error": "Sender email is not configured."}, status=400)
        if not recipient:
            return web.json_response({"error": "Recipient email is not configured."}, status=400)

        body_text = (
            "This is a test message from AlgoTrade.\n\n"
            f"Provider  : {provider}\n"
            f"Sender    : {user}\n"
            f"Recipient : {recipient}\n\n"
            "Your email notification configuration is working correctly."
        )

        # ── HTTP API providers (not blocked by Railway) ────────────────────
        if provider in ("brevo", "sendgrid", "resend"):
            if not api_key:
                return web.json_response(
                    {"error": f"API key not set. Add NOTIFY_EMAIL_API_KEY env var or set it in Settings."},
                    status=400,
                )

            if provider == "brevo":
                url     = "https://api.brevo.com/v3/smtp/email"
                headers = {"api-key": api_key, "Content-Type": "application/json"}
                payload = {
                    "sender":      {"email": user},
                    "to":          [{"email": recipient}],
                    "subject":     "[AlgoTrade] Test Email",
                    "textContent": body_text,
                }
            elif provider == "sendgrid":
                url     = "https://api.sendgrid.com/v3/mail/send"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "personalizations": [{"to": [{"email": recipient}]}],
                    "from":    {"email": user},
                    "subject": "[AlgoTrade] Test Email",
                    "content": [{"type": "text/plain", "value": body_text}],
                }
            else:  # resend
                url     = "https://api.resend.com/emails"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"from": user, "to": [recipient], "subject": "[AlgoTrade] Test Email", "text": body_text}

            try:
                loop = asyncio.get_event_loop()

                def _http_send():
                    data = _json.dumps(payload).encode()
                    req  = _urlreq.Request(url, data=data, headers=headers, method="POST")
                    with _urlreq.urlopen(req, timeout=15) as resp:
                        return resp.getcode(), resp.read().decode()

                status_code, resp_body = await loop.run_in_executor(None, _http_send)
                if status_code not in (200, 201, 202):
                    return web.json_response(
                        {"error": f"{provider} API returned {status_code}: {resp_body}"},
                        status=500,
                    )
                log.info("test email sent via api", provider=provider, recipient=recipient, api_response=resp_body)
                return web.json_response({"ok": True, "recipient": recipient, "provider": provider, "api_response": resp_body})
            except Exception as exc:
                log.error("test email api failed", provider=provider, error=str(exc))
                return web.json_response({"error": str(exc)}, status=500)

        # ── SMTP path ──────────────────────────────────────────────────────
        if not password:
            return web.json_response({"error": "App password is not configured."}, status=400)

        try:
            msg = _MIMEText(body_text)
            msg["Subject"] = "[AlgoTrade] Test Email"
            msg["From"]    = user
            msg["To"]      = recipient

            context = _ssl.create_default_context()
            loop    = asyncio.get_event_loop()

            def _send():
                if smtp_port == 465:
                    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as srv:
                        srv.login(user, password)
                        srv.sendmail(user, recipient, msg.as_string())
                else:
                    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as srv:
                        srv.starttls(context=context)
                        srv.login(user, password)
                        srv.sendmail(user, recipient, msg.as_string())

            await loop.run_in_executor(None, _send)
            log.info("test email sent", recipient=recipient)
            return web.json_response({"ok": True, "recipient": recipient, "provider": "smtp"})
        except smtplib.SMTPAuthenticationError:
            return web.json_response(
                {"error": "Authentication failed. Check your app password (Gmail requires a dedicated App Password, not your account password)."},
                status=500,
            )
        except smtplib.SMTPConnectError:
            return web.json_response(
                {"error": f"Cannot connect to {smtp_host}:{smtp_port}. Check host/port settings."},
                status=500,
            )
        except OSError as exc:
            if getattr(exc, "errno", None) in (101, 111, 110):
                log.error("test email failed — SMTP blocked by platform", error=str(exc))
                return web.json_response(
                    {"error": (
                        "Railway blocks outbound SMTP. "
                        "Switch Email Provider to 'brevo' in Settings and add your Brevo API key."
                    )},
                    status=500,
                )
            log.error("test email failed", error=str(exc))
            return web.json_response({"error": str(exc)}, status=500)
        except Exception as exc:
            log.error("test email failed", error=str(exc))
            return web.json_response({"error": str(exc)}, status=500)

    # ── Market data endpoints ──────────────────────────────────────────────

    async def get_overview(request: web.Request) -> web.Response:
        """Top gainers/losers from live market data."""
        if not market_adapter:
            return web.json_response({"error": "market adapter unavailable"}, status=503)
        try:
            gainers = await market_adapter.get_top_gainers(limit=5)
            losers  = await market_adapter.get_top_losers(limit=5)
            return web.json_response({
                "gainers": [
                    {"symbol": q.symbol, "price": q.price,
                     "change_pct": round(q.change_pct, 2), "volume": q.volume}
                    for q in gainers
                ],
                "losers": [
                    {"symbol": q.symbol, "price": q.price,
                     "change_pct": round(q.change_pct, 2), "volume": q.volume}
                    for q in losers
                ],
                "refreshed_at": now_et().isoformat(),
            })
        except Exception as exc:
            log.error("overview endpoint failed", error=str(exc))
            return web.json_response({"error": "failed to fetch market data"}, status=503)

    async def get_quote(request: web.Request) -> web.Response:
        """Price bars for a symbol. Query params: range (default 1d), interval (default 1m)."""
        symbol    = request.match_info.get("symbol", "").upper()
        if not symbol:
            return web.json_response({"error": "symbol required"}, status=400)
        range_str = request.rel_url.query.get("range", "1d")
        interval  = request.rel_url.query.get("interval", "1m")
        if not market_adapter:
            return web.json_response({"error": "market adapter unavailable"}, status=503)
        try:
            bars  = await market_adapter.get_historical_bars(symbol, range_str, interval)
            quote = await market_adapter.get_quote(symbol)
            return web.json_response({
                "symbol":        symbol,
                "current_price": quote.price,
                "change_pct":    round(quote.change_pct, 2),
                "bars": bars,
            })
        except Exception as exc:
            log.error("quote endpoint failed", symbol=symbol, error=str(exc))
            return web.json_response({"error": "failed to fetch quote"}, status=503)

    _STRATEGY_META = [
        ("RSIMACD",            "RSI overbought/oversold + MACD histogram direction"),
        ("EMACross",           "EMA 9 crosses above/below EMA 21"),
        ("BollingerBreakout",  "Price breaks outside Bollinger Bands (20-period, 2σ)"),
        ("Momentum",           "5-bar price change exceeds 0.5% threshold"),
        ("MeanReversion",      "Price > 2σ from SMA20 — fade the extreme"),
        ("VWAP",               "Price deviates > 0.3% from VWAP intraday"),
        ("RSIAggressive",      "Pure RSI with aggressive thresholds (80 / 20)"),
        ("TrendFollowing",     "SMA20 > SMA50 uptrend + RSI > 50 confirmation"),
        ("VolatilityBreakout", "Last candle range > 2× ATR — follow direction"),
        ("MACDCross",          "MACD line crosses signal line (crossover event)"),
    ]

    def _extract_strategy_name(sig: dict) -> str:
        """Return strategy name from signal dict (new field, or parsed from rationale)."""
        name = sig.get("strategy", "")
        if not name:
            rationale = sig.get("rationale", "")
            if rationale.startswith("[") and "]" in rationale:
                name = rationale[1:rationale.index("]")]
        return name

    async def get_strategies(request: web.Request) -> web.Response:
        """All 10 strategies with live signal counts and DB performance stats."""
        total = len(signal_store)
        calls = sum(1 for s in signal_store if s.get("direction") == "CALL")
        puts  = total - calls
        seen: dict = {}
        sig_counts: dict = {}
        for s in signal_store:
            sym = s.get("symbol")
            if sym:
                seen[sym] = True
            sname = _extract_strategy_name(s)
            if sname:
                sig_counts[sname] = sig_counts.get(sname, 0) + 1

        perf = position_store.get_strategy_scores() if position_store else {}

        strategies = []
        for name, description in _STRATEGY_META:
            row = perf.get(name, {})
            strategies.append({
                "name":        name,
                "description": description,
                "signals":     sig_counts.get(name, 0),
                "trades":      row.get("trades", 0),
                "wins":        row.get("wins", 0),
                "losses":      row.get("losses", 0),
                "win_rate":    row.get("win_rate", 0.0),
                "total_pnl":   row.get("total_pnl", 0.0),
            })

        return web.json_response({
            "is_active":      True,
            "total_signals":  total,
            "call_signals":   calls,
            "put_signals":    puts,
            "symbols_traded": list(seen.keys())[-20:],
            "strategies":     strategies,
        })

    async def post_reset(request: web.Request) -> web.Response:
        """Reset all paper trading data (positions, signals, cooldowns, strategy stats, actions)."""
        if not position_store:
            return web.json_response({"error": "no persistence store"}, status=503)
        try:
            from src.persistence import (
                PositionRecord, CooldownRecord, SignalRecord,
                ActionRecord, StrategyPerformanceRecord,
            )
            from datetime import datetime, timezone as _tz
            with position_store.SessionLocal() as session:
                session.query(PositionRecord).delete()
                session.query(CooldownRecord).delete()
                session.query(SignalRecord).delete()
                session.query(ActionRecord).delete()
                session.query(StrategyPerformanceRecord).delete()
                session.commit()

            signal_store.clear()
            _action_store.clear()

            reset_entry = {
                "event": "SYSTEM_RESET", "symbol": None,
                "detail": "Paper trading data reset by user",
                "data": {}, "ts": datetime.now(_tz.utc).isoformat(),
            }
            _action_store.append(reset_entry)
            log.info("paper trading data reset by user")
            return web.json_response({"ok": True})
        except Exception as exc:
            log.error("reset failed", error=str(exc))
            return web.json_response({"error": str(exc)}, status=500)

    async def run_backtest_endpoint(request: web.Request) -> web.Response:
        """Run a real backtest using Yahoo Finance historical data."""
        if not market_adapter:
            return web.json_response({"error": "market adapter unavailable"}, status=503)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        symbol = str(body.get("symbol", "SPY")).upper()
        period = str(body.get("period", "1 Year"))

        _range_map = {
            "3 Months": ("3mo", "1d"),
            "6 Months": ("6mo", "1d"),
            "1 Year":   ("1y",  "1d"),
            "2 Years":  ("2y",  "1wk"),
            "5 Years":  ("5y",  "1wk"),
        }
        range_str, interval = _range_map.get(period, ("1y", "1d"))

        try:
            import asyncio as _aio
            bars = await market_adapter.get_historical_bars(symbol, range_str, interval)
            if not bars or len(bars) < 30:
                return web.json_response(
                    {"error": f"Insufficient historical data for {symbol} ({len(bars)} bars)"},
                    status=422,
                )

            from src.backtester import Backtester
            from src.config import get_config
            cfg = get_config()
            bt  = Backtester(cfg)
            result = await _aio.get_event_loop().run_in_executor(None, bt.run_from_bars, bars)
            summary = result.summary()

            # Build equity curve from trade sequence
            equity = 10_000.0
            equity_curve = [{"date": bars[0]["datetime"][:10], "equity": round(equity)}]
            for trade in result.trades:
                if trade.pnl_pct is not None:
                    equity *= (1 + trade.pnl_pct / 100)
                    idx = min(trade.exit_bar or 0, len(bars) - 1)
                    equity_curve.append({
                        "date":   bars[idx]["datetime"][:10],
                        "equity": round(equity),
                    })

            return web.json_response({
                **summary,
                "equity_curve": equity_curve,
                "symbol": symbol,
                "period": period,
            })
        except Exception as exc:
            log.error("backtest endpoint failed", symbol=symbol, error=str(exc))
            return web.json_response({"error": f"Backtest failed: {exc}"}, status=500)

    # ── Router ──────────────────────────────────────────────────────────────

    app = web.Application()
    app.router.add_get("/health",           health)
    app.router.add_get("/signals",          get_signals)
    app.router.add_get("/positions",        get_positions)
    app.router.add_get("/metrics",          get_metrics)
    app.router.add_get("/history",          get_history)
    app.router.add_get("/status",           get_status)
    app.router.add_get("/overview",         get_overview)
    app.router.add_get("/quote/{symbol}",   get_quote)
    app.router.add_get("/strategies",       get_strategies)
    app.router.add_post("/reset",           post_reset)
    app.router.add_post("/backtest/run",    run_backtest_endpoint)
    app.router.add_get("/config",                get_config_endpoint)
    app.router.add_post("/config",               post_config_endpoint)
    app.router.add_post("/config/test-email",    test_email_endpoint)
    app.router.add_get("/",                 dashboard)
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
