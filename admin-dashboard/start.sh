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

echo ""
echo "  Starting Euler Admin Dashboard..."
echo ""
python server.py "$@"
