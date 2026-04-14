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
        # Store initial config but always read live values from get_config() at send time.
        pass

    def _get_email_cfg(self):
        """Read live email config so Settings UI changes take effect without restart."""
        cfg = get_config()
        notif = cfg.get("notifications", {})
        email = notif.get("email", {})
        return {
            "enabled":   email.get("enabled", False),
            "smtp_host": email.get("smtp_host", "smtp.gmail.com"),
            "smtp_port": int(email.get("smtp_port", 587)),
            "user":      os.getenv("NOTIFY_EMAIL_USER") or email.get("username", ""),
            "password":  os.getenv("NOTIFY_EMAIL_PASS") or email.get("password", ""),
            "to":        email.get("recipient", "") or os.getenv("NOTIFY_EMAIL_USER") or email.get("username", ""),
        }

    def _get_webhook_cfg(self):
        """Read live webhook config so Settings UI changes take effect without restart."""
        cfg = get_config()
        notif = cfg.get("notifications", {})
        webhook = notif.get("webhook", {})
        return {
            "enabled": webhook.get("enabled", False),
            "url":     os.getenv("NOTIFY_WEBHOOK_URL", webhook.get("url", "")),
        }

    def _send_email_sync(self, subject: str, body: str) -> None:
        """Synchronous email send — called from thread executor."""
        ec = self._get_email_cfg()
        if not ec["user"] or not ec["password"]:
            log.warning("email not configured — set NOTIFY_EMAIL_USER and NOTIFY_EMAIL_PASS")
            return
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = ec["user"]
            msg["To"] = ec["to"]

            context = ssl.create_default_context()
            with smtplib.SMTP(ec["smtp_host"], ec["smtp_port"]) as server:
                server.starttls(context=context)
                server.login(ec["user"], ec["password"])
                server.sendmail(ec["user"], ec["to"], msg.as_string())
            log.info("email alert sent", subject=subject)
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
