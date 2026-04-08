# file: tests/e2e/notifier.spec.py
"""
E2E tests for the Notifier component (email + webhook channels).

All external I/O (SMTP, HTTP) is mocked.

Covers:
  - send() skips email when email.enabled=False
  - send() skips webhook when webhook.enabled=False
  - send() calls email sender when email.enabled=True and credentials set
  - send() calls webhook poster when webhook.enabled=True and URL set
  - signal() composes and sends correct subject/body
  - filled() composes subject with BUY/SELL and order ID
  - closed() uses PROFIT/LOSS label based on PnL sign
  - startup() sends correct mode string
  - shutdown() sends shutdown message
  - circuit_breaker() sends alert with adapter name and reason
  - email sender swallows SMTP errors without raising
  - webhook poster swallows HTTP errors without raising
  - _send_email_sync() skips when credentials are empty
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.notifier import Notifier

pytestmark = pytest.mark.e2e


def _config(email_enabled=False, webhook_enabled=False, webhook_url=""):
    return {
        "notifications": {
            "email": {
                "enabled": email_enabled,
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "username": "test@gmail.com" if email_enabled else "",
                "password": "app-password" if email_enabled else "",
                "recipient": "recipient@example.com",
            },
            "webhook": {
                "enabled": webhook_enabled,
                "url": webhook_url,
            },
        }
    }


class TestNotifierChannelGating:
    async def test_send_skips_email_when_disabled(self):
        notifier = Notifier(_config(email_enabled=False))
        with patch.object(notifier, "_send_email_sync") as mock_email:
            await notifier.send("subject", "body")
            mock_email.assert_not_called()

    async def test_send_skips_webhook_when_disabled(self):
        notifier = Notifier(_config(webhook_enabled=False))
        with patch.object(notifier, "_send_webhook") as mock_wh:
            await notifier.send("subject", "body")
            mock_wh.assert_not_called()

    async def test_send_triggers_email_when_enabled(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_EMAIL_USER", "user@gmail.com")
        monkeypatch.setenv("NOTIFY_EMAIL_PASS", "app-password")
        notifier = Notifier(_config(email_enabled=True))
        notifier._email_user = "user@gmail.com"
        notifier._email_pass = "app-password"

        with patch.object(notifier, "_send_email_sync") as mock_email:
            await notifier.send("Test subject", "Test body")
            mock_email.assert_called_once_with("Test subject", "Test body")

    async def test_send_triggers_webhook_when_enabled_with_url(self):
        notifier = Notifier(_config(webhook_enabled=True, webhook_url="http://fake.webhook"))
        with patch.object(notifier, "_send_webhook", new=AsyncMock()) as mock_wh:
            await notifier.send("subject", "body")
            mock_wh.assert_called_once()


class TestNotifierMessageComposition:
    async def test_signal_alert_subject_contains_direction_and_symbol(self):
        notifier = Notifier(_config())
        sent_subjects = []

        async def capture_send(subject, body):
            sent_subjects.append(subject)

        notifier.send = capture_send
        await notifier.signal(
            symbol="AAPL", direction="CALL", strike=175.0,
            expiry="2026-05-16", entry=2.55, stop=1.85, target=4.15,
            rationale="RSI=72.3"
        )
        assert len(sent_subjects) == 1
        assert "CALL" in sent_subjects[0]
        assert "AAPL" in sent_subjects[0]

    async def test_signal_alert_body_contains_key_fields(self):
        notifier = Notifier(_config())
        sent_bodies = []

        async def capture_send(subject, body):
            sent_bodies.append(body)

        notifier.send = capture_send
        await notifier.signal(
            symbol="AAPL", direction="CALL", strike=175.0,
            expiry="2026-05-16", entry=2.55, stop=1.85, target=4.15,
            rationale="RSI=72.3"
        )
        body = sent_bodies[0]
        assert "175.0" in body   # strike
        assert "2.55" in body    # entry
        assert "1.85" in body    # stop

    async def test_filled_subject_contains_side_and_symbol(self):
        notifier = Notifier(_config())
        sent = []
        notifier.send = AsyncMock(side_effect=lambda s, b: sent.append((s, b)))
        await notifier.filled("AAPL", "BUY", qty=10, fill_price=2.55, order_id="ord-001")
        assert "BUY" in sent[0][0]
        assert "AAPL" in sent[0][0]

    async def test_filled_body_contains_order_id(self):
        notifier = Notifier(_config())
        bodies = []
        notifier.send = AsyncMock(side_effect=lambda s, b: bodies.append(b))
        await notifier.filled("AAPL", "BUY", qty=10, fill_price=2.55, order_id="ord-XYZ")
        assert "ord-XYZ" in bodies[0]

    async def test_closed_subject_contains_profit_label_for_positive_pnl(self):
        notifier = Notifier(_config())
        sent = []
        notifier.send = AsyncMock(side_effect=lambda s, b: sent.append((s, b)))
        await notifier.closed("AAPL", "TAKE_PROFIT", entry=2.00, exit_price=3.50, pnl=150.0)
        assert "PROFIT" in sent[0][0]

    async def test_closed_subject_contains_loss_label_for_negative_pnl(self):
        notifier = Notifier(_config())
        sent = []
        notifier.send = AsyncMock(side_effect=lambda s, b: sent.append((s, b)))
        await notifier.closed("AAPL", "STOP_LOSS", entry=2.00, exit_price=1.50, pnl=-50.0)
        assert "LOSS" in sent[0][0]

    async def test_startup_body_contains_mode(self):
        notifier = Notifier(_config())
        bodies = []
        notifier.send = AsyncMock(side_effect=lambda s, b: bodies.append(b))
        await notifier.startup("paper")
        assert "PAPER" in bodies[0].upper() or "paper" in bodies[0]

    async def test_shutdown_sends_non_empty_message(self):
        notifier = Notifier(_config())
        sent = []
        notifier.send = AsyncMock(side_effect=lambda s, b: sent.append((s, b)))
        await notifier.shutdown()
        assert len(sent) == 1
        assert len(sent[0][1]) > 0

    async def test_circuit_breaker_contains_adapter_name_in_subject(self):
        notifier = Notifier(_config())
        sent = []
        notifier.send = AsyncMock(side_effect=lambda s, b: sent.append((s, b)))
        await notifier.circuit_breaker("FMPMarketAdapter", "too many errors")
        assert "FMPMarketAdapter" in sent[0][0]


class TestNotifierErrorHandling:
    def test_email_sender_swallows_smtp_errors(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_EMAIL_USER", "user@gmail.com")
        monkeypatch.setenv("NOTIFY_EMAIL_PASS", "bad-pass")
        notifier = Notifier(_config(email_enabled=True))
        notifier._email_user = "user@gmail.com"
        notifier._email_pass = "bad-pass"

        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("connection refused")):
            # Must not raise
            notifier._send_email_sync("subject", "body")

    def test_email_sender_skips_when_no_credentials(self):
        notifier = Notifier(_config(email_enabled=False))
        notifier._email_user = ""
        notifier._email_pass = ""
        with patch("smtplib.SMTP") as mock_smtp:
            notifier._send_email_sync("subject", "body")
            mock_smtp.assert_not_called()

    async def test_webhook_sender_swallows_http_errors(self):
        notifier = Notifier(_config(webhook_enabled=True, webhook_url="http://fake.webhook"))

        async def _fake_post(*args, **kwargs):
            raise ConnectionError("no network")

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session.return_value.post.side_effect = ConnectionError("no network")
            # Must not raise
            await notifier._send_webhook("test message")
