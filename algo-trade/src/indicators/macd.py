# file: src/indicators/macd.py
"""
Moving Average Convergence/Divergence (MACD) — pure numpy implementation.

Uses exponential weighted moving average (EWM) computed via numpy for
performance and zero dependency on pandas.
"""

from __future__ import annotations

from typing import NamedTuple, Sequence

import numpy as np


class MACDResult(NamedTuple):
    """Container for a single-bar MACD snapshot."""
    macd_line: float    # fast_ema - slow_ema
    signal_line: float  # EMA of macd_line
    histogram: float    # macd_line - signal_line


def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    """
    Compute exponential moving average with adjust=False convention.

    alpha = 2 / (span + 1)
    EMA[0] = arr[0]
    EMA[i] = alpha * arr[i] + (1 - alpha) * EMA[i-1]

    Complexity: O(n).  Thread-safe pure function.
    """
    alpha = 2.0 / (span + 1)
    out = np.empty_like(arr, dtype=float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


def macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> MACDResult:
    """
    Compute MACD, signal line, and histogram for the last bar.

    Parameters
    ----------
    closes : sequence of floats, length >= slow + signal
    fast   : fast EMA period (default 12)
    slow   : slow EMA period (default 26)
    signal : signal EMA period (default 9)

    Returns
    -------
    MACDResult (macd_line, signal_line, histogram)

    Raises
    ------
    ValueError
        When fewer than *slow + signal* data points are supplied.

    Complexity: O(n).  Concurrency: pure, thread-safe.
    """
    required = slow + signal
    arr = np.asarray(closes, dtype=float)
    if len(arr) < required:
        raise ValueError(
            f"macd requires at least {required} data points, got {len(arr)}"
        )

    fast_ema = _ema(arr, fast)
    slow_ema = _ema(arr, slow)
    macd_line = fast_ema - slow_ema
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line

    return MACDResult(
        macd_line=float(macd_line[-1]),
        signal_line=float(signal_line[-1]),
        histogram=float(histogram[-1]),
    )
