#!/bin/bash
set -e

# Railway injects PORT. Fall back to API_PORT or 8181 for local runs.
export PORT=${PORT:-${API_PORT:-8181}}
export API_PORT=$PORT

echo "[entrypoint] Starting trading engine on port $PORT (mode: ${MODE:-paper})..."
exec python -m src.cli.main --mode "${MODE:-paper}"
