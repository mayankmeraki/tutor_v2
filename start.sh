#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/backend"

# Create venv if needed
if [ ! -d .venv ]; then
    echo "Creating Python venv..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install deps
echo "Installing dependencies..."
pip install -q -e .

# Install manim if not already installed
if ! command -v manim &>/dev/null && ! .venv/bin/manim --version &>/dev/null 2>&1; then
    echo "Installing manim..."
    pip install -q manim
fi

# Free port 3001 if already in use (e.g. leftover from previous run)
if command -v lsof &>/dev/null; then
  PIDS=$(lsof -ti :3001 2>/dev/null) || true
  if [ -n "$PIDS" ]; then
    echo "Stopping existing process on port 3001..."
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
fi

echo ""
echo "Starting server..."
uvicorn app.main:app --host 0.0.0.0 --port 3001 --app-dir .
