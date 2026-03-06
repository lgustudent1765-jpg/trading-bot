# file: src/execution/base.py
"""
Abstract broker adapter interface.

All concrete adapters (Webull, Robinhood, Mock) must implement this interface.
Dependency injection via create_broker_adapter(config) factory.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional

from src.events import OptionContract, OrderEvent, OrderStatus


class BrokerAdapter(abc.ABC):
    """Protocol for broker integration."""

    # ------------------------------------------------------------------ #
    # Option-chain retrieval                                               #
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def get_option_chain(self, symbol: str, underlying_price: float = 0.0) -> List[OptionContract]:
        """
        Return all available option contracts for *symbol*.

        underlying_price: current spot price — used by mock adapters to generate
        realistic strikes. Real broker adapters may ignore this parameter.
        The caller (OptionsFetcher) applies liquidity filters afterward.
        """

    # ------------------------------------------------------------------ #
    # Order management                                                     #
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def place_limit_order(
        self,
        option_symbol: str,
        side: str,           # "BUY" | "SELL"
        quantity: int,
        limit_price: float,
    ) -> OrderEvent:
        """
        Submit a limit order and return the initial OrderEvent.

        Must be idempotent if called with the same parameters.
        Implementations must retry on transient network errors internally.
        """

    @abc.abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order; return True if successfully cancelled."""

    @abc.abstractmethod
    async def get_order_status(self, order_id: str) -> OrderEvent:
        """Poll and return the current state of an order."""

    # ------------------------------------------------------------------ #
    # Account info                                                         #
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def get_account_equity(self) -> float:
        """Return the total account equity in USD."""

    async def close(self) -> None:
        """Release any held resources."""


def create_broker_adapter(config: Dict[str, Any]) -> BrokerAdapter:
    """
    Factory returning a concrete BrokerAdapter.

    Broker choices (config['broker']['name']):
        'mock'    -> MockBrokerAdapter  (default; no credentials needed)
        'webull'  -> WebullAdapter      (requires env credentials)
    """
    broker_name = config.get("broker", {}).get("name", "mock").lower()
    if broker_name == "webull":
        from src.execution.webull_adapter import WebullAdapter
        return WebullAdapter(config)
    from src.execution.mock_adapter import MockBrokerAdapter
    return MockBrokerAdapter()
