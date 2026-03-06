# file: tests/test_options_fetcher.py
"""
Unit tests for the options fetcher and liquidity filter.

Uses synthetic option chains; no broker or network access.
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from src.events import OptionContract
from src.options_fetcher.fetcher import apply_liquidity_filter, _days_to_expiry


def _make_contract(
    symbol: str = "AAPL",
    expiry_days: int = 14,
    strike: float = 150.0,
    spot: float = 150.0,
    opt_type: str = "call",
    bid: float = 2.0,
    ask: float = 2.10,
    volume: int = 500,
    open_interest: int = 2000,
    iv: float = 0.35,
) -> OptionContract:
    expiry = (date.today() + timedelta(days=expiry_days)).isoformat()
    return OptionContract(
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        option_type=opt_type,
        bid=bid,
        ask=ask,
        volume=volume,
        open_interest=open_interest,
        implied_volatility=iv,
        underlying_price=spot,
    )


class TestLiquidityFilter:
    def test_all_pass_filter(self):
        contracts = [_make_contract()]
        result = apply_liquidity_filter(contracts, spot=150.0)
        assert len(result) == 1

    def test_low_volume_excluded(self):
        c = _make_contract(volume=10)
        result = apply_liquidity_filter([c], spot=150.0, min_volume=100)
        assert len(result) == 0

    def test_low_oi_excluded(self):
        c = _make_contract(open_interest=100)
        result = apply_liquidity_filter([c], spot=150.0, min_open_interest=500)
        assert len(result) == 0

    def test_wide_spread_excluded(self):
        # bid=1.0, ask=2.0 -> spread_pct = 1.0/1.5 = 0.67 > 0.10
        c = _make_contract(bid=1.0, ask=2.0)
        result = apply_liquidity_filter([c], spot=150.0, max_spread_pct=0.10)
        assert len(result) == 0

    def test_far_dated_excluded(self):
        c = _make_contract(expiry_days=60)
        result = apply_liquidity_filter([c], spot=150.0, max_dte=30)
        assert len(result) == 0

    def test_same_day_expiry_excluded(self):
        c = _make_contract(expiry_days=0)
        result = apply_liquidity_filter([c], spot=150.0, min_dte=1)
        assert len(result) == 0

    def test_far_otm_excluded(self):
        # strike 200 on spot 150 = 33% OTM
        c = _make_contract(strike=200.0, spot=150.0)
        result = apply_liquidity_filter([c], spot=150.0, max_otm_pct=0.15)
        assert len(result) == 0

    def test_near_atm_passes(self):
        # strike 155 on spot 150 = 3.3% OTM (< 15%)
        c = _make_contract(strike=155.0, spot=150.0)
        result = apply_liquidity_filter([c], spot=150.0, max_otm_pct=0.15)
        assert len(result) == 1

    def test_mixed_chain_filtered_correctly(self):
        """Only the liquid ATM contract should survive."""
        good = _make_contract(strike=150.0, volume=1000, open_interest=5000)
        bad_volume = _make_contract(strike=145.0, volume=5)
        bad_spread = _make_contract(strike=155.0, bid=0.10, ask=5.0)
        bad_dte = _make_contract(strike=150.0, expiry_days=90)

        result = apply_liquidity_filter(
            [good, bad_volume, bad_spread, bad_dte],
            spot=150.0,
            min_volume=100,
            min_open_interest=500,
            max_spread_pct=0.10,
            max_dte=30,
        )
        assert len(result) == 1
        assert result[0].strike == 150.0

    def test_days_to_expiry_calculation(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        assert _days_to_expiry(tomorrow) == 1

    def test_days_to_expiry_past_date(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        assert _days_to_expiry(yesterday) == 0
