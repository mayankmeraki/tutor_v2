#!/usr/bin/env bash
set -euo pipefail

# ─── BYO Pipeline Worker ───────────────────────────────────
# Processes uploaded resources (extract → chunk → embed → store).
# Runs independently of the main app server.
#
# Usage:
#   ./scripts/start_byo.sh              # default 3 concurrent jobs
#   ./scripts/start_byo.sh 5            # 5 concurrent jobs
# ────────────────────────────────────────────────────────────

CONCURRENT="${1:-3}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT/backend"

# Activate venv
if [ ! -d .venv ]; then
    echo "ERROR: No .venv found. Run ./start.sh first to set up the environment."
    exit 1
fi
source .venv/bin/activate

# Load env
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Validate required env
if [ -z "${MONGODB_URI:-}" ]; then
    echo "ERROR: MONGODB_URI not set. Check backend/.env"
    exit 1
fi

# Tell the main app server to skip its embedded worker
export BYO_WORKER_EXTERNAL=true

echo "═══════════════════════════════════════════"
echo " BYO Pipeline Worker"
echo "═══════════════════════════════════════════"
echo " Concurrent jobs:  $CONCURRENT"
echo " MongoDB:          ${MONGODB_URI:0:30}..."
echo " OpenRouter:       $([ -n "${OPENROUTER_API_KEY:-}" ] && echo 'set' || echo 'MISSING')"
echo " Qdrant:           ${QDRANT_URL:-not set}"
echo "═══════════════════════════════════════════"
echo ""

cd "$ROOT"
exec python -m byo.worker --concurrent "$CONCURRENT"
