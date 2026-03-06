#!/usr/bin/env python3
# file: scripts/backtest.py
"""
Backtest CLI script.

Usage:
    python scripts/backtest.py sample_data/minute_sample.csv
    python scripts/backtest.py sample_data/minute_sample.csv --config config.yaml
"""

import argparse
import sys
from pathlib import Path

# Ensure src is importable when running from project root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtester import Backtester
from src.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strategy backtest on historical CSV data.")
    parser.add_argument("csv_path", help="Path to minute-bar CSV file.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml.")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path if config_path.exists() else None)

    print(f"\nRunning backtest on: {args.csv_path}")
    bt = Backtester(config)
    try:
        result = bt.run(args.csv_path)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    result.print_report()


if __name__ == "__main__":
    main()
