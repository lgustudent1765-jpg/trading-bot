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

log = get_logger(__name__)


class Notifier:
    """
    Sends alerts via email and/or webhook.

    All sends are non-blocking (run in thread executor) so they never
    stall the asyncio event loop.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        notif = config.get("notifications", {})

        email_cfg = notif.get("email", {})
        self._email_enabled: bool = email_cfg.get("enabled", False)
        self._smtp_host: str = email_cfg.get("smtp_host", "smtp.gmail.com")
        self._smtp_port: int = int(email_cfg.get("smtp_port", 587))
        self._email_user: str = os.getenv("NOTIFY_EMAIL_USER", email_cfg.get("username", ""))
        self._email_pass: str = os.getenv("NOTIFY_EMAIL_PASS", email_cfg.get("password", ""))
        self._email_to: str = email_cfg.get("recipient", self._email_user)

        webhook_cfg = notif.get("webhook", {})
        self._webhook_enabled: bool = webhook_cfg.get("enabled", False)
        self._webhook_url: str = os.getenv("NOTIFY_WEBHOOK_URL", webhook_cfg.get("url", ""))

    def _send_email_sync(self, subject: str, body: str) -> None:
        """Synchronous email send — called from thread executor."""
        if not self._email_user or not self._email_pass:
            log.warning("email not configured — set NOTIFY_EMAIL_USER and NOTIFY_EMAIL_PASS")
            return
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self._email_user
            msg["To"] = self._email_to

            context = ssl.create_default_context()
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.starttls(context=context)
                server.login(self._email_user, self._email_pass)
                server.sendmail(self._email_user, self._email_to, msg.as_string())
            log.info("email alert sent", subject=subject)
        except Exception as exc:
            log.error("email send failed", error=str(exc))

    async def _send_webhook(self, message: str) -> None:
        """Send a webhook POST (Discord/Slack format)."""
        if not self._webhook_url:
            log.warning("webhook not configured — set NOTIFY_WEBHOOK_URL")
            return
        try:
            import aiohttp
            payload = {"content": message}  # Discord format
            async with aiohttp.ClientSession() as session:
                async with session.post(self._webhook_url, json=payload) as resp:
                    if resp.status not in (200, 204):
                        log.warning("webhook returned non-200", status=resp.status)
        except Exception as exc:
            log.error("webhook send failed", error=str(exc))

    async def send(self, subject: str, body: str) -> None:
        """Send alert via all configured channels (non-blocking)."""
        tasks = []
        if self._email_enabled:
            loop = asyncio.get_event_loop()
            tasks.append(loop.run_in_executor(None, self._send_email_sync, subject, body))
        if self._webhook_enabled:
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
