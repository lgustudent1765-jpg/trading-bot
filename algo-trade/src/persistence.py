# file: src/persistence.py
"""
JSON-based persistence for open positions and recent signals.

Survives process restarts — state is written to disk after every change.
File: data/positions.json

Schema:
{
  "open_positions": {
    "AAPL_2026-03-20_150.0_C": {
      "symbol": "AAPL",
      "option_symbol": "...",
      "direction": "CALL",
      "entry_price": 2.10,
      "stop_loss": 1.50,
      "take_profit": 3.50,
      "quantity": 5,
      "opened_at": "2026-03-06T09:35:00+00:00"
    }
  },
  "signal_cooldowns": {
    "AAPL": "2026-03-06T09:35:00+00:00"
  }
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.logger import get_logger

log = get_logger(__name__)

_DATA_DIR  = Path("data")
_STATE_FILE = _DATA_DIR / "positions.json"


def _ensure_dir() -> None:
    _DATA_DIR.mkdir(exist_ok=True)


def _load_raw() -> Dict[str, Any]:
    _ensure_dir()
    if not _STATE_FILE.exists():
        return {"open_positions": {}, "signal_cooldowns": {}}
    try:
        with _STATE_FILE.open() as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("failed to load state file", error=str(exc))
        return {"open_positions": {}, "signal_cooldowns": {}}


def _save_raw(state: Dict[str, Any]) -> None:
    _ensure_dir()
    try:
        tmp = _STATE_FILE.with_suffix(".tmp")
        with tmp.open("w") as fh:
            json.dump(state, fh, indent=2)
        tmp.replace(_STATE_FILE)  # atomic rename
    except OSError as exc:
        log.error("failed to save state file", error=str(exc))


class PositionStore:
    """
    Thread-safe (single asyncio event loop) position and cooldown store.
    Writes to disk on every mutation.
    """

    def __init__(self) -> None:
        state = _load_raw()
        self._positions: Dict[str, Dict[str, Any]] = state.get("open_positions", {})
        self._cooldowns: Dict[str, str] = state.get("signal_cooldowns", {})
        log.info(
            "position store loaded",
            open_positions=len(self._positions),
        )

    # ------------------------------------------------------------------ #
    # Positions                                                            #
    # ------------------------------------------------------------------ #

    def add_position(
        self,
        option_symbol: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: int,
        underlying_price: float = 0.0,
    ) -> None:
        self._positions[option_symbol] = {
            "symbol": symbol,
            "option_symbol": option_symbol,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "quantity": quantity,
            "underlying_price": underlying_price,
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }
        self._flush()
        log.info("position saved", option_symbol=option_symbol)

    def remove_position(self, option_symbol: str) -> None:
        if option_symbol in self._positions:
            del self._positions[option_symbol]
            self._flush()
            log.info("position removed", option_symbol=option_symbol)

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._positions)

    @property
    def open_count(self) -> int:
        return len(self._positions)

    def symbols(self) -> list:
        return [v["symbol"] for v in self._positions.values()]

    # ------------------------------------------------------------------ #
    # Signal cooldowns                                                     #
    # ------------------------------------------------------------------ #

    def set_cooldown(self, symbol: str) -> None:
        """Record that a signal was just emitted for *symbol*."""
        self._cooldowns[symbol] = datetime.now(timezone.utc).isoformat()
        self._flush()

    def is_on_cooldown(self, symbol: str, cooldown_minutes: int = 30) -> bool:
        """Return True if *symbol* had a signal within *cooldown_minutes*."""
        ts_str = self._cooldowns.get(symbol)
        if not ts_str:
            return False
        try:
            last = datetime.fromisoformat(ts_str)
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            return elapsed < cooldown_minutes * 60
        except ValueError:
            return False

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _flush(self) -> None:
        _save_raw({
            "open_positions": self._positions,
            "signal_cooldowns": self._cooldowns,
        })
