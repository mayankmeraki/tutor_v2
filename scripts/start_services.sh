#!/usr/bin/env bash
set -euo pipefail

# ─── Euler Extra Services ─────────────────────────────────
# Starts all non-tutor services:
#   1. BYO Pipeline Worker (document processing)
#   2. Judge0 Code Execution Engine (DSA test runner)
#
# Usage:
#   ./scripts/start_services.sh              # start all
#   ./scripts/start_services.sh --no-judge   # skip Judge0
#   ./scripts/start_services.sh --no-byo     # skip BYO worker
# ────────────────────────────────────────────────────────────

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BYO_CONCURRENT=3
SKIP_JUDGE=false
SKIP_BYO=false

for arg in "$@"; do
  case $arg in
    --no-judge) SKIP_JUDGE=true ;;
    --no-byo) SKIP_BYO=true ;;
    --concurrent=*) BYO_CONCURRENT="${arg#*=}" ;;
  esac
done

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

# Tell main app to skip embedded BYO worker
export BYO_WORKER_EXTERNAL=true

echo ""
echo "═══════════════════════════════════════════════════"
echo " Euler Services"
echo "═══════════════════════════════════════════════════"
echo " MongoDB:      ${MONGODB_URI:+${MONGODB_URI:0:30}...}${MONGODB_URI:-NOT SET}"
echo " OpenRouter:   ${OPENROUTER_API_KEY:+set}${OPENROUTER_API_KEY:-MISSING}"
echo " Qdrant:       ${QDRANT_URL:-not set}"
echo " Judge0:       ${JUDGE0_URL:-http://localhost:2358}"
echo "═══════════════════════════════════════════════════"
echo ""

PIDS=()

cleanup() {
    echo ""
    echo "Stopping services..."
    for pid in "${PIDS[@]+"${PIDS[@]}"}"; do
        kill "$pid" 2>/dev/null || true
    done
    # Stop Judge0 containers
    if [ "$SKIP_JUDGE" = false ]; then
        docker-compose -f "$ROOT/docker-compose.judge0.yml" down 2>/dev/null || true
    fi
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

# ── 1. Judge0 Code Execution ──────────────────────────────
if [ "$SKIP_JUDGE" = false ]; then
    echo "▸ Starting Judge0 (code execution engine)..."
    if ! command -v docker-compose &>/dev/null && ! command -v docker &>/dev/null; then
        echo "  ⚠ Docker not found — skipping Judge0"
        echo "  Install Docker to enable code execution: https://docs.docker.com/get-docker/"
    else
        cd "$ROOT"
        # Use docker compose v2 syntax if available, fall back to v1
        if docker compose version &>/dev/null 2>&1; then
            docker compose -f docker-compose.judge0.yml up -d 2>&1 | sed 's/^/  /'
        else
            docker-compose -f docker-compose.judge0.yml up -d 2>&1 | sed 's/^/  /'
        fi
        echo "  ✓ Judge0 running on ${JUDGE0_URL:-http://localhost:2358}"
        echo ""
    fi
fi

# ── 2. BYO Pipeline Worker ────────────────────────────────
if [ "$SKIP_BYO" = false ]; then
    if [ -z "${MONGODB_URI:-}" ]; then
        echo "▸ Skipping BYO worker — MONGODB_URI not set"
    else
        echo "▸ Starting BYO Pipeline Worker (${BYO_CONCURRENT} concurrent jobs)..."
        cd "$ROOT"
        python -m byo.worker --concurrent "$BYO_CONCURRENT" &
        BYO_PID=$!
        PIDS+=($BYO_PID)
        echo "  ✓ BYO worker running (PID $BYO_PID)"
        echo ""
    fi
fi

echo "═══════════════════════════════════════════════════"
echo " All services running. Press Ctrl+C to stop."
echo "═══════════════════════════════════════════════════"
echo ""

# Wait for background processes
wait
