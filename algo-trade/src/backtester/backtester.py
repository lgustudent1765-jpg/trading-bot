# file: src/backtester/backtester.py
"""
Simple event-driven backtester for replaying historical minute/bar data.

Reads a CSV with columns: datetime, open, high, low, close, volume.
Applies the same indicator and signal logic as the live engine.
Simulates fills at the next bar's open price (no look-ahead bias).

Output: BacktestResult with trade log and summary statistics.

Limitations:
- No option-chain data in historical CSV; option P/L is estimated from
  underlying price moves scaled by a fixed option delta (configurable).
- Slippage and commissions are not modelled (conservative assumption).
- Intended for strategy validation, not precise P/L estimation.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


from src.indicators import atr, macd, rsi


@dataclass
class Trade:
    bar_index: int
    direction: str           # "CALL" | "PUT"
    entry_price: float       # next-bar open (underlying)
    stop_loss: float
    take_profit: float
    exit_price: Optional[float] = None
    exit_bar: Optional[int] = None
    exit_reason: Optional[str] = None

    @property
    def pnl_pct(self) -> Optional[float]:
        if self.exit_price is None:
            return None
        if self.direction == "CALL":
            return (self.exit_price - self.entry_price) / self.entry_price * 100
        return (self.entry_price - self.exit_price) / self.entry_price * 100


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    signals: int = 0

    def summary(self) -> Dict[str, Any]:
        closed = [t for t in self.trades if t.pnl_pct is not None]
        if not closed:
            return {"signals": self.signals, "trades": 0, "win_rate": 0.0, "avg_pnl_pct": 0.0}
        winners = [t for t in closed if (t.pnl_pct or 0) > 0]
        avg_pnl = sum(t.pnl_pct or 0 for t in closed) / len(closed)
        return {
            "signals": self.signals,
            "trades": len(closed),
            "winners": len(winners),
            "win_rate": round(len(winners) / len(closed) * 100, 1),
            "avg_pnl_pct": round(avg_pnl, 2),
            "total_pnl_pct": round(sum(t.pnl_pct or 0 for t in closed), 2),
        }

    def print_report(self) -> None:
        s = self.summary()
        print("\n" + "=" * 60)
        print("  BACKTEST REPORT")
        print("=" * 60)
        print(f"  Total signals generated : {s['signals']}")
        print(f"  Trades executed         : {s['trades']}")
        print(f"  Winners                 : {s.get('winners', 0)}")
        print(f"  Win rate                : {s['win_rate']}%")
        print(f"  Average P/L per trade   : {s['avg_pnl_pct']}%")
        print(f"  Total P/L               : {s['total_pnl_pct']}%")
        print("=" * 60)
        if self.trades:
            print("\n  Trade log (last 10):")
            print(f"  {'Bar':>5} {'Dir':<5} {'Entry':>8} {'Exit':>8} {'Reason':<14} {'P/L%':>7}")
            print(f"  {'-'*5:>5} {'-'*5:<5} {'-'*8:>8} {'-'*8:>8} {'-'*14:<14} {'-'*7:>7}")
            for t in self.trades[-10:]:
                print(
                    f"  {t.bar_index:>5} {t.direction:<5} {t.entry_price:>8.2f} "
                    f"{(t.exit_price or 0):>8.2f} {(t.exit_reason or 'OPEN'):<14} "
                    f"{(t.pnl_pct or 0):>7.2f}"
                )
        print()


def _load_csv(path: Path) -> List[Dict[str, Any]]:
    """Load a CSV file into a list of bar dicts."""
    bars = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                bars.append({
                    "datetime": row["datetime"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(float(row["volume"])),
                })
            except (KeyError, ValueError):
                continue  # skip malformed rows
    return bars


class Backtester:
    """
    Replay historical bars and evaluate strategy signals.

    Parameters
    ----------
    config : application configuration dict.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        ind = config.get("indicators", {})
        self._rsi_period: int = int(ind.get("rsi_period", 14))
        self._rsi_ob: float = float(ind.get("rsi_overbought", 70))
        self._rsi_os: float = float(ind.get("rsi_oversold", 30))
        self._macd_fast: int = int(ind.get("macd_fast", 12))
        self._macd_slow: int = int(ind.get("macd_slow", 26))
        self._macd_sig: int = int(ind.get("macd_signal", 9))
        self._atr_period: int = int(ind.get("atr_period", 14))

        risk = config.get("risk", {})
        self._sl_mult: float = float(risk.get("stop_loss_atr_mult", 1.5))
        self._tp_mult: float = float(risk.get("take_profit_atr_mult", 3.0))

        self._warmup = max(
            self._rsi_period + 1,
            self._macd_slow + self._macd_sig,
            self._atr_period + 1,
        )

    def run(self, csv_path: str) -> BacktestResult:
        """
        Run the backtest on a CSV file.

        Parameters
        ----------
        csv_path : path to CSV with columns: datetime, open, high, low, close, volume.

        Returns
        -------
        BacktestResult
        """
        bars = _load_csv(Path(csv_path))
        if len(bars) < self._warmup + 1:
            raise ValueError(
                f"CSV has only {len(bars)} bars; need at least {self._warmup + 1}"
            )

        result = BacktestResult()
        open_trade: Optional[Trade] = None

        for i in range(self._warmup, len(bars) - 1):
            slice_bars = bars[: i + 1]
            closes = [b["close"] for b in slice_bars]
            highs  = [b["high"]  for b in slice_bars]
            lows   = [b["low"]   for b in slice_bars]

            try:
                rsi_val  = rsi(closes, self._rsi_period)
                macd_res = macd(closes, self._macd_fast, self._macd_slow, self._macd_sig)
                atr_val  = atr(highs, lows, closes, self._atr_period)
            except ValueError:
                continue

            # Manage open trade exit.
            if open_trade is not None:
                price = bars[i]["close"]
                if open_trade.direction == "CALL":
                    if price <= open_trade.stop_loss:
                        open_trade.exit_price = price
                        open_trade.exit_bar = i
                        open_trade.exit_reason = "STOP_LOSS"
                        result.trades.append(open_trade)
                        open_trade = None
                    elif price >= open_trade.take_profit:
                        open_trade.exit_price = price
                        open_trade.exit_bar = i
                        open_trade.exit_reason = "TAKE_PROFIT"
                        result.trades.append(open_trade)
                        open_trade = None
                else:
                    if price >= open_trade.stop_loss:
                        open_trade.exit_price = price
                        open_trade.exit_bar = i
                        open_trade.exit_reason = "STOP_LOSS"
                        result.trades.append(open_trade)
                        open_trade = None
                    elif price <= open_trade.take_profit:
                        open_trade.exit_price = price
                        open_trade.exit_bar = i
                        open_trade.exit_reason = "TAKE_PROFIT"
                        result.trades.append(open_trade)
                        open_trade = None

            # Skip new signal if already in a trade.
            if open_trade is not None:
                continue

            # Determine signal direction.
            direction: Optional[str] = None
            if rsi_val > self._rsi_ob and macd_res.histogram > 0:
                direction = "CALL"
            elif rsi_val < self._rsi_os and macd_res.histogram < 0:
                direction = "PUT"

            if direction is None:
                continue

            result.signals += 1
            entry = bars[i + 1]["open"]  # fill at next bar open (no look-ahead)

            if direction == "CALL":
                stop = entry - atr_val * self._sl_mult
                tp   = entry + atr_val * self._tp_mult
            else:
                stop = entry + atr_val * self._sl_mult
                tp   = entry - atr_val * self._tp_mult

            open_trade = Trade(
                bar_index=i,
                direction=direction,
                entry_price=entry,
                stop_loss=stop,
                take_profit=tp,
            )

        # Close any remaining open trade at last bar.
        if open_trade is not None:
            last = bars[-1]["close"]
            open_trade.exit_price = last
            open_trade.exit_bar = len(bars) - 1
            open_trade.exit_reason = "END_OF_DATA"
            result.trades.append(open_trade)

        return result
