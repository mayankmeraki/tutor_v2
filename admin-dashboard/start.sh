#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Line-buffered Python logs (otherwise output can look "stuck" until buffer fills)
export PYTHONUNBUFFERED=1

VENV="../backend/.venv"

if [ ! -d "$VENV" ]; then
    echo "Backend venv not found at $VENV - creating local venv..."
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

# ── Free the port: bind probe + lsof (4s cap) + SIGKILL, repeat until free or fail ──
if [ "${DASHBOARD_SKIP_PORT_FREE:-}" != "1" ]; then
    export DASHBOARD_BIND_CHECK_PORT="$PORT"
    python3 <<'PY'
import errno, os, signal, socket, subprocess, sys, time

port = int(os.environ["DASHBOARD_BIND_CHECK_PORT"])
max_rounds = 12


def try_bind():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", port))
        return s
    except OSError as e:
        s.close()
        if e.errno == errno.EADDRINUSE:
            return None
        raise


def lsof_pids():
    try:
        r = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=4,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    out = (r.stdout or "").strip()
    if not out:
        return []
    pids = []
    for tok in out.replace("\n", " ").split():
        if tok.isdigit():
            pids.append(int(tok))
    return list(dict.fromkeys(pids))


for i in range(max_rounds):
    sk = try_bind()
    if sk is not None:
        sk.close()
        if i:
            print(f"  OK Port {port} is free after cleanup ({i} round(s)).", flush=True)
        sys.exit(0)

    pids = lsof_pids()
    if pids:
        print(
            f"  Port {port} in use (round {i + 1}/{max_rounds}) - PID(s): "
            + " ".join(str(p) for p in pids)
            + " - SIGKILL",
            flush=True,
        )
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                print(f"  WARN cannot kill PID {pid} (need same user or sudo)", flush=True)
    else:
        print(
            f"  Port {port} in use but lsof found no PID (round {i + 1}/{max_rounds}); waiting...",
            flush=True,
        )
    time.sleep(0.7)

print(
    f"  ERROR Port {port} still busy after {max_rounds} rounds. "
    "Use another port: ./start.sh --port 4010  or  DASHBOARD_SKIP_PORT_FREE=1 ./start.sh",
    flush=True,
)
sys.exit(1)
PY
    unset DASHBOARD_BIND_CHECK_PORT
fi

echo ""
echo "  Starting Euler Admin Dashboard on port $PORT..."
echo ""
exec python3 server.py "$@"
