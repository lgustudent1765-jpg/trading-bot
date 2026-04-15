# file: src/notifier.py
"""
Alert notifier — sends email and/or webhook (Discord/Slack) notifications
when signals are generated, orders fill, or positions close.

Configuration (config.yaml):
    notifications:
      email:
        enabled: true
        smtp_host: smtp.gmail.com
        smtp_port: 587
        username: your@gmail.com      # set via NOTIFY_EMAIL_USER env var
        password: ""                  # set via NOTIFY_EMAIL_PASS env var (app password)
        recipient: your@gmail.com
      webhook:
        enabled: false
        url: ""                       # Discord/Slack webhook URL via NOTIFY_WEBHOOK_URL

Gmail setup: use an App Password (not your account password).
  Google Account -> Security -> 2-Step Verification -> App passwords
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from typing import Any, Dict, Optional
import os

from src.logger import get_logger
from src.config import get_config

log = get_logger(__name__)


class Notifier:
    """
    Sends alerts via email and/or webhook.

    All sends are non-blocking (run in thread executor) so they never
    stall the asyncio event loop.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        # Store initial config; live overrides still applied via get_config() when
        # the instance config has no notifications key (production path).
        self._init_config = config or {}

    def _get_email_cfg(self):
        """Read email config from instance config (tests) or live get_config() (production)."""
        if self._init_config.get("notifications"):
            notif = self._init_config.get("notifications", {})
        else:
            notif = get_config().get("notifications", {})
        email = notif.get("email", {})
        # Allow tests to override credentials via instance attributes.
        user = getattr(self, "_email_user", None)
        if user is None:
            user = os.getenv("NOTIFY_EMAIL_USER") or email.get("username", "")
        password = getattr(self, "_email_pass", None)
        if password is None:
            password = os.getenv("NOTIFY_EMAIL_PASS") or email.get("password", "")
        return {
            "enabled":   email.get("enabled", False),
            "provider":  os.getenv("NOTIFY_EMAIL_PROVIDER") or email.get("provider", "smtp"),
            "api_key":   os.getenv("NOTIFY_EMAIL_API_KEY") or email.get("api_key", ""),
            "smtp_host": email.get("smtp_host", "smtp.gmail.com"),
            "smtp_port": int(email.get("smtp_port", 587)),
            "user":      user,
            "password":  password,
            "to":        email.get("recipient", "") or user,
        }

    def _get_webhook_cfg(self):
        """Read webhook config from instance config (tests) or live get_config() (production)."""
        if self._init_config.get("notifications"):
            notif = self._init_config.get("notifications", {})
        else:
            notif = get_config().get("notifications", {})
        webhook = notif.get("webhook", {})
        url = getattr(self, "_webhook_url", None)
        if url is None:
            url = os.getenv("NOTIFY_WEBHOOK_URL", webhook.get("url", ""))
        return {
            "enabled": webhook.get("enabled", False),
            "url":     url,
        }

    def _send_email_sync(self, subject: str, body: str) -> None:
        """Synchronous email send — called from thread executor."""
        ec = self._get_email_cfg()
        provider = ec["provider"]

        if provider in ("brevo", "sendgrid", "resend"):
            # HTTP API send — not blocked by Railway
            import urllib.request
            import json as _json

            if not ec["api_key"]:
                log.warning("email api_key not configured — set NOTIFY_EMAIL_API_KEY")
                return
            if not ec["user"] or not ec["to"]:
                log.warning("email sender/recipient not configured")
                return

            if provider == "brevo":
                url = "https://api.brevo.com/v3/smtp/email"
                headers = {"api-key": ec["api_key"], "Content-Type": "application/json"}
                payload = {
                    "sender":      {"email": ec["user"]},
                    "to":          [{"email": ec["to"]}],
                    "subject":     subject,
                    "textContent": body,
                }
            elif provider == "sendgrid":
                url = "https://api.sendgrid.com/v3/mail/send"
                headers = {"Authorization": f"Bearer {ec['api_key']}", "Content-Type": "application/json"}
                payload = {
                    "personalizations": [{"to": [{"email": ec["to"]}]}],
                    "from":    {"email": ec["user"]},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                }
            else:  # resend
                url = "https://api.resend.com/emails"
                headers = {"Authorization": f"Bearer {ec['api_key']}", "Content-Type": "application/json"}
                payload = {"from": ec["user"], "to": [ec["to"]], "subject": subject, "text": body}

            try:
                data = _json.dumps(payload).encode()
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    status = resp.getcode()
                if status not in (200, 201, 202):
                    log.error("email api returned unexpected status", status=status)
                    return
                log.info("email alert sent via api", provider=provider, subject=subject)
            except Exception as exc:
                log.error("email api send failed", provider=provider, error=str(exc))
            return

        # ── SMTP path ──────────────────────────────────────────────────────
        if not ec["user"] or not ec["password"]:
            log.warning("email not configured — set NOTIFY_EMAIL_USER and NOTIFY_EMAIL_PASS")
            return
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = ec["user"]
            msg["To"] = ec["to"]

            context = ssl.create_default_context()
            if ec["smtp_port"] == 465:
                with smtplib.SMTP_SSL(ec["smtp_host"], ec["smtp_port"], context=context) as server:
                    server.login(ec["user"], ec["password"])
                    server.sendmail(ec["user"], ec["to"], msg.as_string())
            else:
                with smtplib.SMTP(ec["smtp_host"], ec["smtp_port"]) as server:
                    server.starttls(context=context)
                    server.login(ec["user"], ec["password"])
                    server.sendmail(ec["user"], ec["to"], msg.as_string())
            log.info("email alert sent", subject=subject)
        except OSError as exc:
            if getattr(exc, "errno", None) in (101, 111, 110):
                log.error(
                    "email send failed — SMTP port blocked by hosting platform. "
                    "Switch provider to 'brevo' or 'sendgrid' in Settings.",
                    error=str(exc),
                )
            else:
                log.error("email send failed", error=str(exc))
        except Exception as exc:
            log.error("email send failed", error=str(exc))

    async def _send_webhook(self, message: str) -> None:
        """Send a webhook POST (Discord/Slack format)."""
        wc = self._get_webhook_cfg()
        if not wc["url"]:
            log.warning("webhook not configured — set NOTIFY_WEBHOOK_URL")
            return
        try:
            import aiohttp
            payload = {"content": message}  # Discord format
            async with aiohttp.ClientSession() as session:
                async with session.post(wc["url"], json=payload) as resp:
                    if resp.status not in (200, 204):
                        log.warning("webhook returned non-200", status=resp.status)
        except Exception as exc:
            log.error("webhook send failed", error=str(exc))

    async def send(self, subject: str, body: str) -> None:
        """Send alert via all configured channels (non-blocking)."""
        tasks = []
        if self._get_email_cfg()["enabled"]:
            loop = asyncio.get_event_loop()
            tasks.append(loop.run_in_executor(None, self._send_email_sync, subject, body))
        if self._get_webhook_cfg()["enabled"]:
            tasks.append(self._send_webhook(f"**{subject}**\n{body}"))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def signal(self, symbol: str, direction: str, strike: float,
                     expiry: str, entry: float, stop: float, target: float,
                     rationale: str) -> None:
        subject = f"[ALGO-TRADE] Signal: {direction} {symbol}"
        body = (
            f"Symbol    : {symbol}\n"
            f"Direction : {direction}\n"
            f"Strike    : {strike}  Expiry: {expiry}\n"
            f"Entry     : ${entry:.2f}\n"
            f"Stop      : ${stop:.2f}\n"
            f"Target    : ${target:.2f}\n"
            f"Rationale : {rationale}\n"
        )
        await self.send(subject, body)

    async def filled(self, symbol: str, side: str, qty: int,
                     fill_price: float, order_id: str) -> None:
        subject = f"[ALGO-TRADE] Filled: {side} {symbol}"
        body = (
            f"Order ID  : {order_id}\n"
            f"Symbol    : {symbol}\n"
            f"Side      : {side}\n"
            f"Quantity  : {qty} contracts\n"
            f"Fill price: ${fill_price:.2f}\n"
        )
        await self.send(subject, body)

    async def closed(self, symbol: str, reason: str, entry: float,
                     exit_price: float, pnl: float) -> None:
        emoji = "PROFIT" if pnl >= 0 else "LOSS"
        subject = f"[ALGO-TRADE] Closed ({emoji}): {symbol}"
        body = (
            f"Symbol    : {symbol}\n"
            f"Reason    : {reason}\n"
            f"Entry     : ${entry:.2f}\n"
            f"Exit      : ${exit_price:.2f}\n"
            f"P&L       : ${pnl:+.2f}\n"
        )
        await self.send(subject, body)

    async def startup(self, mode: str) -> None:
        subject = "[ALGO-TRADE] System Started"
        body = f"Trading system started in {mode} mode."
        await self.send(subject, body)

    async def shutdown(self) -> None:
        subject = "[ALGO-TRADE] System Shutdown"
        body = "Trading system has shut down gracefully."
        await self.send(subject, body)

    async def circuit_breaker(self, adapter_name: str, reason: str) -> None:
        subject = f"[ALGO-TRADE] Circuit Breaker: {adapter_name}"
        body = f"Adapter: {adapter_name}\nReason:  {reason}\n"
        await self.send(subject, body)
