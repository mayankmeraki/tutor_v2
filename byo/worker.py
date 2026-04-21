#!/usr/bin/env python3
"""BYO Pipeline Worker — standalone service for processing uploaded resources.

Runs independently of the main app server. Polls MongoDB for jobs,
processes them (extract → chunk → classify → embed → store), and
updates resource status.

Usage:
    python -m byo.worker                    # run with defaults
    python -m byo.worker --concurrent 5     # 5 parallel jobs

Environment:
    MONGODB_URI          — MongoDB connection string (required)
    OPENROUTER_API_KEY   — for embeddings, classification, image description
    QDRANT_URL           — for vector storage
    QDRANT_API_KEY       — for vector storage auth
    BYO_GCS_BUCKET       — GCS bucket for file storage
"""

import asyncio
import logging
import os
import signal
import sys

# Ensure the project root is on the path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "backend"))

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "severity": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("byo.worker")


def _check_env():
    """Validate required environment variables before starting."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(_root, "backend", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
            log.info("Loaded env from %s", env_path)
    except ImportError:
        log.warning("python-dotenv not installed — reading env vars directly")

    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        log.error("MONGODB_URI not set. Add it to backend/.env or export it.")
        sys.exit(1)

    openrouter = os.environ.get("OPENROUTER_API_KEY", "")
    qdrant_url = os.environ.get("QDRANT_URL", "")
    qdrant_key = os.environ.get("QDRANT_API_KEY", "")
    gcs_bucket = os.environ.get("BYO_GCS_BUCKET", "capacity-byo-uploads")

    log.info("═══ BYO Worker Environment ═══")
    log.info("  MONGODB_URI:        %s...%s", uri[:25], uri[-10:] if len(uri) > 35 else "")
    log.info("  OPENROUTER_API_KEY: %s", "set" if openrouter else "MISSING — embeddings degraded")
    log.info("  QDRANT_URL:         %s", qdrant_url or "not set — vector storage disabled")
    log.info("  QDRANT_API_KEY:     %s", "set" if qdrant_key else "not set")
    log.info("  BYO_GCS_BUCKET:     %s", gcs_bucket)
    log.info("═══════════════════════════════")


async def main(concurrent: int = 3):
    """Run the BYO worker with auto-restart on crash."""
    from byo.processing.orchestrator import run_worker, MAX_CONCURRENT_JOBS

    actual_concurrent = concurrent or MAX_CONCURRENT_JOBS
    log.info("BYO Worker starting (concurrent=%d)", actual_concurrent)

    shutdown = asyncio.Event()

    def handle_signal():
        log.info("Shutdown signal received")
        shutdown.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    consecutive_crashes = 0
    while not shutdown.is_set():
        try:
            log.info("Worker loop starting (crash count: %d)", consecutive_crashes)
            worker_task = asyncio.create_task(run_worker())

            # Wait for either worker completion or shutdown signal
            done, _ = await asyncio.wait(
                [worker_task, asyncio.create_task(shutdown.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if shutdown.is_set():
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass
                break

            # Worker exited (shouldn't happen) — check for errors
            for task in done:
                if task.exception():
                    raise task.exception()

            consecutive_crashes = 0

        except asyncio.CancelledError:
            break
        except Exception as e:
            consecutive_crashes += 1
            backoff = min(60, 5 * consecutive_crashes)
            log.error("Worker crashed (attempt %d) — restarting in %ds: %s",
                      consecutive_crashes, backoff, e, exc_info=True)
            await asyncio.sleep(backoff)

    log.info("BYO Worker stopped")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BYO Pipeline Worker")
    parser.add_argument("--concurrent", type=int, default=3, help="Max concurrent jobs")
    args = parser.parse_args()

    _check_env()
    asyncio.run(main(concurrent=args.concurrent))
