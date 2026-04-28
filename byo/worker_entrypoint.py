"""BYO Worker entrypoint for Cloud Run.

Starts a minimal HTTP health check server on PORT (default 8080)
so Cloud Run knows the container is alive, then runs the worker loop.
"""

import asyncio
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add project root to path so both `app.*` and `byo.*` imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *args):
        pass  # suppress access logs


def start_health_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('', port), HealthHandler)
    print(f"[BYO Worker] Health check listening on :{port}")
    server.serve_forever()


def main():
    # Start health check in background thread
    threading.Thread(target=start_health_server, daemon=True).start()

    # Load env
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

    # Run worker
    from byo.processing.orchestrator import run_worker
    print("[BYO Worker] Starting processing loop...")
    asyncio.run(run_worker())


if __name__ == '__main__':
    main()
