# file: src/config.py
"""
Centralised configuration loader.

Reads config.yaml, then applies environment-variable overrides.
All modules import `get_config()` to access their settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


_CONFIG: Optional[Dict[str, Any]] = None
_CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "config.yaml"))


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Recursively merge *override* into *base*, returning a new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _apply_env_overrides(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply environment-variable overrides for critical keys.

    Naming convention: ALGO_<SECTION>_<KEY> (upper-cased).
    Example: ALGO_SCREENER_TOP_N=15 overrides cfg['screener']['top_n'].
    """
    prefix = "ALGO_"
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        parts = env_key[len(prefix):].lower().split("_", 1)
        if len(parts) == 2:
            section, key = parts
            if section in cfg and isinstance(cfg[section], dict):
                # Attempt numeric coercion.
                try:
                    cfg[section][key] = int(env_val)
                except ValueError:
                    try:
                        cfg[section][key] = float(env_val)
                    except ValueError:
                        cfg[section][key] = env_val
    return cfg


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load YAML configuration and apply environment overrides."""
    global _CONFIG
    config_path = path or _CONFIG_PATH
    if config_path.exists():
        with config_path.open() as fh:
            raw = yaml.safe_load(fh) or {}
    else:
        raw = {}

    # Provide hard-coded defaults so the system runs without a config file.
    defaults: Dict[str, Any] = {
        "mode": os.getenv("MODE", "paper"),
        "screener": {
            "top_n": 10,
            "poll_interval_seconds": 60,
            "provider": "fmp",
        },
        "options_filter": {
            "min_volume": 100,
            "min_open_interest": 500,
            "max_spread_pct": 0.10,
            "max_dte": 30,
            "min_dte": 1,
            "max_otm_pct": 0.15,
        },
        "indicators": {
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "atr_period": 14,
            "lookback_bars": 50,
        },
        "risk": {
            "max_position_pct": 0.05,
            "max_open_positions": 5,
            "pdt_equity_threshold": 25000,
            "stop_loss_atr_mult": 1.5,
            "take_profit_atr_mult": 3.0,
        },
        "broker": {
            "name": "mock",
            "webull": {
                "device_id": os.getenv("WEBULL_DEVICE_ID", ""),
                "access_token": os.getenv("WEBULL_ACCESS_TOKEN", ""),
                "refresh_token": os.getenv("WEBULL_REFRESH_TOKEN", ""),
                "trade_token": os.getenv("WEBULL_TRADE_TOKEN", ""),
                "account_id": os.getenv("WEBULL_ACCOUNT_ID", ""),
            },
        },
        "market_data": {
            "fmp_api_key": os.getenv("FMP_API_KEY", ""),
            "base_url": "https://financialmodelingprep.com/api/v3",
            "request_timeout": 10,
            "retry_max": 3,
            "retry_backoff": 2.0,
        },
        "logging": {
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "json_format": True,
            "log_file": os.getenv("LOG_FILE", ""),
        },
        "api_server": {
            "host": "0.0.0.0",
            "port": int(os.getenv("API_PORT", "8080")),
        },
    }

    merged = _deep_merge(defaults, raw)
    merged = _apply_env_overrides(merged)
    _CONFIG = merged
    return merged


def get_config() -> Dict[str, Any]:
    """Return the cached configuration, loading it on first call."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config()
    return _CONFIG
