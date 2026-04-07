#!/bin/bash
set -e

# Python backend listens on this internal port (not publicly exposed).
export API_PORT=${API_PORT:-8181}

echo "[entrypoint] Starting Python backend on port $API_PORT..."
python -m src.cli.main --mode "${MODE:-paper}" &
BACKEND_PID=$!

# Give backend a few seconds to bind its port before Next.js starts proxying.
sleep 5

# Railway injects PORT; Next.js standalone server respects it.
export PORT=${PORT:-3000}
export HOSTNAME="0.0.0.0"

echo "[entrypoint] Starting Next.js frontend on port $PORT..."
cd /app/frontend
node server.js &
FRONTEND_PID=$!

echo "[entrypoint] Both services running. Backend PID=$BACKEND_PID, Frontend PID=$FRONTEND_PID"

# Exit (and bring down the container) if either process dies.
wait -n $BACKEND_PID $FRONTEND_PID
EXIT_CODE=$?
echo "[entrypoint] A process exited with code $EXIT_CODE — shutting down."
kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
exit $EXIT_CODE
