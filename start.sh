#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/backend"

# Create venv if needed
if [ ! -d .venv ]; then
    echo "Creating Python venv..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Only re-install if pyproject.toml changed since last install
MARKER=".venv/.deps_installed"
if [ ! -f "$MARKER" ] || [ pyproject.toml -nt "$MARKER" ]; then
    echo "Installing dependencies..."
    pip install -q -e .
    touch "$MARKER"
else
    echo "Dependencies up to date."
fi

# Free port 3001 if already in use (timeout lsof at 3s to avoid hangs)
PIDS=$(timeout 3 lsof -ti :3001 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "Stopping existing process on port 3001 (PIDs: $PIDS)..."
  echo "$PIDS" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

echo ""
echo "Starting server on http://localhost:3001 ..."

# Default: run BYO worker embedded (in-process).
# If you're running start_services.sh separately, set BYO_WORKER_EXTERNAL=true
# to avoid running two workers:
#   BYO_WORKER_EXTERNAL=true ./start.sh
echo " BYO worker: ${BYO_WORKER_EXTERNAL:-embedded (set BYO_WORKER_EXTERNAL=true if running start_services.sh)}"
echo ""

exec uvicorn app.main:app --host 0.0.0.0 --port 3001 --app-dir .
