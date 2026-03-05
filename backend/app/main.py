"""FastAPI app — Two-Agent Teaching Architecture (Python port of server.js)."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import chat, content, learning_tools, sessions

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

RENDERED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rendered")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(RENDERED_DIR, exist_ok=True)
    from app.core.config import settings
    print(f"\n  Mockup Teaching Agent — Python Backend")
    print(f"  ─────────────────────────────────────────────────")
    print(f"  Server:         http://localhost:{settings.PORT}")
    print(f"  Director Model: {settings.DIRECTOR_MODEL}")
    print(f"  Tutor Model:    {settings.TUTOR_MODEL}")
    print(f"  API Key:        {'set' if settings.ANTHROPIC_API_KEY else 'MISSING'}")
    print(f"\n  Logs below\n")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(content.router)
app.include_router(learning_tools.router)
app.include_router(sessions.router)
app.include_router(chat.router)

# Static files: rendered Manim output
app.mount("/rendered", StaticFiles(directory=RENDERED_DIR), name="rendered")

# Static files: frontend (must be last — catch-all with html=True)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
