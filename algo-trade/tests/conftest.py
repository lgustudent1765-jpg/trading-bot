# file: tests/conftest.py
"""
Shared pytest fixtures.

All tests run in isolation: no network calls, no file I/O outside tmp_path.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest


@pytest.fixture(scope="session")
def default_config() -> Dict[str, Any]:
    """Return a minimal in-memory configuration for tests."""
    return {
        "mode": "paper",
        "screener": {"top_n": 5, "poll_interval_seconds": 60, "provider": "mock"},
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
        "broker": {"name": "mock"},
        "market_data": {"fmp_api_key": "", "request_timeout": 5},
        "logging": {"level": "WARNING", "json_format": False},
        "api_server": {"host": "127.0.0.1", "port": 18080},
    }
