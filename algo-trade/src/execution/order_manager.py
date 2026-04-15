# file: src/execution/order_manager.py
"""
Order manager — production version.

New features:
  - Persists open positions to disk (survives restarts)
  - Sends fill/close notifications via Notifier
  - Graceful shutdown support
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from src.events import OrderEvent, OrderSide, OrderStatus, SignalEvent
from src.execution.base import BrokerAdapter
from src.logger import get_logger
from src.market_adapter.base import MarketDataAdapter
from src.risk_manager import RiskManager

log = get_logger(__name__)

_STOP_POLL_INTERVAL = 10.0  # seconds between stop-check polls


class OrderManager:
    def __init__(
        self,
        broker: BrokerAdapter,
        risk_manager: RiskManager,
        signal_queue: "asyncio.Queue[SignalEvent]",
        mode: str = "paper",
        config: Optional[Dict[str, Any]] = None,
        position_store=None,
        notifier=None,
        signal_store: Optional[list] = None,
        action_store: Optional[list] = None,
        market_adapter: Optional[MarketDataAdapter] = None,
        **kwargs: Any,
    ) -> None:
        self._broker = broker
        self._risk = risk_manager
        self._signal_queue = signal_queue
        self._mode = mode.lower()
        self._config = config or {}
        self._position_store = position_store
        self._notifier = notifier
        self._signal_store = signal_store
        self._action_store = action_store
        self._market = market_adapter
        self._open_orders: Dict[str, SignalEvent] = {}

    def _record_action(self, event: str, symbol: Optional[str], detail: str, data: dict) -> None:
        """Append to in-memory action_store and persist to DB."""
        from datetime import datetime, timezone
        entry = {"event": event, "symbol": symbol, "detail": detail, "data": data,
                 "ts": datetime.now(timezone.utc).isoformat()}
        if self._action_store is not None:
            self._action_store.append(entry)
            if len(self._action_store) > 200:
                self._action_store.pop(0)
        if self._position_store:
            self._position_store.add_action(event=event, symbol=symbol, detail=detail, data=data)

    async def _handle_signal(self, signal: SignalEvent) -> None:
        plan = signal.trade_plan

        equity = await self._broker.get_account_equity()
        approved, reject_reason = self._risk.approve(plan, equity)
        if not approved:
            log.info("signal rejected by risk manager", symbol=plan.symbol, reason=reject_reason)
            self._record_action(
                "SIGNAL_REJECTED", plan.symbol,
                f"{plan.direction.value} signal rejected: {reject_reason}",
                {"direction": plan.direction.value, "entry": plan.entry_limit, "reason": reject_reason},
            )
            return

        if self._mode == "manual":
            log.info(
                "TRADE RECOMMENDATION (manual — not executed)",
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
            self._record_action(
                "ORDER_FILLED", plan.symbol,
                f"BUY {order.filled_qty}x {option_symbol} @ ${order.avg_fill_price:.2f}",
                {"option_symbol": option_symbol, "qty": order.filled_qty,
                 "fill_price": order.avg_fill_price, "order_id": order.order_id},
            )

            # Persist position.
            if self._position_store:
                self._position_store.add_position(
                    option_symbol=option_symbol,
                    symbol=plan.symbol,
                    direction=plan.direction.value,
                    entry_price=order.avg_fill_price,
                    stop_loss=plan.stop_loss,
                    take_profit=plan.take_profit,
                    quantity=order.filled_qty,
                    underlying_price=plan.contract.underlying_price,
                )

            # Send fill notification.
            if self._notifier:
                asyncio.ensure_future(self._notifier.filled(
                    symbol=plan.symbol,
                    side="BUY",
                    qty=order.filled_qty,
                    fill_price=order.avg_fill_price,
                    order_id=order.order_id,
                ))

            log.info(
                "order filled — starting stop monitor",
                order_id=order.order_id,
                fill_price=order.avg_fill_price,
            )
            asyncio.ensure_future(self._monitor_stop(order, plan, option_symbol))
        else:
            self._open_orders[order.order_id] = signal

    async def _monitor_stop(
        self,
        entry_order: OrderEvent,
        plan: Any,
        option_symbol: str,
    ) -> None:
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
                if self._market is not None:
                    try:
                        quote = await self._market.get_quote(plan.symbol)
                        current_price = quote.price
                    except Exception:
                        current_price = plan.contract.underlying_price
                else:
                    current_price = plan.contract.underlying_price
                chain = await self._broker.get_option_chain(
                    plan.symbol,
                    underlying_price=current_price,
                )
                contract = next(
                    (c for c in chain
                     if c.expiry == plan.contract.expiry
                     and c.strike == plan.contract.strike
                     and c.option_type == plan.contract.option_type),
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
                        limit_price=round(mid * 0.99, 2),
                    )
                    pnl = (exit_order.avg_fill_price - entry_fill) * entry_order.filled_qty * 100
                    self._risk.register_close(option_symbol)
                    pnl_sign = "+" if pnl >= 0 else ""
                    self._record_action(
                        "POSITION_CLOSED", plan.symbol,
                        f"{exit_reason}: SELL {option_symbol} @ ${exit_order.avg_fill_price:.2f} "
                        f"(P&L: {pnl_sign}${pnl:.2f})",
                        {"option_symbol": option_symbol, "reason": exit_reason,
                         "entry": entry_fill, "exit": exit_order.avg_fill_price,
                         "pnl": round(pnl, 2)},
                    )

                    if self._position_store:
                        self._position_store.remove_position(option_symbol)

                    if self._notifier:
                        asyncio.ensure_future(self._notifier.closed(
                            symbol=plan.symbol,
                            reason=exit_reason,
                            entry=entry_fill,
                            exit_price=exit_order.avg_fill_price,
                            pnl=pnl,
                        ))

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

    async def recover_open_positions(self) -> None:
        """Re-arm stop monitors for positions that survived a restart."""
        if not self._position_store:
            return
        positions = self._position_store.get_positions()
        for option_symbol, pos in positions.items():
            try:
                # Option symbol format: SYM_EXPIRY_STRIKE_TYPE (e.g. AAPL_2026-05-16_175.0_C)
                parts = option_symbol.split("_")
                if len(parts) < 4:
                    log.warning("recover: skipping unparseable symbol", option_symbol=option_symbol)
                    continue

                from src.events import (
                    OptionContract, OrderEvent, OrderSide, OrderStatus,
                    SignalDirection, TradePlan,
                )

                direction_str = pos["direction"].upper()
                direction = SignalDirection.CALL if direction_str == "CALL" else SignalDirection.PUT
                opt_type = "call" if direction == SignalDirection.CALL else "put"

                contract = OptionContract(
                    symbol=pos["symbol"],
                    expiry=parts[1],
                    strike=float(parts[2]),
                    option_type=opt_type,
                    bid=pos["entry_price"],
                    ask=pos["entry_price"],
                    volume=0,
                    open_interest=0,
                    implied_volatility=0.0,
                    delta=0.5,
                    underlying_price=pos.get("underlying_price", 0.0),
                )
                plan = TradePlan(
                    symbol=pos["symbol"],
                    direction=direction,
                    contract=contract,
                    entry_limit=pos["entry_price"],
                    stop_loss=pos["stop_loss"],
                    take_profit=pos["take_profit"],
                    position_size=pos["quantity"],
                    rationale="recovered from persistence",
                )
                entry_order = OrderEvent(
                    order_id=f"recovered_{option_symbol}",
                    symbol=pos["symbol"],
                    option_symbol=option_symbol,
                    side=OrderSide.BUY,
                    quantity=pos["quantity"],
                    limit_price=pos["entry_price"],
                    status=OrderStatus.FILLED,
                    filled_qty=pos["quantity"],
                    avg_fill_price=pos["entry_price"],
                )
                self._risk.register_open(option_symbol)
                asyncio.ensure_future(self._monitor_stop(entry_order, plan, option_symbol))
                log.info("recovered position — stop monitor re-armed", option_symbol=option_symbol)
            except Exception as exc:
                log.warning(
                    "recover: failed to recover position",
                    option_symbol=option_symbol,
                    error=str(exc),
                )

    async def run(self) -> None:
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
