#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

VENV="../backend/.venv"

if [ ! -d "$VENV" ]; then
    echo "Backend venv not found at $VENV — creating local venv..."
    python3 -m venv .venv
    VENV=".venv"
    source "$VENV/bin/activate"
    pip install -q -r requirements.txt
else
    source "$VENV/bin/activate"
fi

# ── Resolve port (default 4000, can be overridden by --port flag or DASHBOARD_PORT env var) ──
PORT="${DASHBOARD_PORT:-4000}"
for ((i=1; i<=$#; i++)); do
    if [[ "${!i}" == "--port" ]]; then
        next=$((i+1))
        PORT="${!next}"
        break
    fi
done

# ── Free the port if a stale dashboard is holding it ──
EXISTING=$(lsof -ti:"$PORT" 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
    echo "  Port $PORT is in use by PID(s): $EXISTING — stopping them first"
    kill $EXISTING 2>/dev/null || true
    sleep 1
    STILL=$(lsof -ti:"$PORT" 2>/dev/null || true)
    if [ -n "$STILL" ]; then
        echo "  Force-killing PID(s): $STILL"
        kill -9 $STILL 2>/dev/null || true
        sleep 1
    fi
fi

echo ""
echo "  Starting Euler Admin Dashboard on port $PORT..."
echo ""
exec python server.py "$@"
