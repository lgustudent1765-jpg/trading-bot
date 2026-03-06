#!/usr/bin/env bash
# file: run_paper_demo.sh
# ============================================================
# Paper-trade demo script.
# Runs the system with mock data, produces at least one signal,
# and exits after 30 seconds.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if present.
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Use mock provider + mock broker so no credentials are needed.
export MODE=paper
export CONFIG_PATH="${SCRIPT_DIR}/config.yaml.template"
export ALGO_SCREENER_PROVIDER=mock
export ALGO_SCREENER_POLL_INTERVAL_SECONDS=2
export ALGO_SCREENER_TOP_N=5
export ALGO_LOGGING_JSON_FORMAT=false
export ALGO_LOGGING_LEVEL=INFO
export API_PORT=18080

echo "============================================================"
echo "  Algo-Trade Paper-Trade Demo"
echo "  Using: mock market adapter + mock broker"
echo "  Polling interval: 2 seconds | Top N: 5"
echo "  API server: http://localhost:${API_PORT}"
echo "  Press Ctrl+C to stop."
echo "============================================================"
echo ""

# Run the pipeline for 30 seconds then exit.
timeout 30 python -m src.cli.main --mode paper --config "${CONFIG_PATH}" || true

echo ""
echo "============================================================"
echo "  Demo complete. Check logs above for SIGNAL GENERATED events."
echo "  To run backtest: python scripts/backtest.py sample_data/minute_sample.csv"
echo "============================================================"
