# file: src/indicators/rsi.py
"""
Relative Strength Index (RSI) — pure, stateless implementation.

References: Wilder (1978).  Uses simple-average (Cutler's) variant for
reproducibility in unit tests; not the exponential-smoothed variant.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def rsi(closes: Sequence[float], period: int = 14) -> float:
    """
    Compute RSI for a series of close prices.

    Parameters
    ----------
    closes : sequence of floats, length >= period + 1
    period : look-back window (default 14)

    Returns
    -------
    float
        RSI value in the range [0, 100].

    Raises
    ------
    ValueError
        When fewer than *period + 1* data points are supplied.

    Complexity: O(n) time, O(n) space (dominated by np.diff allocation).
    Concurrency: pure function; thread-safe and async-safe.
    """
    arr = np.asarray(closes, dtype=float)
    if len(arr) < period + 1:
        raise ValueError(
            f"rsi requires at least {period + 1} data points, got {len(arr)}"
        )

    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = gains[-period:].mean()
    avg_loss = losses[-period:].mean()

    if avg_loss == 0.0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def rsi_series(closes: Sequence[float], period: int = 14) -> np.ndarray:
    """
    Return RSI for every bar that has sufficient history.

    The first *period* values of the output are NaN.

    Parameters
    ----------
    closes : sequence of floats
    period : look-back window

    Returns
    -------
    numpy.ndarray of shape (len(closes),)
    """
    arr = np.asarray(closes, dtype=float)
    result = np.full(len(arr), np.nan)
    for i in range(period, len(arr)):
        result[i] = rsi(arr[: i + 1], period)
    return result
