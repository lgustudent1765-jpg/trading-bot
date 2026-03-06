# file: src/cli/main.py
"""
Command-line entry point.

Usage:
    python -m src.cli.main --mode paper
    python -m src.cli.main --mode manual
    python -m src.cli.main --mode automated
    python -m src.cli.main --mode backtest --data sample_data/minute_sample.csv

WARNING: automated mode places real orders when broker='webull'.
         Always verify in paper mode first.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.api_server.server import create_app, run_api_server
from src.config import load_config
from src.events import SignalEvent
from src.execution.base import create_broker_adapter
from src.execution.order_manager import OrderManager
from src.logger import get_logger
from src.market_adapter.base import create_market_adapter
from src.options_fetcher import OptionsFetcher
from src.risk_manager import RiskManager
from src.screener import Screener
from src.strategy_engine import StrategyEngine

log = get_logger(__name__)

# Shared signal store for the API server.
_signal_store: List[Dict] = []


async def _run_pipeline(config: Dict[str, Any], mode: str) -> None:
    """Wire up and run the full event-driven pipeline."""
    market_adapter = create_market_adapter(config)
    broker_adapter = create_broker_adapter(config)
    risk_manager = RiskManager(config)

    candidate_queue: asyncio.Queue = asyncio.Queue(maxsize=20)
    chain_queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    signal_queue: asyncio.Queue = asyncio.Queue(maxsize=20)

    screener = Screener(market_adapter, candidate_queue, config)
    fetcher = OptionsFetcher(broker_adapter, candidate_queue, chain_queue, config)
    engine = StrategyEngine(market_adapter, chain_queue, signal_queue, config)
    order_mgr = OrderManager(broker_adapter, risk_manager, signal_queue, mode, config)

    # Signal logger: copies signals to the shared store for the API.
    async def signal_tap() -> None:
        while True:
            sig: SignalEvent = await asyncio.wait_for(signal_queue.get(), timeout=1.0)
            plan = sig.trade_plan
            _signal_store.append({
                "symbol": plan.symbol,
                "direction": plan.direction.value,
                "strike": plan.contract.strike,
                "expiry": plan.contract.expiry,
                "entry": plan.entry_limit,
                "stop": plan.stop_loss,
                "target": plan.take_profit,
                "size": plan.position_size,
                "rationale": plan.rationale,
                "ts": sig.timestamp.isoformat(),
            })
            if len(_signal_store) > 200:
                _signal_store.pop(0)
            await signal_queue.put(sig)  # put back for order manager

    api_cfg = config.get("api_server", {})
    app = create_app(risk_manager, _signal_store)

    log.info("pipeline starting", mode=mode)

    try:
        await asyncio.gather(
            screener.run(),
            fetcher.run(),
            engine.run(),
            order_mgr.run(),
            run_api_server(app, api_cfg.get("host", "0.0.0.0"), api_cfg.get("port", 8080)),
        )
    finally:
        await market_adapter.close()
        await broker_adapter.close()


def _run_backtest(config: Dict[str, Any], data_path: str) -> None:
    from src.backtester import Backtester
    bt = Backtester(config)
    result = bt.run(data_path)
    result.print_report()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Algorithmic options trading system (paper-trade default)."
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "manual", "automated", "backtest"],
        default="paper",
        help="Execution mode (default: paper).",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml (default: config.yaml).",
    )
    parser.add_argument(
        "--data",
        default="sample_data/minute_sample.csv",
        help="CSV path for backtest mode.",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))

    # Enforce safe default: paper mode unless explicitly overridden.
    effective_mode = args.mode
    if effective_mode == "automated" and config.get("broker", {}).get("name", "mock") == "mock":
        log.warning("automated mode with mock broker — orders will be simulated only")

    if effective_mode == "backtest":
        _run_backtest(config, args.data)
        sys.exit(0)

    try:
        asyncio.run(_run_pipeline(config, effective_mode))
    except KeyboardInterrupt:
        log.info("shutdown requested")


if __name__ == "__main__":
    main()
