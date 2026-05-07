"""Centralized usage tracking — logs every LLM/TTS/STT call to MongoDB.

Every API call (LLM, embedding, TTS, STT, rerank) goes through here.
Stored in `usage_log` collection, queryable by user, purpose, date.
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import yaml

log = logging.getLogger(__name__)

# ── Load model registry ──────────────────────────────────────────

_MODELS_YAML = os.path.join(os.path.dirname(__file__), "models.yaml")
_registry: dict = {}
_purposes: dict = {}
_voice: dict = {}


def _load_registry():
    global _registry, _purposes, _voice
    try:
        with open(_MODELS_YAML) as f:
            data = yaml.safe_load(f)
        _registry = data.get("models", {})
        _purposes = data.get("purposes", {})
        _voice = data.get("voice", {})
    except Exception as e:
        log.warning("Failed to load models.yaml: %s", e)


def get_model_pricing(model_id: str) -> dict:
    """Get pricing info for a model. Returns defaults if not found."""
    if not _registry:
        _load_registry()
    # Try exact match, then prefix match
    info = _registry.get(model_id)
    if not info:
        # OpenRouter sometimes appends version suffixes
        for key, val in _registry.items():
            if model_id.startswith(key) or key.startswith(model_id):
                info = val
                break
    return info or {"input": 1.0, "output": 3.0, "cached_input": 0.5}


def compute_cost_usd(
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    provider_cost_usd: float | None = None,
) -> float:
    """Compute cost in USD. Prefers provider-reported cost if available."""
    if provider_cost_usd is not None and provider_cost_usd > 0:
        return provider_cost_usd

    pricing = get_model_pricing(model_id)
    uncached_input = max(0, input_tokens - cached_tokens)
    cost = (
        (uncached_input / 1_000_000) * pricing.get("input", 1.0)
        + (cached_tokens / 1_000_000) * pricing.get("cached_input", pricing.get("input", 1.0) * 0.1)
        + (output_tokens / 1_000_000) * pricing.get("output", 3.0)
    )
    return cost


def compute_tts_cost_usd(char_count: int, model: str = "eleven_turbo_v2_5") -> float:
    """Compute TTS cost based on character count."""
    if not _voice:
        _load_registry()
    tts_info = _voice.get("elevenlabs_tts", {})
    rate = tts_info.get("cost_per_1k_chars_usd", 0.30)
    return (char_count / 1000) * rate


def compute_stt_cost_usd(duration_seconds: float) -> float:
    """Compute STT cost based on audio duration."""
    if not _voice:
        _load_registry()
    stt_info = _voice.get("elevenlabs_scribe", {})
    rate = stt_info.get("cost_per_minute_usd", 0.40)
    return (duration_seconds / 60) * rate


# ── Usage log entry ──────────────────────────────────────────────

class UsageEntry:
    """A single usage log entry ready to be persisted."""

    __slots__ = (
        "timestamp", "user_id", "purpose", "model", "call_type",
        "input_tokens", "output_tokens", "cached_tokens",
        "cost_usd", "duration_ms",
        "session_id", "path_id", "resource_id", "collection_id",
        "extra",
    )

    def __init__(
        self,
        purpose: str,
        model: str = "",
        call_type: str = "llm",  # llm, embed, tts, stt, rerank
        user_id: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        cost_usd: float = 0.0,
        duration_ms: int = 0,
        session_id: str = "",
        path_id: str = "",
        resource_id: str = "",
        collection_id: str = "",
        extra: dict | None = None,
    ):
        self.timestamp = datetime.now(timezone.utc)
        self.user_id = user_id
        self.purpose = purpose
        self.model = model
        self.call_type = call_type
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cached_tokens = cached_tokens
        self.cost_usd = cost_usd
        self.duration_ms = duration_ms
        self.session_id = session_id
        self.path_id = path_id
        self.resource_id = resource_id
        self.collection_id = collection_id
        self.extra = extra or {}

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "userId": self.user_id,
            "purpose": self.purpose,
            "model": self.model,
            "callType": self.call_type,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cachedTokens": self.cached_tokens,
            "costUsd": round(self.cost_usd, 6),
            "costCents": round(self.cost_usd * 100, 4),
            "durationMs": self.duration_ms,
        }
        # Only include non-empty optional fields
        if self.session_id:
            d["sessionId"] = self.session_id
        if self.path_id:
            d["pathId"] = self.path_id
        if self.resource_id:
            d["resourceId"] = self.resource_id
        if self.collection_id:
            d["collectionId"] = self.collection_id
        if self.extra:
            d["extra"] = self.extra
        return d


# ── Async logger (fire-and-forget to MongoDB) ────────────────────

_buffer: list[dict] = []
_BUFFER_SIZE = 10
_FLUSH_INTERVAL_S = 30
_last_flush: float = 0


async def log_usage(entry: UsageEntry):
    """Log a usage entry. Buffered — flushes every 10 entries or 30 seconds."""
    global _last_flush
    _buffer.append(entry.to_dict())

    now = time.monotonic()
    if len(_buffer) >= _BUFFER_SIZE or (now - _last_flush > _FLUSH_INTERVAL_S and _buffer):
        await _flush()
        _last_flush = now


async def _flush():
    """Write buffered entries to MongoDB."""
    if not _buffer:
        return
    batch = _buffer.copy()
    _buffer.clear()
    try:
        from app.core.mongodb import get_tutor_db
        db = get_tutor_db()
        await db.usage_log.insert_many(batch, ordered=False)
        log.debug("Usage log flushed: %d entries", len(batch))
    except Exception as e:
        log.warning("Usage log flush failed (%d entries lost): %s", len(batch), e)


async def flush_now():
    """Force flush — call on shutdown."""
    await _flush()


async def ensure_usage_indexes():
    """Create indexes on the usage_log collection."""
    try:
        from app.core.mongodb import get_tutor_db
        db = get_tutor_db()
        await db.usage_log.create_index([("userId", 1), ("timestamp", -1)])
        await db.usage_log.create_index([("purpose", 1), ("timestamp", -1)])
        await db.usage_log.create_index([("sessionId", 1)])
        await db.usage_log.create_index([("timestamp", -1)])
        await db.usage_log.create_index([("callType", 1), ("timestamp", -1)])
        log.info("Usage log indexes ensured")
    except Exception as e:
        log.warning("Usage log indexes failed: %s", e)


# ── Query helpers (for admin dashboard) ──────────────────────────

async def get_user_usage(user_id: str, days: int = 30) -> dict:
    """Get usage summary for a user over N days."""
    from app.core.mongodb import get_tutor_db
    db = get_tutor_db()
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    from datetime import timedelta
    cutoff -= timedelta(days=days)

    pipeline = [
        {"$match": {"userId": user_id, "timestamp": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$purpose",
            "totalCostUsd": {"$sum": "$costUsd"},
            "totalInputTokens": {"$sum": "$inputTokens"},
            "totalOutputTokens": {"$sum": "$outputTokens"},
            "callCount": {"$sum": 1},
        }},
        {"$sort": {"totalCostUsd": -1}},
    ]
    results = await db.usage_log.aggregate(pipeline).to_list(100)
    total = sum(r["totalCostUsd"] for r in results)
    return {
        "userId": user_id,
        "days": days,
        "totalCostUsd": round(total, 4),
        "totalCostCents": round(total * 100, 2),
        "byPurpose": {r["_id"]: {
            "costUsd": round(r["totalCostUsd"], 4),
            "inputTokens": r["totalInputTokens"],
            "outputTokens": r["totalOutputTokens"],
            "calls": r["callCount"],
        } for r in results},
    }


async def get_global_usage(days: int = 30) -> dict:
    """Get global usage summary across all users."""
    from app.core.mongodb import get_tutor_db
    db = get_tutor_db()
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {
            "_id": {"purpose": "$purpose", "model": "$model"},
            "totalCostUsd": {"$sum": "$costUsd"},
            "totalInputTokens": {"$sum": "$inputTokens"},
            "totalOutputTokens": {"$sum": "$outputTokens"},
            "callCount": {"$sum": 1},
        }},
        {"$sort": {"totalCostUsd": -1}},
    ]
    results = await db.usage_log.aggregate(pipeline).to_list(200)
    total = sum(r["totalCostUsd"] for r in results)

    # Top users
    user_pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$userId",
            "totalCostUsd": {"$sum": "$costUsd"},
            "callCount": {"$sum": 1},
        }},
        {"$sort": {"totalCostUsd": -1}},
        {"$limit": 20},
    ]
    top_users = await db.usage_log.aggregate(user_pipeline).to_list(20)

    return {
        "days": days,
        "totalCostUsd": round(total, 4),
        "byPurposeModel": [{
            "purpose": r["_id"]["purpose"],
            "model": r["_id"]["model"],
            "costUsd": round(r["totalCostUsd"], 4),
            "calls": r["callCount"],
        } for r in results],
        "topUsers": [{
            "userId": u["_id"],
            "costUsd": round(u["totalCostUsd"], 4),
            "calls": u["callCount"],
        } for u in top_users],
    }
