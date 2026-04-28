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

CMD ["python", "/app/byo/worker_entrypoint.py"]
