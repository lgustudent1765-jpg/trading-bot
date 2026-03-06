# file: tests/test_indicators.py
"""
Unit tests for indicator functions (RSI, MACD, ATR).

All tests are pure: no I/O, no network, no randomness.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.indicators.atr import atr
from src.indicators.macd import macd
from src.indicators.rsi import rsi, rsi_series


# ------------------------------------------------------------------ #
# RSI                                                                 #
# ------------------------------------------------------------------ #

class TestRSI:
    def test_basic_uptrend_gives_high_rsi(self):
        """Monotonically increasing prices should give RSI near 100."""
        closes = list(range(1, 20))  # 1, 2, ..., 19
        result = rsi(closes, period=14)
        assert result > 80, f"Expected RSI > 80 for uptrend, got {result:.1f}"

    def test_basic_downtrend_gives_low_rsi(self):
        """Monotonically decreasing prices should give RSI near 0."""
        closes = list(range(20, 1, -1))  # 20, 19, ..., 2
        result = rsi(closes, period=14)
        assert result < 20, f"Expected RSI < 20 for downtrend, got {result:.1f}"

    def test_all_same_prices_raises_or_returns_boundary(self):
        """Flat prices: avg_loss == 0, so RSI should be 100."""
        closes = [100.0] * 20
        result = rsi(closes, period=14)
        assert result == 100.0

    def test_insufficient_data_raises_value_error(self):
        with pytest.raises(ValueError, match="at least"):
            rsi([1.0, 2.0, 3.0], period=14)

    def test_result_in_valid_range(self):
        """RSI must always be in [0, 100]."""
        np.random.seed(42)
        closes = np.cumsum(np.random.randn(100)) + 100
        result = rsi(closes.tolist(), period=14)
        assert 0.0 <= result <= 100.0

    def test_rsi_series_length_matches_input(self):
        closes = list(range(1, 31))
        series = rsi_series(closes, period=14)
        assert len(series) == len(closes)

    def test_rsi_series_first_values_are_nan(self):
        closes = list(range(1, 31))
        series = rsi_series(closes, period=14)
        assert np.all(np.isnan(series[:14]))

    def test_rsi_overbought_threshold(self):
        """Verify RSI > 70 on data engineered to be overbought."""
        base = 100.0
        closes = [base]
        for _ in range(25):
            closes.append(closes[-1] * 1.02)  # +2% each bar
        result = rsi(closes, period=14)
        assert result > 70, f"Expected RSI > 70, got {result:.1f}"


# ------------------------------------------------------------------ #
# MACD                                                                #
# ------------------------------------------------------------------ #

class TestMACD:
    def test_uptrend_gives_positive_histogram(self):
        """In a persistent uptrend, MACD histogram should be positive."""
        closes = [100.0 + i * 0.5 for i in range(50)]
        result = macd(closes)
        assert result.histogram > 0, f"Expected histogram > 0, got {result.histogram:.4f}"

    def test_downtrend_gives_negative_histogram(self):
        closes = [150.0 - i * 0.5 for i in range(50)]
        result = macd(closes)
        assert result.histogram < 0, f"Expected histogram < 0, got {result.histogram:.4f}"

    def test_insufficient_data_raises(self):
        with pytest.raises(ValueError, match="at least"):
            macd([1.0] * 10)  # needs >= 35 (26 + 9)

    def test_result_fields_are_floats(self):
        closes = list(range(1, 60))
        result = macd(closes)
        assert isinstance(result.macd_line, float)
        assert isinstance(result.signal_line, float)
        assert isinstance(result.histogram, float)

    def test_histogram_equals_macd_minus_signal(self):
        closes = list(range(1, 60))
        result = macd(closes)
        assert abs(result.histogram - (result.macd_line - result.signal_line)) < 1e-9


# ------------------------------------------------------------------ #
# ATR                                                                 #
# ------------------------------------------------------------------ #

class TestATR:
    def _make_bars(self, n: int = 20, spread: float = 1.0):
        closes = [100.0 + i * 0.1 for i in range(n)]
        highs  = [c + spread for c in closes]
        lows   = [c - spread for c in closes]
        return highs, lows, closes

    def test_atr_is_positive(self):
        h, l, c = self._make_bars()
        result = atr(h, l, c, period=14)
        assert result > 0

    def test_atr_roughly_equals_bar_range(self):
        """When H-L is constant and no gaps, ATR ~ spread * 2."""
        h, l, c = self._make_bars(spread=2.0)
        result = atr(h, l, c, period=14)
        assert 3.5 < result < 5.0, f"Unexpected ATR: {result:.4f}"

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="same length"):
            atr([100, 101], [99, 100], [100])

    def test_insufficient_data_raises(self):
        with pytest.raises(ValueError, match="at least"):
            atr([100] * 5, [99] * 5, [100] * 5, period=14)
