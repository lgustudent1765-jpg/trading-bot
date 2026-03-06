# file: src/execution/order_manager.py
"""
Order manager — consumes SignalEvents, applies risk checks, places orders,
and monitors fills and stop exits.

Automated mode: places limit orders and monitors for fill + stop exit.
Manual mode   : logs the recommended trade plan without placing orders.

Stop-exit logic (mock OCO since options brokers may lack native OCO):
    After fill confirmation, the order_manager polls the underlying price
    and exits the position if stop_loss is breached.  This is a software
    stop — not a native broker stop — and therefore susceptible to slippage.

    Trade-off: safer than no stop; inferior to a native bracket order.
    When the broker supports native stop orders for options, replace the
    polling loop with a native stop placement call.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from src.events import FillEvent, OrderEvent, OrderSide, OrderStatus, SignalEvent
from src.execution.base import BrokerAdapter
from src.logger import get_logger
from src.risk_manager import RiskManager

log = get_logger(__name__)

_STOP_POLL_INTERVAL = 5.0  # seconds between stop-check polls


class OrderManager:
    """
    Bridges SignalEvents to the broker adapter, enforces risk rules,
    and manages the open-position lifecycle.

    Parameters
    ----------
    broker       : concrete BrokerAdapter.
    risk_manager : RiskManager instance.
    signal_queue : asyncio.Queue[SignalEvent].
    mode         : 'automated' | 'manual' | 'paper'.
    config       : application configuration dict.
    """

    def __init__(
        self,
        broker: BrokerAdapter,
        risk_manager: RiskManager,
        signal_queue: "asyncio.Queue[SignalEvent]",
        mode: str = "paper",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._broker = broker
        self._risk = risk_manager
        self._signal_queue = signal_queue
        self._mode = mode.lower()
        self._config = config or {}
        self._open_orders: Dict[str, SignalEvent] = {}  # order_id -> signal

    async def _handle_signal(self, signal: SignalEvent) -> None:
        plan = signal.trade_plan

        # Risk check and position sizing.
        equity = await self._broker.get_account_equity()
        if not self._risk.approve(plan, equity):
            log.info("signal rejected by risk manager", symbol=plan.symbol)
            return

        # In manual mode, only log the recommendation.
        if self._mode == "manual":
            log.info(
                "TRADE RECOMMENDATION (manual mode — not executed)",
                symbol=plan.symbol,
                direction=plan.direction.value,
                strike=plan.contract.strike,
                expiry=plan.contract.expiry,
                entry=plan.entry_limit,
                stop=plan.stop_loss,
                target=plan.take_profit,
                size=plan.position_size,
                rationale=plan.rationale,
            )
            return

        # Automated / paper mode: place the order.
        option_symbol = (
            f"{plan.symbol}_{plan.contract.expiry}_{plan.contract.strike}"
            f"_{plan.contract.option_type[0].upper()}"
        )
        try:
            order: OrderEvent = await self._broker.place_limit_order(
                option_symbol=option_symbol,
                side=OrderSide.BUY.value,
                quantity=plan.position_size,
                limit_price=plan.entry_limit,
            )
        except Exception as exc:
            log.error("order placement failed", symbol=plan.symbol, error=str(exc))
            return

        if order.status == OrderStatus.FILLED:
            self._risk.register_open(option_symbol)
            log.info(
                "order filled — starting stop monitor",
                order_id=order.order_id,
                fill_price=order.avg_fill_price,
            )
            # Launch stop monitor as a background task.
            asyncio.ensure_future(
                self._monitor_stop(order, plan, option_symbol)
            )
        else:
            self._open_orders[order.order_id] = signal

    async def _monitor_stop(
        self,
        entry_order: OrderEvent,
        plan: Any,
        option_symbol: str,
    ) -> None:
        """
        Software-based stop monitor.

        Polls the option price every _STOP_POLL_INTERVAL seconds.
        Exits the position if:
            - mid_price <= stop_loss (stop hit for CALL), or
            - mid_price >= take_profit (target hit for CALL).
        """
        entry_fill = entry_order.avg_fill_price
        log.info(
            "stop monitor started",
            symbol=plan.symbol,
            option_symbol=option_symbol,
            stop=plan.stop_loss,
            target=plan.take_profit,
        )
        while True:
            await asyncio.sleep(_STOP_POLL_INTERVAL)
            try:
                chain = await self._broker.get_option_chain(plan.symbol)
                contract = next(
                    (
                        c for c in chain
                        if c.expiry == plan.contract.expiry
                        and c.strike == plan.contract.strike
                        and c.option_type == plan.contract.option_type
                    ),
                    None,
                )
                if contract is None:
                    continue

                mid = contract.mid_price
                exit_reason: Optional[str] = None

                from src.events import SignalDirection
                if plan.direction == SignalDirection.CALL:
                    if mid <= plan.stop_loss:
                        exit_reason = "STOP_LOSS"
                    elif mid >= plan.take_profit:
                        exit_reason = "TAKE_PROFIT"
                else:
                    if mid >= plan.stop_loss:
                        exit_reason = "STOP_LOSS"
                    elif mid <= plan.take_profit:
                        exit_reason = "TAKE_PROFIT"

                if exit_reason:
                    exit_order = await self._broker.place_limit_order(
                        option_symbol=option_symbol,
                        side=OrderSide.SELL.value,
                        quantity=entry_order.filled_qty,
                        limit_price=round(mid * 0.99, 2),  # slight discount for fill
                    )
                    pnl = (exit_order.avg_fill_price - entry_fill) * entry_order.filled_qty * 100
                    self._risk.register_close(option_symbol)
                    log.info(
                        "position closed",
                        reason=exit_reason,
                        symbol=plan.symbol,
                        entry=entry_fill,
                        exit=exit_order.avg_fill_price,
                        pnl=round(pnl, 2),
                    )
                    return

            except asyncio.CancelledError:
                return
            except Exception as exc:
                log.error("stop monitor error", error=str(exc))

    async def run(self) -> None:
        """Consume SignalEvents and act on them indefinitely."""
        log.info("order_manager started", mode=self._mode)
        while True:
            try:
                signal: SignalEvent = await self._signal_queue.get()
                await self._handle_signal(signal)
            except asyncio.CancelledError:
                log.info("order_manager cancelled")
                return
            except Exception as exc:
                log.error("order_manager loop error", error=str(exc))
