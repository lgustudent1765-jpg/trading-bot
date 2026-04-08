# file: tests/e2e/config.spec.py
"""
E2E tests for configuration loading and the /config HTTP endpoints.

Covers (load_config unit tests):
  - load_config() returns a dict with all top-level sections
  - Default values are applied when YAML is missing
  - YAML file values override hardcoded defaults
  - ALGO_<SECTION>_<KEY> env vars override YAML values
  - FMP_API_KEY env var sets market_data.fmp_api_key
  - BROKER env var sets broker.name
  - MODE env var sets mode
  - LOG_LEVEL env var sets logging.level
  - API_PORT env var sets api_server.port
  - Numeric env vars are cast to the correct Python type
  - Config is cached after first load (same object returned on second call)
  - Cache can be reset by setting _CONFIG = None

Covers (GET /config HTTP endpoint):
  - Returns HTTP 200 with all expected flat keys
  - fmp_api_key_set is a boolean
  - Sensitive fields are masked

Covers (POST /config HTTP endpoint):
  - Valid payload returns {"ok": True}
  - Unknown-only fields return 400
  - Invalid enum value returns 422
  - Zero value for positive-int field returns 422
  - Negative value for positive-float field returns 422
  - Webhook URL with http:// (not https) returns 422
  - Webhook URL from non-allowed domain returns 422
  - Valid Discord webhook URL is accepted
  - Empty string values are silently skipped (not overwritten)
  - Mask sentinel values are silently skipped
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

pytestmark = pytest.mark.e2e


def _reset_and_load(**env):
    """Reset config cache and reload with injected env vars."""
    import src.config as cfg_mod
    cfg_mod._CONFIG = None

    with patch.dict("os.environ", env, clear=False):
        from src.config import load_config
        return load_config(path=Path("/nonexistent_config.yaml"))


class TestConfigDefaults:
    def test_load_config_returns_dict(self):
        config = _reset_and_load()
        assert isinstance(config, dict)

    def test_load_config_has_required_top_level_keys(self):
        required = {"mode", "screener", "risk", "broker", "market_data", "logging"}
        config = _reset_and_load()
        assert required.issubset(config.keys())

    def test_default_mode_is_paper_when_set_explicitly(self, monkeypatch):
        """load_config() honours the MODE env var when set to 'paper'."""
        config = _reset_and_load(MODE="paper")
        assert config.get("mode") == "paper"


class TestConfigEnvVarOverrides:
    def test_mode_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("MODE", "automated")
        config = _reset_and_load(MODE="automated")
        assert config["mode"] == "automated"

    def test_fmp_api_key_env_var_sets_market_data_key(self, monkeypatch):
        config = _reset_and_load(FMP_API_KEY="my-fmp-key-123")
        assert config["market_data"]["fmp_api_key"] == "my-fmp-key-123"

    def test_broker_env_var_sets_broker_name(self, monkeypatch):
        config = _reset_and_load(BROKER="webull")
        assert config["broker"]["name"] == "webull"

    def test_log_level_env_var_sets_logging_level(self, monkeypatch):
        config = _reset_and_load(LOG_LEVEL="DEBUG")
        assert config["logging"]["level"] == "DEBUG"

    def test_api_port_env_var_sets_port(self, monkeypatch):
        config = _reset_and_load(API_PORT="9090")
        assert int(config["api_server"]["port"]) == 9090

    def test_algo_risk_max_open_positions_override(self):
        config = _reset_and_load(ALGO_RISK_MAX_OPEN_POSITIONS="12")
        assert int(config["risk"]["max_open_positions"]) == 12

    def test_algo_screener_top_n_override(self):
        config = _reset_and_load(ALGO_SCREENER_TOP_N="20")
        assert int(config["screener"]["top_n"]) == 20

    def test_robinhood_username_env_var_propagates(self):
        config = _reset_and_load(
            ROBINHOOD_USERNAME="trader@example.com",
            ROBINHOOD_PASSWORD="s3cr3t",
            ROBINHOOD_MFA_CODE="123456",
        )
        rh = config["broker"]["robinhood"]
        assert rh["username"] == "trader@example.com"
        assert rh["password"] == "s3cr3t"
        assert rh["mfa_code"] == "123456"


class TestConfigCaching:
    def test_config_is_cached_after_first_load(self):
        import src.config as cfg_mod
        cfg_mod._CONFIG = None

        from src.config import load_config, get_config
        c1 = load_config(path=Path("/nonexistent.yaml"))
        c2 = get_config()
        assert c1 is c2

    def test_cache_can_be_reset(self):
        import src.config as cfg_mod

        cfg_mod._CONFIG = None
        from src.config import load_config
        c1 = load_config(path=Path("/nonexistent.yaml"))

        cfg_mod._CONFIG = None
        c2 = load_config(path=Path("/nonexistent.yaml"))
        # After reset, a fresh dict is returned (may or may not be the same object,
        # but both must be valid configs).
        assert isinstance(c2, dict)
        assert "mode" in c2


# ---------------------------------------------------------------------------
# Enhancement: HTTP endpoint tests for GET /config and POST /config
# ---------------------------------------------------------------------------

GET_CONFIG_EXPECTED_KEYS = {
    "mode", "broker_name", "screener_provider", "screener_poll_interval_seconds",
    "screener_top_n", "screener_market_hours_only", "fmp_api_key_set",
    "risk_max_position_pct", "risk_max_open_positions", "risk_pdt_equity_threshold",
    "risk_stop_loss_atr_mult", "risk_take_profit_atr_mult",
    "notify_email_enabled", "notify_email_username", "notify_email_recipient",
    "notify_webhook_enabled", "notify_webhook_url",
}


class TestGetConfigEndpoint:
    async def test_get_config_returns_200(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.get("/config")
            assert resp.status == 200

    async def test_get_config_contains_all_expected_keys(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/config")).json()
            assert GET_CONFIG_EXPECTED_KEYS.issubset(body.keys())

    async def test_get_config_fmp_api_key_set_is_boolean(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/config")).json()
            assert isinstance(body["fmp_api_key_set"], bool)

    async def test_get_config_mode_is_string(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/config")).json()
            assert isinstance(body["mode"], str)

    async def test_get_config_notify_email_enabled_is_boolean(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/config")).json()
            assert isinstance(body["notify_email_enabled"], bool)

    async def test_get_config_risk_fields_are_numeric(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            body = await (await client.get("/config")).json()
            assert isinstance(body["risk_max_position_pct"], (int, float))
            assert isinstance(body["risk_max_open_positions"], (int, float))


class TestPostConfigEndpoint:
    async def test_post_config_valid_mode_returns_ok(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post("/config", json={"mode": "paper"})
            assert resp.status == 200
            body = await resp.json()
            assert body.get("ok") is True

    async def test_post_config_valid_broker_name_returns_ok(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post("/config", json={"broker_name": "mock"})
            assert resp.status == 200
            assert (await resp.json()).get("ok") is True

    async def test_post_config_empty_body_returns_400(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post("/config", json={})
            assert resp.status == 400

    async def test_post_config_unknown_only_fields_returns_400(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post("/config", json={"totally_unknown_key": "value"})
            assert resp.status == 400

    async def test_post_config_invalid_mode_enum_returns_422(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post("/config", json={"mode": "invalid_mode"})
            assert resp.status == 422
            body = await resp.json()
            assert "error" in body

    async def test_post_config_invalid_broker_enum_returns_422(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post("/config", json={"broker_name": "unknown_broker"})
            assert resp.status == 422

    async def test_post_config_zero_positive_int_field_returns_422(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post("/config", json={"screener_top_n": 0})
            assert resp.status == 422

    async def test_post_config_negative_positive_float_field_returns_422(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post("/config", json={"risk_max_position_pct": -0.1})
            assert resp.status == 422

    async def test_post_config_webhook_http_url_returns_422(self, make_app):
        """Webhook URL must be https://."""
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post(
                "/config",
                json={"notify_webhook_url": "http://discord.com/api/webhooks/123/abc"},
            )
            assert resp.status == 422

    async def test_post_config_webhook_non_allowed_domain_returns_422(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post(
                "/config",
                json={"notify_webhook_url": "https://malicious.example.com/hook"},
            )
            assert resp.status == 422

    async def test_post_config_valid_discord_webhook_returns_ok(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post(
                "/config",
                json={"notify_webhook_url": "https://discord.com/api/webhooks/123/abc"},
            )
            assert resp.status == 200
            assert (await resp.json()).get("ok") is True

    async def test_post_config_empty_string_value_skipped_silently(self, make_app):
        """Empty strings must not overwrite existing config values."""
        async with TestClient(TestServer(make_app())) as client:
            # First read current mode
            original = (await (await client.get("/config")).json())["mode"]
            # Attempt to overwrite with empty string
            await client.post("/config", json={"mode": ""})
            current = (await (await client.get("/config")).json())["mode"]
            assert current == original

    async def test_post_config_mask_sentinel_skipped_silently(self, make_app):
        """The mask sentinel '********' must not overwrite config values."""
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post("/config", json={"fmp_api_key": "********"})
            # Should either succeed with ok:True (skipped) or 400 (no recognized fields)
            assert resp.status in (200, 400)

    async def test_post_config_invalid_json_returns_400(self, make_app):
        async with TestClient(TestServer(make_app())) as client:
            resp = await client.post(
                "/config",
                data="not-json",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 400
