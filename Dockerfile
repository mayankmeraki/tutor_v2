FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/setup.cfg* ./backend/
COPY backend/app ./backend/app

RUN pip install --no-cache-dir -e ./backend

# BYO pipeline module (sits alongside backend, imported as `byo.*`)
COPY byo ./byo

# ── Backend API target (Cloud Run) ──────────────────────
FROM base AS backend

COPY frontend ./frontend

ENV PORT=8080
EXPOSE 8080

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --app-dir /app/backend

# ── BYO Worker target (VM / Cloud Run) ──────────────────
FROM base AS worker

ENV PORT=8080
EXPOSE 8080

# Health check server for Cloud Run + worker loop
CMD python -c "\
import asyncio, threading; \
from http.server import HTTPServer, BaseHTTPRequestHandler; \
class H(BaseHTTPRequestHandler): \
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b'ok'); \
    def log_message(self, *a): pass; \
threading.Thread(target=lambda: HTTPServer(('',8080), H).serve_forever(), daemon=True).start(); \
import byo.worker; byo.worker._check_env(); asyncio.run(byo.worker.main())"
