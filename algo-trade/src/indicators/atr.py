# file: src/indicators/atr.py
"""
Average True Range (ATR) — pure implementation.

Used by the strategy engine to set stop-loss / take-profit distances.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float:
    """
    Compute the Average True Range for the most recent bar.

    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR        = simple average of TR over *period* bars.

    Parameters
    ----------
    highs   : bar high prices, length >= period + 1
    lows    : bar low prices, same length
    closes  : bar close prices, same length
    period  : look-back window (default 14)

    Returns
    -------
    float — ATR value >= 0.

    Raises
    ------
    ValueError
        If input arrays have inconsistent lengths or insufficient data.

    Complexity: O(n).  Concurrency: pure, thread-safe.
    """
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)
    c = np.asarray(closes, dtype=float)

    if not (len(h) == len(l) == len(c)):
        raise ValueError("highs, lows, closes must have the same length")
    if len(h) < period + 1:
        raise ValueError(
            f"atr requires at least {period + 1} data points, got {len(h)}"
        )

    prev_close = c[:-1]
    curr_high = h[1:]
    curr_low = l[1:]

    tr = np.maximum(
        curr_high - curr_low,
        np.maximum(
            np.abs(curr_high - prev_close),
            np.abs(curr_low - prev_close),
        ),
    )
    return float(tr[-period:].mean())
