# file: src/market_adapter/__init__.py
from .base import MarketDataAdapter, create_market_adapter
from .fmp_adapter import FMPMarketAdapter

__all__ = ["MarketDataAdapter", "create_market_adapter", "FMPMarketAdapter"]
