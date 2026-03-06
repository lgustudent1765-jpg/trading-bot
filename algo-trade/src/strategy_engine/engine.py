# file: src/strategy_engine/engine.py
"""
CEP-style strategy engine.

Event flow:
    OptionChainEvent (from options_fetcher)
        -> fetch intraday bars
        -> compute RSI, MACD, ATR
        -> apply momentum rules
        -> select best option contract
        -> compute entry, SL, TP
        -> emit SignalEvent

Momentum rules:
    CALL signal: RSI > rsi_overbought AND MACD histogram > 0
    PUT  signal: RSI < rsi_oversold  AND MACD histogram < 0

Entry / exit formulas (per contract):
    entry_limit  = ask * 1.01
    stop_loss    = entry_limit - (ATR_underlying * sl_mult)
    take_profit  = entry_limit + (ATR_underlying * tp_mult)

The engine is stateless between events (pure CEP style); state is held
only for bar-history caching to avoid redundant API calls.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from src.events import (
    OptionChainEvent,
    OptionContract,
    SignalDirection,
    SignalEvent,
    TradePlan,
)
from src.indicators import atr, macd, rsi
from src.logger import get_logger
from src.market_adapter.base import MarketDataAdapter

log = get_logger(__name__)


def _select_contract(
    contracts: List[OptionContract],
    direction: SignalDirection,
) -> Optional[OptionContract]:
    """
    Select the best contract for the signal direction.

    Strategy: choose the near-ATM contract (smallest |strike - spot|)
    of the correct type with the best volume*OI score.
    """
    opt_type = "call" if direction == SignalDirection.CALL else "put"
    candidates = [c for c in contracts if c.option_type == opt_type]
    if not candidates:
        return None

    # Sort by moneyness proximity then by volume.
    candidates.sort(
        key=lambda c: (abs(c.strike - c.underlying_price), -c.volume)
    )
    return candidates[0]


class StrategyEngine:
    """
    Consumes OptionChainEvents, computes indicators, and emits SignalEvents.

    Parameters
    ----------
    market_adapter : used to fetch intraday bars for indicator computation.
    chain_queue    : asyncio.Queue[OptionChainEvent] from options_fetcher.
    signal_queue   : asyncio.Queue[SignalEvent] consumed by execution layer.
    config         : application configuration dict.
    """

    def __init__(
        self,
        market_adapter: MarketDataAdapter,
        chain_queue: "asyncio.Queue[OptionChainEvent]",
        signal_queue: "asyncio.Queue[SignalEvent]",
        config: Dict[str, Any],
    ) -> None:
        self._market = market_adapter
        self._chain_queue = chain_queue
        self._signal_queue = signal_queue

        ind = config.get("indicators", {})
        self._rsi_period: int = int(ind.get("rsi_period", 14))
        self._rsi_ob: float = float(ind.get("rsi_overbought", 70))
        self._rsi_os: float = float(ind.get("rsi_oversold", 30))
        self._macd_fast: int = int(ind.get("macd_fast", 12))
        self._macd_slow: int = int(ind.get("macd_slow", 26))
        self._macd_sig: int = int(ind.get("macd_signal", 9))
        self._atr_period: int = int(ind.get("atr_period", 14))
        self._lookback: int = int(ind.get("lookback_bars", 50))

        risk = config.get("risk", {})
        self._sl_mult: float = float(risk.get("stop_loss_atr_mult", 1.5))
        self._tp_mult: float = float(risk.get("take_profit_atr_mult", 3.0))

    async def _compute_indicators(self, symbol: str):
        """
        Fetch intraday bars and compute RSI, MACD, ATR.

        Returns (rsi_val, macd_result, atr_val) or raises ValueError if
        there is insufficient bar history.
        """
        bars = await self._market.get_intraday_bars(
            symbol, interval="1min", limit=self._lookback + 10
        )
        if len(bars) < max(self._rsi_period + 1, self._macd_slow + self._macd_sig, self._atr_period + 1):
            raise ValueError(f"Insufficient bar data for {symbol}: {len(bars)} bars")

        closes = [b["close"] for b in bars]
        highs  = [b["high"]  for b in bars]
        lows   = [b["low"]   for b in bars]

        rsi_val  = rsi(closes, self._rsi_period)
        macd_res = macd(closes, self._macd_fast, self._macd_slow, self._macd_sig)
        atr_val  = atr(highs, lows, closes, self._atr_period)

        return rsi_val, macd_res, atr_val

    def _determine_direction(
        self, rsi_val: float, macd_hist: float
    ) -> Optional[SignalDirection]:
        """Apply momentum rules to determine signal direction."""
        if rsi_val > self._rsi_ob and macd_hist > 0:
            return SignalDirection.CALL
        if rsi_val < self._rsi_os and macd_hist < 0:
            return SignalDirection.PUT
        return None

    def _build_trade_plan(
        self,
        symbol: str,
        direction: SignalDirection,
        contract: OptionContract,
        atr_val: float,
        rsi_val: float,
        macd_hist: float,
    ) -> TradePlan:
        """
        Compute entry, stop-loss, and take-profit for a given contract.

        Formulas:
            entry_limit = contract.ask * 1.01   (small premium for fill)
            stop_loss   = entry_limit - (atr_val * sl_mult)   [for CALL]
                        = entry_limit + (atr_val * sl_mult)   [for PUT]
            take_profit = entry_limit + (atr_val * tp_mult)   [for CALL]
                        = entry_limit - (atr_val * tp_mult)   [for PUT]
        """
        entry = round(contract.ask * 1.01, 2)

        if direction == SignalDirection.CALL:
            stop  = round(entry - atr_val * self._sl_mult, 2)
            tp    = round(entry + atr_val * self._tp_mult, 2)
        else:
            stop  = round(entry + atr_val * self._sl_mult, 2)
            tp    = round(entry - atr_val * self._tp_mult, 2)

        rationale = (
            f"RSI={rsi_val:.1f} ({'OB' if direction == SignalDirection.CALL else 'OS'}), "
            f"MACD_hist={macd_hist:.4f}, "
            f"ATR={atr_val:.2f}, "
            f"strike={contract.strike}, expiry={contract.expiry}"
        )

        return TradePlan(
            symbol=symbol,
            direction=direction,
            contract=contract,
            entry_limit=entry,
            stop_loss=stop,
            take_profit=tp,
            rsi=rsi_val,
            macd_hist=macd_hist,
            rationale=rationale,
        )

    async def _process_chain(self, event: OptionChainEvent) -> None:
        """Process a single OptionChainEvent and emit a SignalEvent if warranted."""
        symbol = event.symbol
        try:
            rsi_val, macd_res, atr_val = await self._compute_indicators(symbol)
        except ValueError as exc:
            log.debug("indicator computation skipped", symbol=symbol, reason=str(exc))
            return
        except Exception as exc:
            log.error("indicator error", symbol=symbol, error=str(exc))
            return

        direction = self._determine_direction(rsi_val, macd_res.histogram)
        if direction is None:
            log.debug(
                "no signal",
                symbol=symbol,
                rsi=round(rsi_val, 1),
                macd_hist=round(macd_res.histogram, 4),
            )
            return

        contract = _select_contract(event.contracts, direction)
        if contract is None:
            log.debug("no suitable contract", symbol=symbol, direction=direction.value)
            return

        plan = self._build_trade_plan(
            symbol, direction, contract, atr_val, rsi_val, macd_res.histogram
        )
        signal = SignalEvent(trade_plan=plan)
        await self._signal_queue.put(signal)

        log.info(
            "SIGNAL GENERATED",
            symbol=symbol,
            direction=direction.value,
            strike=contract.strike,
            expiry=contract.expiry,
            entry=plan.entry_limit,
            stop=plan.stop_loss,
            target=plan.take_profit,
            rsi=round(rsi_val, 1),
            macd_hist=round(macd_res.histogram, 4),
        )

    async def run(self) -> None:
        """Consume OptionChainEvents and emit SignalEvents indefinitely."""
        log.info("strategy_engine started")
        while True:
            try:
                event: OptionChainEvent = await self._chain_queue.get()
                await self._process_chain(event)
            except asyncio.CancelledError:
                log.info("strategy_engine cancelled")
                return
            except Exception as exc:
                log.error("strategy_engine loop error", error=str(exc))
