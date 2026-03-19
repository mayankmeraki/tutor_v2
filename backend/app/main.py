"""FastAPI app — Sub-Agent Teaching Architecture."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, chat, content, events, ingestion, learning_tools, sessions

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)

RENDERED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rendered")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(RENDERED_DIR, exist_ok=True)

    # Ensure MongoDB indexes
    from app.services.user_service import ensure_indexes
    try:
        await ensure_indexes()
    except Exception as e:
        log.warning("Failed to ensure user indexes (MongoDB may be unreachable): %s", e)

    # Ensure BYO pipeline indexes
    from app.services.byo_indexes import ensure_byo_indexes
    try:
        await ensure_byo_indexes()
    except Exception as e:
        log.warning("Failed to ensure BYO indexes (MongoDB may be unreachable): %s", e)

    # Register centralized LLM usage tracking callback
    from app.core.llm import set_usage_callback, LLMResponse, LLMCallMetadata
    from app.agents.session import _sessions

    def _on_llm_usage(response: LLMResponse, metadata: LLMCallMetadata) -> None:
        if metadata.session_id and metadata.session_id in _sessions:
            _sessions[metadata.session_id].track_llm_usage(
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                provider_cost_usd=response.usage.cost_usd,
            )

    set_usage_callback(_on_llm_usage)

    from app.core.config import settings
    log.info("Mockup Teaching Agent — Python Backend")
    log.info("Server:         http://0.0.0.0:%s", settings.PORT)
    log.info("Tutor Model:    %s", settings.TUTOR_MODEL)
    log.info("Planning Model: %s", settings.PLANNING_MODEL)
    log.info("Research Model: %s", settings.RESEARCH_MODEL)
    log.info("API Key:        %s", "set" if settings.ANTHROPIC_API_KEY else "MISSING")
    yield

    # ── Shutdown: close DB connections ──
    log.info("Shutting down — closing database connections…")
    try:
        from app.core.mongodb import get_mongo_client
        get_mongo_client().close()
    except Exception as e:
        log.warning("MongoDB close error: %s", e)
    try:
        from app.core.database import async_engine
        await async_engine.dispose()
    except Exception as e:
        log.warning("Postgres dispose error: %s", e)


app = FastAPI(lifespan=lifespan)

# ─── CORS ──────────────────────────────────────────────────────────

_cors_env = os.environ.get("CORS_ORIGINS", "")
if _cors_env:
    # Production: use only configured origins
    _all_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    # Local dev: allow localhost
    _all_origins = [
        "http://localhost:3001",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_all_origins,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ─── Health Check ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check — pings MongoDB and returns status."""
    mongo_ok = False
    try:
        from app.core.mongodb import get_mongo_client
        result = await get_mongo_client().admin.command("ping")
        mongo_ok = result.get("ok") == 1.0
    except Exception as e:
        log.warning("Health check — MongoDB ping failed: %s", e)
    return JSONResponse(
        status_code=200 if mongo_ok else 503,
        content={"status": "ok" if mongo_ok else "degraded", "mongo": mongo_ok},
    )


# API routes
app.include_router(auth.router)
app.include_router(content.router)
app.include_router(learning_tools.router)
app.include_router(sessions.router)
app.include_router(events.router)
app.include_router(ingestion.router)
app.include_router(chat.router)

# Static files: rendered Manim output
os.makedirs(RENDERED_DIR, exist_ok=True)
app.mount("/rendered", StaticFiles(directory=RENDERED_DIR), name="rendered")

# SPA fallback — serve index.html for known client-side routes.
# Registered before the static-files mount so they take priority.
_index_html = os.path.join(FRONTEND_DIR, "index.html")

@app.get("/login")
@app.get("/login/")
@app.get("/dashboard")
@app.get("/dashboard/")
@app.get("/session/{session_id}")
@app.get("/session/")
@app.get("/session")
async def spa_fallback(session_id: str = ""):
    return FileResponse(_index_html, media_type="text/html")

# Static files: frontend (must be last — catch-all mount)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
