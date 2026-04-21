# file: src/strategy_engine/multi_engine.py
"""
MultiStrategyEngine — runs all 10 strategies in parallel per symbol.

Selection logic:
  1. Score each strategy: 0.6 * win_rate + 0.4 * normalised_pnl
  2. No history yet → equal scores → round-robin tiebreak
  3. Highest-scoring strategy that produced a signal wins
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from src.events import OptionChainEvent, SignalEvent, TradePlan
from src.logger import get_logger
from src.market_adapter.base import MarketDataAdapter
from src.strategy_engine.strategies import ALL_STRATEGIES, BaseStrategy

log = get_logger(__name__)


class MultiStrategyEngine:
    def __init__(
        self,
        market_adapter: MarketDataAdapter,
        chain_queue: "asyncio.Queue[OptionChainEvent]",
        signal_queue: "asyncio.Queue[SignalEvent]",
        config: Dict[str, Any],
        position_store=None,
        notifier=None,
        tap_queue: "Optional[asyncio.Queue[SignalEvent]]" = None,
    ) -> None:
        self._market         = market_adapter
        self._chain_queue    = chain_queue
        self._signal_queue   = signal_queue
        self._tap_queue      = tap_queue
        self._position_store = position_store
        self._notifier       = notifier
        self._config         = config
        self._strategies: List[BaseStrategy] = ALL_STRATEGIES
        self._rr_index: int = 0  # round-robin tiebreak counter

        ind = config.get("indicators", {})
        self._lookback: int    = int(ind.get("lookback_bars", 50))
        self._cooldown_min: int = int(ind.get("signal_cooldown_minutes", 30))

        log.info(
            "multi_strategy_engine initialised",
            strategies=[s.name for s in self._strategies],
            count=len(self._strategies),
        )

    def _get_scores(self) -> Dict[str, float]:
        """Return composite score [float] per strategy name. Equal (0.0) if no data."""
        if not self._position_store:
            return {s.name: 0.0 for s in self._strategies}
        try:
            stats = self._position_store.get_strategy_scores()
        except Exception:
            return {s.name: 0.0 for s in self._strategies}
        if not stats:
            return {s.name: 0.0 for s in self._strategies}

        pnls = [v.get("total_pnl", 0.0) for v in stats.values()]
        max_abs = max((abs(p) for p in pnls), default=1.0) or 1.0

        scores: Dict[str, float] = {}
        for s in self._strategies:
            row = stats.get(s.name)
            if row is None or row.get("trades", 0) == 0:
                scores[s.name] = 0.0
            else:
                win_rate = row.get("win_rate", 0.0)
                norm_pnl = row.get("total_pnl", 0.0) / max_abs
                scores[s.name] = 0.6 * win_rate + 0.4 * norm_pnl
        return scores

    def _pick_winner(
        self,
        candidates: List[TradePlan],
        scores: Dict[str, float],
    ) -> Optional[TradePlan]:
        if not candidates:
            return None
        # If all candidate scores are equal → round-robin (no performance history yet)
        cand_scores = [scores.get(c.strategy_name, 0.0) for c in candidates]
        if len(set(cand_scores)) == 1:
            idx = self._rr_index % len(candidates)
            self._rr_index += 1
            return candidates[idx]
        return max(candidates, key=lambda p: scores.get(p.strategy_name, 0.0))

    async def _evaluate_strategy(
        self,
        strategy: BaseStrategy,
        symbol: str,
        bars: List[Dict],
        contracts: List,
    ) -> Optional[TradePlan]:
        try:
            return strategy.generate_signal(symbol, bars, contracts, self._config)
        except Exception as exc:
            log.debug("strategy error", strategy=strategy.name, symbol=symbol, error=str(exc))
            return None

    async def _process_chain(self, event: OptionChainEvent) -> None:
        symbol = event.symbol

        if self._position_store and self._position_store.is_on_cooldown(symbol, self._cooldown_min):
            log.debug("signal cooldown active", symbol=symbol)
            return

        if self._position_store and symbol in self._position_store.symbols():
            log.debug("already in position", symbol=symbol)
            return

        try:
            bars = await self._market.get_intraday_bars(
                symbol, interval="1min", limit=self._lookback + 10
            )
        except Exception as exc:
            log.debug("bars fetch failed", symbol=symbol, error=str(exc))
            return

        if not bars:
            return

        # Run all strategies concurrently
        results = await asyncio.gather(
            *[
                self._evaluate_strategy(s, symbol, bars, event.contracts)
                for s in self._strategies
            ],
            return_exceptions=False,
        )

        candidates: List[TradePlan] = [r for r in results if r is not None]
        if not candidates:
            log.debug("no signal from any strategy", symbol=symbol)
            return

        scores = self._get_scores()
        plan = self._pick_winner(candidates, scores)
        if plan is None:
            return

        log.info(
            "SIGNAL GENERATED",
            symbol=symbol,
            strategy=plan.strategy_name,
            direction=plan.direction.value,
            strike=plan.contract.strike,
            entry=plan.entry_limit,
            stop=plan.stop_loss,
            target=plan.take_profit,
            candidates_count=len(candidates),
            candidate_strategies=[c.strategy_name for c in candidates],
        )

        signal = SignalEvent(trade_plan=plan)
        await self._signal_queue.put(signal)
        if self._tap_queue is not None:
            try:
                self._tap_queue.put_nowait(signal)
            except asyncio.QueueFull:
                log.debug("tap_queue full", symbol=symbol)

        if self._position_store:
            self._position_store.set_cooldown(symbol)

        if self._notifier:
            asyncio.ensure_future(self._notifier.signal(
                symbol=symbol,
                direction=plan.direction.value,
                strike=plan.contract.strike,
                expiry=plan.contract.expiry,
                entry=plan.entry_limit,
                stop=plan.stop_loss,
                target=plan.take_profit,
                rationale=plan.rationale,
            ))

    async def run(self) -> None:
        log.info("multi_strategy_engine started", strategies=len(self._strategies))
        while True:
            try:
                event: OptionChainEvent = await self._chain_queue.get()
                await self._process_chain(event)
            except asyncio.CancelledError:
                log.info("multi_strategy_engine cancelled")
                return
            except Exception as exc:
                log.error("multi_strategy_engine error", error=str(exc))
