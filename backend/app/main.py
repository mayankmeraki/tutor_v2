"""FastAPI app — Sub-Agent Teaching Architecture."""

import logging
import os
from contextlib import asynccontextmanager

from app.core.logging_config import setup_logging

setup_logging()  # Must be called before any other module logs

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings

from app.api.routes import artifacts, auth, chat, content, events, learning_tools, sessions

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

    # Ensure session indexes
    from app.services.session_service import ensure_session_indexes
    try:
        await ensure_session_indexes()
    except Exception as e:
        log.warning("Failed to ensure session indexes: %s", e)

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
    log.info("Tutor Model:    %s", settings.tutor_model)
    log.info("Euler Model:    %s", settings.euler_model)
    log.info("Fast Model:     %s", settings.MODEL_FAST)
    log.info("LLM Provider:   %s", settings.LLM_PROVIDER)
    _key = settings.OPENROUTER_API_KEY if settings.LLM_PROVIDER == "openrouter" else settings.ANTHROPIC_API_KEY
    log.info("API Key:        %s", "set" if _key else "MISSING")
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


@app.get("/api/config")
async def get_config():
    """Return frontend-safe config values. No secrets exposed."""
    return {
        "tts_enabled": bool(settings.ELEVENLABS_API_KEY),
    }


@app.post("/api/tts")
async def tts_proxy(request: Request):
    """Proxy TTS requests to ElevenLabs — keeps API key server-side.
    Requires auth + rate limited to prevent quota abuse.
    """
    # Auth check — required
    from app.api.routes.auth import get_optional_user
    try:
        await get_optional_user(request)
    except Exception:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    # Rate limit
    from app.core.rate_limit import check_rate_limit_tts
    try:
        await check_rate_limit_tts(request)
    except Exception as e:
        return JSONResponse(status_code=429, content={"error": str(e.detail) if hasattr(e, 'detail') else "Rate limited"})

    if not settings.ELEVENLABS_API_KEY:
        return JSONResponse(status_code=503, content={"error": "TTS not configured"})

    body = await request.json()
    text = body.get("text", "")
    voice_id = body.get("voice_id", "UgBBYS2sOqTuMpoF3BR0")

    if not text or len(text) > 500:
        return JSONResponse(status_code=400, content={"error": "Text required, max 500 chars"})

    import httpx
    from starlette.responses import StreamingResponse

    async def _stream_tts():
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": "eleven_turbo_v2_5",
                    "voice_settings": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.2},
                    "optimize_streaming_latency": 4,
                },
            ) as resp:
                if resp.status_code != 200:
                    yield b""
                    return
                async for chunk in resp.aiter_bytes(chunk_size=4096):
                    yield chunk

    try:
        return StreamingResponse(
            content=_stream_tts(),
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-cache",
                "Transfer-Encoding": "chunked",
            },
        )
    except Exception as e:
        log.warning("TTS proxy error: %s", e)
        return JSONResponse(status_code=502, content={"error": "TTS proxy failed"})


# ── Animation Code Fix (Haiku — fast, cheap) ─────────────────

@app.post("/api/fix-animation")
async def fix_animation(request: Request):
    """Fix broken p5.js animation code using Haiku (fast, cheap).
    Takes broken code + error, returns fixed code.
    """
    from app.api.routes.auth import get_optional_user
    try:
        await get_optional_user(request)
    except Exception:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    body = await request.json()
    broken_code = body.get("code", "")
    error_msg = body.get("error", "")

    if not broken_code:
        return JSONResponse(status_code=400, content={"error": "code is required"})

    import httpx

    # Use Haiku via OpenRouter for speed (< 2s typically)
    api_key = settings.OPENROUTER_API_KEY or settings.ANTHROPIC_API_KEY
    if not api_key:
        return JSONResponse(status_code=503, content={"error": "No API key configured"})

    is_openrouter = bool(settings.OPENROUTER_API_KEY)
    base_url = "https://openrouter.ai/api/v1" if is_openrouter else "https://api.anthropic.com/v1"
    model = "anthropic/claude-4.5-haiku-20251001" if is_openrouter else "claude-haiku-4-5-20251001"

    system_prompt = (
        "You are a p5.js animation fixer. Return ONLY fixed JavaScript — no explanation, no markdown fences.\n"
        "The code runs inside: new Function('p', 'W', 'H', code)\n"
        "Pre-injected: p (p5 instance), W/H (canvas size in px), S (scale factor for text/strokes).\n\n"
        "CRITICAL RULES for the fix:\n"
        "- p.createCanvas(W, H) in setup (NOT p.WEBGL unless the original used it)\n"
        "- p.background(15, 20, 16) as FIRST line in draw()\n"
        "- Use VISIBLE colors: p.stroke(52,211,153) green, p.stroke(251,191,36) gold, p.stroke(83,216,251) cyan\n"
        "- Call p.stroke() or p.fill() BEFORE drawing any shape\n"
        "- Use p.strokeWeight(2*S) for visible lines\n"
        "- ALL coordinates relative to W,H: e.g., x=W*0.1, y=H*0.5\n"
        "- NO p.text() calls — labels go outside the animation\n"
        "- Keep code under 30 lines, simple shapes (lines, ellipses, rects)\n\n"
        "Common blank-canvas causes: missing stroke/fill, coordinates outside canvas, "
        "drawing with background color, no beginShape/endShape pair, using p.WEBGL accidentally.\n"
        "If the original code is too complex to fix, REWRITE it simply with the same visual concept."
    )

    user_msg = f"ERROR: {error_msg}\n\nBROKEN CODE:\n{broken_code[:3000]}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if is_openrouter:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_msg},
                        ],
                        "max_tokens": 4000,
                        "temperature": 0,
                    },
                )
                if resp.status_code != 200:
                    return JSONResponse(status_code=502, content={"error": f"LLM error: {resp.status_code}"})
                data = resp.json()
                fixed = data["choices"][0]["message"]["content"]
            else:
                resp = await client.post(
                    f"{base_url}/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_msg}],
                        "max_tokens": 4000,
                        "temperature": 0,
                    },
                )
                if resp.status_code != 200:
                    return JSONResponse(status_code=502, content={"error": f"LLM error: {resp.status_code}"})
                data = resp.json()
                fixed = data["content"][0]["text"]

        # Strip markdown fences if Haiku wrapped them
        fixed = fixed.strip()
        if fixed.startswith("```"):
            fixed = fixed.split("\n", 1)[1] if "\n" in fixed else fixed[3:]
        if fixed.endswith("```"):
            fixed = fixed[:-3].rstrip()

        return JSONResponse(content={"code": fixed})
    except Exception as e:
        log.warning("fix-animation error: %s", e)
        return JSONResponse(status_code=502, content={"error": str(e)})


# API routes
app.include_router(auth.router)
app.include_router(artifacts.router)
app.include_router(content.router)
app.include_router(learning_tools.router)
app.include_router(sessions.router)
app.include_router(events.router)
app.include_router(chat.router)

# Euler (Orchestrator) — Home screen agent
from app.orchestrator.api import router as euler_router
app.include_router(euler_router)

# BYO — Student materials upload
try:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from byo.api.collections import router as byo_router
    app.include_router(byo_router)
except Exception as e:
    log.warning("BYO routes not loaded: %s", e)


# ─── Admin / management endpoints ────────────────────────────────

@app.post("/api/admin/backfill-vectors")
async def backfill_vectors(request: Request):
    """Backfill vector embeddings for all existing knowledge notes.

    POST /api/admin/backfill-vectors?dry_run=true  — preview what would be synced
    POST /api/admin/backfill-vectors               — actually run the backfill
    """
    from app.services.knowledge_state import backfill_vector_index
    from app.api.routes.auth import get_current_user

    # Require auth
    try:
        user = await get_current_user(request)
    except Exception:
        return {"error": "Authentication required"}, 401

    dry_run = request.query_params.get("dry_run", "").lower() in ("true", "1", "yes")
    stats = await backfill_vector_index(dry_run=dry_run)
    return {"ok": True, "dry_run": dry_run, **stats}


# Static files: rendered Manim output
os.makedirs(RENDERED_DIR, exist_ok=True)
app.mount("/rendered", StaticFiles(directory=RENDERED_DIR), name="rendered")

# SPA fallback — serve index.html for known client-side routes.
# Registered before the static-files mount so they take priority.
_index_html = os.path.join(FRONTEND_DIR, "index.html")

@app.get("/login")
@app.get("/login/")
@app.get("/home")
@app.get("/home/")
@app.get("/dashboard")
@app.get("/dashboard/")
@app.get("/courses")
@app.get("/courses/")
@app.get("/courses/{course_id}")
@app.get("/tutor")
@app.get("/tutor/")
@app.get("/session/{session_id}")
@app.get("/session/")
@app.get("/session")
async def spa_fallback(session_id: str = "", course_id: str = ""):
    return FileResponse(_index_html, media_type="text/html")

# Static files: frontend (must be last — catch-all mount)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
