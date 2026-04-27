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


class TestIVFilter:
    def test_normal_iv_passes(self):
        c = _make_contract(iv=0.35)
        result = apply_liquidity_filter([c], spot=150.0, min_iv=0.10, max_iv=0.80)
        assert len(result) == 1

    def test_high_iv_excluded(self):
        """IV=1.50 (150%) is overpriced — theta will destroy the position."""
        c = _make_contract(iv=1.50)
        result = apply_liquidity_filter([c], spot=150.0, min_iv=0.10, max_iv=0.80)
        assert len(result) == 0

    def test_low_iv_excluded(self):
        """IV=0.05 (5%) has almost no premium — correct move won't pay."""
        c = _make_contract(iv=0.05)
        result = apply_liquidity_filter([c], spot=150.0, min_iv=0.10, max_iv=0.80)
        assert len(result) == 0

    def test_iv_at_max_boundary_passes(self):
        """IV exactly at the max (0.80) should pass."""
        c = _make_contract(iv=0.80)
        result = apply_liquidity_filter([c], spot=150.0, min_iv=0.10, max_iv=0.80)
        assert len(result) == 1

    def test_iv_at_min_boundary_passes(self):
        """IV exactly at the min (0.10) should pass."""
        c = _make_contract(iv=0.10)
        result = apply_liquidity_filter([c], spot=150.0, min_iv=0.10, max_iv=0.80)
        assert len(result) == 1

    def test_zero_iv_skips_check(self):
        """IV=0 means broker didn't supply it — don't filter based on missing data."""
        c = _make_contract(iv=0.0)
        result = apply_liquidity_filter([c], spot=150.0, min_iv=0.10, max_iv=0.80)
        assert len(result) == 1

    def test_mixed_iv_chain(self):
        """Only contracts in the IV window survive."""
        cheap = _make_contract(strike=148.0, iv=0.35)   # good
        pricey = _make_contract(strike=150.0, iv=0.95)  # too expensive
        stale = _make_contract(strike=152.0, iv=0.04)   # too low
        result = apply_liquidity_filter(
            [cheap, pricey, stale], spot=150.0, min_iv=0.10, max_iv=0.80
        )
        assert len(result) == 1
        assert result[0].strike == 148.0
