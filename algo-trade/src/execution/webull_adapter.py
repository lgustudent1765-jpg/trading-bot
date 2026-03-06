# file: src/execution/webull_adapter.py
"""
Webull broker adapter.

Credentials are read exclusively from environment variables via config:
    WEBULL_DEVICE_ID, WEBULL_ACCESS_TOKEN, WEBULL_REFRESH_TOKEN,
    WEBULL_TRADE_TOKEN, WEBULL_ACCOUNT_ID

No credentials are ever logged or stored in code.

NOTE: The webull Python SDK (pip install webull) uses synchronous calls.
      This adapter wraps SDK calls in asyncio.get_event_loop().run_in_executor
      to avoid blocking the event loop.

WARNING: This adapter is provided for integration purposes. Test thoroughly
         in paper-trade mode before using with real funds.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from functools import partial
from typing import Any, Dict, List, Optional

from src.events import OptionContract, OrderEvent, OrderSide, OrderStatus
from src.execution.base import BrokerAdapter
from src.logger import get_logger

log = get_logger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="webull")


class WebullAdapter(BrokerAdapter):
    """
    Concrete Webull adapter.

    Lazy-initialises the Webull SDK client on first use to avoid import errors
    if the 'webull' package is not installed (tests use MockBrokerAdapter).
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        wb_cfg = config.get("broker", {}).get("webull", {})
        self._device_id: str = wb_cfg.get("device_id", "")
        self._access_token: str = wb_cfg.get("access_token", "")
        self._refresh_token: str = wb_cfg.get("refresh_token", "")
        self._trade_token: str = wb_cfg.get("trade_token", "")
        self._account_id: str = wb_cfg.get("account_id", "")
        self._client: Optional[Any] = None  # webull.webull instance

    def _get_client(self) -> Any:
        """Lazily initialise and return the Webull SDK client."""
        if self._client is not None:
            return self._client
        try:
            from webull import webull  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "webull package is required for WebullAdapter. "
                "Install it with: pip install webull"
            ) from exc

        wb = webull()
        wb.api_login(
            access_token=self._access_token,
            refresh_token=self._refresh_token,
            token_expiry=None,
            uuid=self._device_id,
            trade_token=self._trade_token,
            account_id=self._account_id,
        )
        self._client = wb
        log.info("webull client initialised")
        return self._client

    async def _run_sync(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous SDK call in the thread-pool executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_EXECUTOR, partial(fn, *args, **kwargs))

    async def get_option_chain(self, symbol: str, underlying_price: float = 0.0) -> List[OptionContract]:
        """
        Fetch option chain from Webull.

        Maps Webull's option data format to OptionContract objects.
        """
        wb = self._get_client()
        try:
            raw = await self._run_sync(wb.get_options, stock=symbol)
        except Exception as exc:
            log.error("webull get_options failed", symbol=symbol, error=str(exc))
            return []

        contracts: List[OptionContract] = []
        for item in raw or []:
            try:
                expiry = item.get("expireDate", "")
                strike = float(item.get("strikePrice", 0))
                opt_type = "call" if item.get("direction", "").lower() == "call" else "put"
                bid = float(item.get("bidList", [{}])[0].get("price", 0) if item.get("bidList") else 0)
                ask = float(item.get("askList", [{}])[0].get("price", 0) if item.get("askList") else 0)
                contracts.append(
                    OptionContract(
                        symbol=symbol,
                        expiry=expiry,
                        strike=strike,
                        option_type=opt_type,
                        bid=bid,
                        ask=ask,
                        volume=int(item.get("volume", 0)),
                        open_interest=int(item.get("openInterest", 0)),
                        implied_volatility=float(item.get("impliedVolatility", 0)),
                        delta=float(item.get("delta", 0)),
                    )
                )
            except (TypeError, ValueError, KeyError) as exc:
                log.warning("skipped malformed option row", error=str(exc))
        return contracts

    async def place_limit_order(
        self,
        option_symbol: str,
        side: str,
        quantity: int,
        limit_price: float,
    ) -> OrderEvent:
        """Place a limit order via Webull SDK."""
        wb = self._get_client()
        action = "BUY" if side == "BUY" else "SELL"
        try:
            resp = await self._run_sync(
                wb.place_option_order,
                optionId=option_symbol,
                lmtPrice=limit_price,
                action=action,
                orderType="LMT",
                enforce="DAY",
                quant=quantity,
            )
            order_id = str(resp.get("orderId", "unknown"))
            order = OrderEvent(
                order_id=order_id,
                symbol=option_symbol,
                option_symbol=option_symbol,
                side=OrderSide(side),
                quantity=quantity,
                limit_price=limit_price,
            )
            order.transition(OrderStatus.SUBMITTED)
            log.info(
                "webull order placed",
                order_id=order_id,
                option_symbol=option_symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price,
            )
            return order
        except Exception as exc:
            log.error("webull place_order failed", error=str(exc))
            raise

    async def cancel_order(self, order_id: str) -> bool:
        wb = self._get_client()
        try:
            await self._run_sync(wb.cancel_order, order_id)
            return True
        except Exception as exc:
            log.error("webull cancel_order failed", order_id=order_id, error=str(exc))
            return False

    async def get_order_status(self, order_id: str) -> OrderEvent:
        wb = self._get_client()
        try:
            resp = await self._run_sync(wb.get_history_orders, status="All", count=20)
            for item in resp or []:
                if str(item.get("orderId")) == order_id:
                    status_str = item.get("statusStr", "").upper()
                    status_map = {
                        "FILLED": OrderStatus.FILLED,
                        "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
                        "CANCELLED": OrderStatus.CANCELLED,
                        "REJECTED": OrderStatus.REJECTED,
                        "WORKING": OrderStatus.SUBMITTED,
                    }
                    status = status_map.get(status_str, OrderStatus.SUBMITTED)
                    order = OrderEvent(
                        order_id=order_id,
                        symbol=str(item.get("ticker", {}).get("symbol", "")),
                        option_symbol=order_id,
                        side=OrderSide("BUY"),
                        quantity=int(item.get("totalQuantity", 0)),
                        limit_price=float(item.get("lmtPrice", 0)),
                        status=status,
                        filled_qty=int(item.get("filledQuantity", 0)),
                        avg_fill_price=float(item.get("avgFilledPrice", 0)),
                    )
                    return order
            raise KeyError(f"Order {order_id} not found in Webull history")
        except Exception as exc:
            log.error("webull get_order_status failed", order_id=order_id, error=str(exc))
            raise

    async def get_account_equity(self) -> float:
        wb = self._get_client()
        try:
            resp = await self._run_sync(wb.get_account)
            return float(resp.get("netLiquidation", 0))
        except Exception as exc:
            log.error("webull get_account_equity failed", error=str(exc))
            return 0.0

    async def close(self) -> None:
        _EXECUTOR.shutdown(wait=False)
