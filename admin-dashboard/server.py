#!/usr/bin/env python3
"""
Euler Admin Dashboard — standalone monitoring server.

Usage:
    python server.py                         # defaults: port 4000
    python server.py --port 4001

Reads MONGODB_URI from ../backend/.env (via dotenv) or environment variables.
"""

import asyncio
import json
import os
import sys
import time
import threading
from datetime import datetime, timedelta as datetime_timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

# ── Config — load from backend .env ─────────────────────────────────

_BACKEND_ENV = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")

try:
    from dotenv import load_dotenv
    load_dotenv(_BACKEND_ENV, override=False)
except ImportError:
    # Fallback: parse .env manually if python-dotenv not installed
    if os.path.exists(_BACKEND_ENV):
        with open(_BACKEND_ENV) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
                    if _k and _v and _k not in os.environ:
                        os.environ[_k] = _v

MONGO_URI = os.environ.get("MONGODB_URI", "")
if not MONGO_URI:
    sys.exit("MONGODB_URI not set. Ensure ../backend/.env exists or set the env var.")

PORT = int(os.environ.get("DASHBOARD_PORT", "4000"))

# Max gap between two consecutive messages that still counts as "active"
INTERACTION_GAP_CAP_SEC = 300  # 5 minutes

# ── MongoDB helpers ─────────────────────────────────────────────────

_client = None

def get_client():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            MONGO_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=5000,
            socketTimeoutMS=30000,
            maxPoolSize=10,
        )
    return _client

def get_db():
    return get_client()["tutor_v2"]


async def ensure_indexes():
    """Create indexes used by dashboard queries — idempotent / no-op if exist."""
    db = get_db()
    try:
        # Sessions: filtering by user, time windows, transcript timestamps
        await db.sessions.create_index("userEmail")
        await db.sessions.create_index("createdAt")
        await db.sessions.create_index("transcript.timestamp")
        await db.sessions.create_index([("userEmail", 1), ("createdAt", -1)])
        await db.users.create_index("email", unique=True)
        await db.users.create_index("createdAt")
        await db.session_feedback.create_index("createdAt")
        print("  ✓ Indexes ensured")
    except Exception as e:
        print(f"  ⚠ Could not ensure indexes: {e}")


# ── TTL cache ───────────────────────────────────────────────────────

_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()
CACHE_TTL = 60  # seconds — long enough that browse-around sessions stay cached

def cache_get(key: str):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry[0]) < CACHE_TTL:
            return entry[1]
    return None

def cache_set(key: str, val):
    with _cache_lock:
        _cache[key] = (time.time(), val)


# ── Interaction time calculation ────────────────────────────────────

def _parse_ts(raw) -> float | None:
    """Parse an ISO timestamp string to epoch seconds. Returns None on failure."""
    if not raw:
        return None
    try:
        s = str(raw)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt.timestamp()
    except Exception:
        return None


    # Gap larger than this → treat as session paused (tab left open, resumed
    # later). The next message starts a new active period.
ACTIVE_PERIOD_GAP_SEC = 15 * 60  # 15 minutes


def compute_interaction_time(transcript: list) -> dict:
    """Compute true interaction time, ignoring time when student wasn't engaging.

    A session can have messages spanning days if the student left the tab open
    and came back. Raw "last - first" overcounts. So we detect "active periods"
    — runs of messages with gaps <= ACTIVE_PERIOD_GAP_SEC — and sum each
    period's duration (its own last - first). Long gaps are discounted.

    Examples:
      - Messages all within 30 min → activeTime = 30 min, spanTime = 30 min
      - 2 bursts of 20 min each, 5h apart → activeTime = 40 min, spanTime = 5h40m
      - Single message → activeTime = 0 (no duration to measure)

    Returns {
        activeSec: int — sum of active periods (the metric we display),
        spanSec: int — raw first → last (kept for diagnostics),
        firstMsg: str, lastMsg: str — ISO timestamps,
    }
    """
    timestamps = []
    for t in transcript:
        if isinstance(t, dict):
            ts = _parse_ts(t.get("timestamp"))
            if ts:
                timestamps.append(ts)

    if len(timestamps) < 2:
        return {"activeSec": 0, "spanSec": 0, "firstMsg": "", "lastMsg": ""}

    timestamps.sort()
    span = int(timestamps[-1] - timestamps[0])

    # Walk timestamps, splitting on long gaps into active periods.
    active_total = 0
    period_start = timestamps[0]
    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i - 1]
        if gap > ACTIVE_PERIOD_GAP_SEC:
            # Close out the previous period, start a new one
            active_total += timestamps[i - 1] - period_start
            period_start = timestamps[i]
    # Add the final period
    active_total += timestamps[-1] - period_start

    first_dt = datetime.fromtimestamp(timestamps[0], tz=timezone.utc)
    last_dt = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)
    return {
        "activeSec": int(active_total),
        "spanSec": span,
        "firstMsg": first_dt.isoformat()[:19],
        "lastMsg": last_dt.isoformat()[:19],
    }


# ── API handlers ────────────────────────────────────────────────────

async def fetch_stats():
    cached = cache_get("stats")
    if cached:
        return cached
    db = get_db()
    total_users = await db.users.count_documents({})
    total_sessions = await db.sessions.count_documents({})
    active_sessions = await db.sessions.count_documents({"status": "active"})
    external_sessions = await db.sessions.count_documents({"userEmail": {"$ne": "mayank@test.com"}})

    # Cost aggregation via MongoDB $group (pushes math to the DB)
    # createdAt is stored as an ISO string, so we compare lexically with .isoformat()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    async def _sum_cost(match_stage: dict) -> dict:
        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": None,
                "llm": {"$sum": {"$ifNull": ["$backendState.llmCostCents", 0]}},
                "tts": {"$sum": {"$ifNull": ["$backendState.ttsCostCents", 0]}},
                "sessions": {"$sum": 1},
            }},
        ]
        async for row in db.sessions.aggregate(pipeline):
            return {"llm": row["llm"], "tts": row["tts"], "sessions": row["sessions"]}
        return {"llm": 0, "tts": 0, "sessions": 0}

    cost_all = await _sum_cost({})
    cost_month = await _sum_cost({"createdAt": {"$gte": month_start}})
    cost_today = await _sum_cost({"createdAt": {"$gte": today_start}})

    result = {
        "totalUsers": total_users,
        "totalSessions": total_sessions,
        "activeSessions": active_sessions,
        "externalSessions": external_sessions,
        "costAllCents": cost_all["llm"] + cost_all["tts"],
        "costAllLlmCents": cost_all["llm"],
        "costAllTtsCents": cost_all["tts"],
        "costMonthCents": cost_month["llm"] + cost_month["tts"],
        "costTodayCents": cost_today["llm"] + cost_today["tts"],
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    cache_set("stats", result)
    return result


async def fetch_users():
    """Optimized user-aggregation:
      1. Mongo $group — counts/costs/per-session min/max timestamps (server-side, fast)
      2. For "outlier" sessions (span > 4h, suggesting tab-open) pull transcript
         timestamps and refine via active-period split. ~5% of sessions.
      3. For normal sessions, span ≈ active (continuous interaction).
    """
    cached = cache_get("users")
    if cached:
        return cached
    db = get_db()
    OUTLIER_GAP_SEC = 4 * 3600  # 4 hours — sessions with span>this need refinement

    # Single aggregation: counts + costs + min/max timestamp per session, then
    # group by user. We sum span-from-min/max here and tag outlier sessions for
    # later refinement.
    users_fut = db.users.find(
        {}, {"name": 1, "email": 1, "createdAt": 1}
    ).sort("createdAt", -1).to_list(length=500)

    sessions_agg_fut = db.sessions.aggregate([
        # Compute per-session min/max timestamp (uses indexed transcript.timestamp)
        {"$addFields": {
            "_minTs": {"$min": "$transcript.timestamp"},
            "_maxTs": {"$max": "$transcript.timestamp"},
        }},
        {"$addFields": {
            # Convert ISO strings to milliseconds; null-safe
            "_spanSec": {
                "$cond": {
                    "if": {"$and": [{"$ne": ["$_minTs", None]}, {"$ne": ["$_maxTs", None]}]},
                    "then": {
                        "$divide": [
                            {"$subtract": [
                                {"$dateFromString": {"dateString": "$_maxTs", "onError": None}},
                                {"$dateFromString": {"dateString": "$_minTs", "onError": None}},
                            ]},
                            1000,
                        ]
                    },
                    "else": 0,
                }
            },
        }},
        {"$group": {
            "_id": "$userEmail",
            "sessionCount": {"$sum": 1},
            "totalTurns": {"$sum": {"$ifNull": ["$metrics.totalTurns", 0]}},
            "totalStudentResponses": {"$sum": {"$ifNull": ["$metrics.studentResponses", 0]}},
            "lastSession": {"$max": "$createdAt"},
            "totalLlm": {"$sum": {"$ifNull": ["$backendState.llmCostCents", 0]}},
            "totalTts": {"$sum": {"$ifNull": ["$backendState.ttsCostCents", 0]}},
            "totalSpan": {"$sum": {"$ifNull": ["$_spanSec", 0]}},
            # Collect outlier session ids per user for refinement
            "outlierSessionIds": {
                "$push": {
                    "$cond": [
                        {"$gt": ["$_spanSec", OUTLIER_GAP_SEC]},
                        "$_id",
                        None,
                    ]
                }
            },
        }},
    ], allowDiskUse=True).to_list(length=1000)

    users, agg = await asyncio.gather(users_fut, sessions_agg_fut)
    session_map = {a["_id"]: a for a in agg}

    # ── Refinement pass: only for outlier sessions, pull transcript.timestamp
    # and recompute active time per session, then adjust each user's totalSpan
    # down to true totalActive. ~5% of sessions per typical dataset.
    outlier_ids = []
    for entry in agg:
        for sid in entry.get("outlierSessionIds", []):
            if sid is not None:
                outlier_ids.append(sid)

    # Map: session_id -> (active_for_this_session, span_for_this_session)
    refined: dict = {}
    if outlier_ids:
        cur = db.sessions.find(
            {"_id": {"$in": outlier_ids}},
            {"userEmail": 1, "transcript.timestamp": 1},
        )
        async for s in cur:
            sid = s["_id"]
            timing = compute_interaction_time(s.get("transcript", []))
            refined[sid] = (timing["activeSec"], timing["spanSec"])

    # Build per-user totals: start with totalSpan from agg, then subtract span
    # of outlier sessions and add their active counterpart.
    timing_per_user: dict[str, dict] = {}
    for entry in agg:
        email = entry["_id"]
        if not email:
            continue
        active = entry["totalSpan"]  # start with span (= active for non-outliers)
        for sid in entry.get("outlierSessionIds", []):
            if sid is None or sid not in refined:
                continue
            ref_active, ref_span = refined[sid]
            # Replace this session's contribution: active = total - this_span + this_active
            active = active - ref_span + ref_active
        timing_per_user[email] = {"active": int(active), "span": int(entry["totalSpan"])}

    result = []
    for u in users:
        email = u.get("email", "")
        st = session_map.get(email, {})
        timing = timing_per_user.get(email, {"active": 0, "span": 0})
        llm_c = st.get("totalLlm", 0) or 0
        tts_c = st.get("totalTts", 0) or 0
        result.append({
            "name": u.get("name", "?"),
            "email": email,
            "createdAt": str(u.get("createdAt", ""))[:19],
            "sessions": st.get("sessionCount", 0),
            "totalActive": timing["active"],   # active-period sum (excludes idle)
            "totalSpan": timing["span"],       # raw last - first per session, summed
            "totalTurns": st.get("totalTurns", 0),
            "studentResponses": st.get("totalStudentResponses", 0),
            "lastSession": str(st.get("lastSession", ""))[:19],
            "totalCostCents": round(llm_c + tts_c, 2),
            "totalLlmCents": round(llm_c, 2),
            "totalTtsCents": round(tts_c, 2),
        })
    cache_set("users", result)
    return result


async def fetch_sessions(limit: int = 50, offset: int = 0, q: str = ""):
    """Paginated sessions list. Default 50/page; supports search filter on
    userEmail / studentName / title / intent.
    """
    cache_key = f"sessions_{limit}_{offset}_{q.lower()}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    db = get_db()

    # Build search filter — server-side, uses indexes when possible
    match = {}
    if q:
        ql = q.strip()
        if ql:
            import re
            # Case-insensitive substring across the relevant fields
            qre = re.compile(re.escape(ql), re.IGNORECASE)
            match = {"$or": [
                {"userEmail": qre},
                {"studentName": qre},
                {"title": qre},
                {"headline": qre},
                {"intent.raw": qre},
            ]}

    # Get total count (cached separately so we don't recount each page)
    count_key = f"sessions_count_{q.lower()}"
    cached_count = cache_get(count_key)
    if cached_count is None:
        total = await db.sessions.count_documents(match)
        cache_set(count_key, total)
    else:
        total = cached_count

    # Pull transcript timestamps (small) so we can compute true active time
    sessions = await db.sessions.find(
        match,
        {
            "userEmail": 1, "studentName": 1, "title": 1, "headline": 1,
            "createdAt": 1, "durationSec": 1, "metrics": 1, "intent": 1,
            "status": 1, "teachingMode": 1, "courseId": 1,
            "transcript.timestamp": 1,
            "backendState.llmCostCents": 1,
            "backendState.ttsCostCents": 1,
            "backendState.llmCallCount": 1,
            "backendState.llmTotalInputTokens": 1,
            "backendState.llmTotalOutputTokens": 1,
            "backendState.ttsCharCount": 1,
        },
    ).sort("createdAt", -1).skip(offset).limit(limit).to_list(length=limit)

    result = []
    for s in sessions:
        metrics = s.get("metrics") or {}
        intent = s.get("intent") or {}
        raw_intent = intent.get("raw", "") if isinstance(intent, dict) else str(intent)
        dur = s.get("durationSec") or 0
        bs = s.get("backendState") or {}
        llm_c = bs.get("llmCostCents") or 0
        tts_c = bs.get("ttsCostCents") or 0
        timing = compute_interaction_time(s.get("transcript", []))
        result.append({
            "_id": str(s.get("_id", "")),
            "user": s.get("studentName", "?"),
            "email": s.get("userEmail", ""),
            "title": s.get("title") or s.get("headline") or "(no title)",
            "createdAt": str(s.get("createdAt", ""))[:19],
            "durationRaw": dur,
            "activeSec": timing["activeSec"],   # active periods (not tab-open)
            "spanSec": timing["spanSec"],
            "firstMsg": timing["firstMsg"],
            "lastMsg": timing["lastMsg"],
            "turns": metrics.get("totalTurns", 0),
            "studentResponses": metrics.get("studentResponses", 0),
            "status": s.get("status", "?"),
            "intent": raw_intent[:120],
            "mode": s.get("teachingMode", ""),
            "courseId": s.get("courseId", ""),
            "costCents": round(llm_c + tts_c, 2),
            "llmCents": round(llm_c, 2),
            "ttsCents": round(tts_c, 2),
            "llmCalls": bs.get("llmCallCount") or 0,
            "inputTokens": bs.get("llmTotalInputTokens") or 0,
            "outputTokens": bs.get("llmTotalOutputTokens") or 0,
            "ttsChars": bs.get("ttsCharCount") or 0,
        })
    response = {
        "items": result,
        "total": total,
        "offset": offset,
        "limit": limit,
        "hasMore": offset + len(result) < total,
    }
    cache_set(cache_key, response)
    return response


async def fetch_analytics(days: int = 30):
    """Time-series + aggregates for the Analytics tab."""
    cached = cache_get(f"analytics_{days}")
    if cached:
        return cached
    db = get_db()
    now = datetime.now(timezone.utc)

    def _iso(dt: datetime) -> str:
        return dt.isoformat()

    since = _iso(now - datetime_timedelta(days=days))
    week_ago = _iso(now - datetime_timedelta(days=7))
    day_ago = _iso(now - datetime_timedelta(days=1))
    month_ago = _iso(now - datetime_timedelta(days=30))

    # ── Signups per day (last N days) — substring on string createdAt ──
    signup_pipeline = [
        {"$match": {"createdAt": {"$gte": since}}},
        {"$group": {
            "_id": {"$substrCP": ["$createdAt", 0, 10]},  # YYYY-MM-DD from ISO string
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    signup_series = [
        {"date": r["_id"], "count": r["count"]}
        async for r in db.users.aggregate(signup_pipeline)
    ]

    # ── Sessions per day ──
    sess_pipeline = [
        {"$match": {"createdAt": {"$gte": since}}},
        {"$group": {
            "_id": {"$substrCP": ["$createdAt", 0, 10]},
            "count": {"$sum": 1},
            "cost": {"$sum": {"$add": [
                {"$ifNull": ["$backendState.llmCostCents", 0]},
                {"$ifNull": ["$backendState.ttsCostCents", 0]},
            ]}},
            "turns": {"$sum": {"$ifNull": ["$backendState.assistantTurnCount", 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]
    session_series = [
        {"date": r["_id"], "count": r["count"], "costCents": round(r["cost"], 2), "turns": r["turns"]}
        async for r in db.sessions.aggregate(sess_pipeline)
    ]

    # ── DAU/WAU/MAU (unique users ACTIVE in window — not just session-creators) ──
    # A user counts as active if any of their session transcripts contains a
    # message timestamp inside the window. createdAt-only counted misses
    # users who started a session earlier and are still actively using it.
    async def _unique_active_users(gte_iso: str) -> int:
        pipeline = [
            # Find sessions with at least one message inside the window.
            # transcript.timestamp is an array field — Mongo's elemMatch-like
            # implicit semantics on dotted paths picks any element matching.
            {"$match": {"transcript.timestamp": {"$gte": gte_iso}}},
            {"$group": {"_id": "$userEmail"}},
        ]
        users = set()
        async for r in db.sessions.aggregate(pipeline):
            if r["_id"]:
                users.add(r["_id"])
        return len(users)
    dau = await _unique_active_users(day_ago)
    wau = await _unique_active_users(week_ago)
    mau = await _unique_active_users(month_ago)

    # ── Mode split (voice vs text) ──
    mode_pipeline = [
        {"$match": {"createdAt": {"$gte": since}}},
        {"$group": {"_id": "$teachingMode", "count": {"$sum": 1}}},
    ]
    mode_split = {r["_id"] or "unknown": r["count"] async for r in db.sessions.aggregate(mode_pipeline)}

    # ── Status breakdown ──
    status_pipeline = [
        {"$match": {"createdAt": {"$gte": since}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    status_breakdown = {r["_id"] or "unknown": r["count"] async for r in db.sessions.aggregate(status_pipeline)}

    # ── Top topics (from intent.raw / headline / title, whichever populated) ──
    topic_pipeline = [
        {"$match": {"createdAt": {"$gte": since}}},
        # Prefer intent.raw → headline → title
        {"$addFields": {
            "_topic": {"$ifNull": [
                "$intent.raw",
                {"$ifNull": ["$headline", "$title"]},
            ]},
        }},
        {"$match": {"_topic": {"$ne": None, "$ne": ""}}},
        {"$group": {
            "_id": {"$toLower": {"$substrCP": ["$_topic", 0, 60]}},
            "count": {"$sum": 1},
            "sample": {"$first": "$_topic"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    top_topics = [
        {"topic": r["sample"][:80], "count": r["count"]}
        async for r in db.sessions.aggregate(topic_pipeline)
    ]

    # ── Aggregate averages ──
    avg_pipeline = [
        {"$match": {"createdAt": {"$gte": since}}},
        {"$group": {
            "_id": None,
            "sessions": {"$sum": 1},
            "totalTurns": {"$sum": {"$ifNull": ["$backendState.assistantTurnCount", 0]}},
            "totalCost": {"$sum": {"$add": [
                {"$ifNull": ["$backendState.llmCostCents", 0]},
                {"$ifNull": ["$backendState.ttsCostCents", 0]},
            ]}},
        }},
    ]
    avg_row = None
    async for r in db.sessions.aggregate(avg_pipeline):
        avg_row = r
        break

    totals = {
        "sessions": (avg_row or {}).get("sessions", 0),
        "turns": (avg_row or {}).get("totalTurns", 0),
        "costCents": round((avg_row or {}).get("totalCost", 0), 2),
    }
    avg_turns_per_session = totals["turns"] / totals["sessions"] if totals["sessions"] else 0
    avg_cost_per_session = totals["costCents"] / totals["sessions"] if totals["sessions"] else 0
    avg_cost_per_turn = totals["costCents"] / totals["turns"] if totals["turns"] else 0

    # ── Return rate: cohort → returned in next window ──
    async def _return_rate(cohort_start_iso: str, cohort_end_iso: str, return_since_iso: str) -> dict:
        cohort = await db.sessions.distinct("userEmail", {
            "createdAt": {"$gte": cohort_start_iso, "$lt": cohort_end_iso},
        })
        cohort = {u for u in cohort if u}
        if not cohort:
            return {"cohort": 0, "returned": 0, "rate": 0}
        returned = await db.sessions.distinct("userEmail", {
            "userEmail": {"$in": list(cohort)},
            "createdAt": {"$gte": return_since_iso},
        })
        returned = {u for u in returned if u}
        rate = len(returned) / len(cohort) * 100 if cohort else 0
        return {"cohort": len(cohort), "returned": len(returned), "rate": round(rate, 1)}

    td = datetime_timedelta
    ret_1d = await _return_rate(_iso(now - td(days=2)), _iso(now - td(days=1)), _iso(now - td(days=1)))
    ret_7d = await _return_rate(_iso(now - td(days=14)), _iso(now - td(days=7)), _iso(now - td(days=7)))
    ret_30d = await _return_rate(_iso(now - td(days=60)), _iso(now - td(days=30)), _iso(now - td(days=30)))

    result = {
        "windowDays": days,
        "signupSeries": signup_series,
        "sessionSeries": session_series,
        "dau": dau, "wau": wau, "mau": mau,
        "modeSplit": mode_split,
        "statusBreakdown": status_breakdown,
        "topTopics": top_topics,
        "totals": totals,
        "avgTurnsPerSession": round(avg_turns_per_session, 2),
        "avgCostPerSessionCents": round(avg_cost_per_session, 2),
        "avgCostPerTurnCents": round(avg_cost_per_turn, 2),
        "returnRate1d": ret_1d,
        "returnRate7d": ret_7d,
        "returnRate30d": ret_30d,
    }
    cache_set(f"analytics_{days}", result)
    return result


async def fetch_feedback():
    """NPS + qualitative feedback from session_feedback collection."""
    cached = cache_get("feedback")
    if cached:
        return cached
    db = get_db()
    docs = await db.session_feedback.find({}).sort("createdAt", -1).to_list(length=500)

    ratings = []
    comments = []
    for d in docs:
        # Common NPS field names
        rating = d.get("rating") or d.get("nps") or d.get("score")
        if rating is not None:
            try:
                ratings.append(int(rating))
            except (ValueError, TypeError):
                pass
        comment = d.get("comment") or d.get("feedback") or d.get("text") or ""
        if comment:
            comments.append({
                "rating": rating,
                "comment": str(comment)[:500],
                "email": d.get("userEmail", ""),
                "createdAt": str(d.get("createdAt", ""))[:19],
                "sessionId": str(d.get("sessionId", "")),
            })

    # Histogram 1-10
    histogram = {str(i): 0 for i in range(1, 11)}
    for r in ratings:
        if 1 <= r <= 10:
            histogram[str(r)] += 1

    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    # NPS calculation: % promoters (9-10) minus % detractors (0-6)
    if ratings:
        promoters = sum(1 for r in ratings if r >= 9)
        detractors = sum(1 for r in ratings if r <= 6)
        nps = (promoters - detractors) / len(ratings) * 100
    else:
        nps = 0

    result = {
        "totalResponses": len(ratings),
        "avgRating": round(avg_rating, 2),
        "npsScore": round(nps, 1),
        "histogram": histogram,
        "comments": comments[:50],
    }
    cache_set("feedback", result)
    return result


async def fetch_session_detail(session_id: str):
    """Per-session details with perTurnCosts and model breakdown."""
    cached = cache_get(f"detail_{session_id}")
    if cached:
        return cached
    from bson import ObjectId
    db = get_db()
    s = None
    try:
        s = await db.sessions.find_one(
            {"_id": ObjectId(session_id)},
            {"backendState.perTurnCosts": 1,
             "backendState.llmCostCents": 1,
             "backendState.ttsCostCents": 1,
             "backendState.llmCallCount": 1,
             "backendState.llmTotalInputTokens": 1,
             "backendState.llmTotalOutputTokens": 1,
             "backendState.ttsCharCount": 1,
             "title": 1, "userEmail": 1, "studentName": 1},
        )
    except Exception:
        pass
    if not s:
        return {"error": "not found"}
    bs = s.get("backendState") or {}
    result = {
        "title": s.get("title", ""),
        "user": s.get("studentName", ""),
        "email": s.get("userEmail", ""),
        "llmCents": round(bs.get("llmCostCents") or 0, 2),
        "ttsCents": round(bs.get("ttsCostCents") or 0, 2),
        "totalCents": round((bs.get("llmCostCents") or 0) + (bs.get("ttsCostCents") or 0), 2),
        "llmCalls": bs.get("llmCallCount") or 0,
        "inputTokens": bs.get("llmTotalInputTokens") or 0,
        "outputTokens": bs.get("llmTotalOutputTokens") or 0,
        "ttsChars": bs.get("ttsCharCount") or 0,
        "perTurnCosts": bs.get("perTurnCosts") or [],
    }
    cache_set(f"detail_{session_id}", result)
    return result


async def fetch_transcript(session_id: str):
    cached = cache_get(f"transcript_{session_id}")
    if cached:
        return cached
    from bson import ObjectId
    db = get_db()
    s = None
    try:
        s = await db.sessions.find_one({"_id": ObjectId(session_id)}, {"transcript": 1})
    except Exception:
        pass
    if not s:
        s = await db.sessions.find_one({"sessionId": session_id}, {"transcript": 1})
    if not s:
        return {"transcript": []}

    transcript = s.get("transcript", [])
    cleaned = []
    for turn in transcript:
        if isinstance(turn, dict):
            role = turn.get("role", turn.get("speaker", "?"))
            content = turn.get("content", turn.get("text", turn.get("message", "")))
            ts = turn.get("timestamp", "")
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                content = " ".join(parts)
            content = str(content)
            if content.startswith("[SYSTEM]"):
                continue
            cleaned.append({"role": role, "content": content[:2000], "ts": str(ts)[:19] if ts else ""})
    result = {"transcript": cleaned}
    cache_set(f"transcript_{session_id}", result)
    return result


# ── Replay data ─────────────────────────────────────────────────────

import re

def _parse_vb_beats(text: str) -> list[dict]:
    """Parse <vb draw='...' say="..." /> tags from assistant content into steps."""
    beats = []
    for m in re.finditer(r'<vb\s([^>]*?)/?>', text, re.DOTALL):
        attrs_str = m.group(1)
        say = ""
        draw = None
        say_m = re.search(r'say="([^"]*)"', attrs_str) or re.search(r"say='([^']*)'", attrs_str)
        if say_m:
            say = say_m.group(1)
        draw_m = re.search(r"draw='(\{[^']*\})'", attrs_str) or re.search(r'draw="(\{[^"]*\})"', attrs_str)
        if draw_m:
            try:
                draw = json.loads(draw_m.group(1))
            except Exception:
                draw = {"raw": draw_m.group(1)[:200]}
        beats.append({"say": say, "draw": draw})
    return beats


def _parse_scene_title(text: str) -> str:
    m = re.search(r'<teaching-voice-scene\s+title="([^"]*)"', text)
    return m.group(1) if m else ""


async def fetch_replay(session_id: str):
    cached = cache_get(f"replay_{session_id}")
    if cached:
        return cached
    from bson import ObjectId
    db = get_db()
    s = None
    try:
        s = await db.sessions.find_one(
            {"_id": ObjectId(session_id)},
            {"transcript.timestamp": 1, "transcript.role": 1,
             "transcript.content": 1, "backendState.messages": 1,
             "studentName": 1, "title": 1, "headline": 1, "intent": 1,
             "createdAt": 1, "metrics": 1},
        )
    except Exception:
        pass
    if not s:
        s = await db.sessions.find_one(
            {"sessionId": session_id},
            {"transcript": 1, "backendState.messages": 1,
             "studentName": 1, "title": 1, "headline": 1, "intent": 1,
             "createdAt": 1, "metrics": 1},
        )
    if not s:
        return {"error": "Session not found", "steps": [], "meta": {}}

    # Build timestamp map from transcript (user messages have timestamps)
    ts_map: dict[str, str] = {}
    for t in s.get("transcript", []):
        if isinstance(t, dict) and t.get("role") == "user":
            content = str(t.get("content", ""))[:80]
            ts_map[content] = str(t.get("timestamp", ""))[:19]

    # Parse backendState.messages into replay steps
    messages = (s.get("backendState") or {}).get("messages", [])
    steps = []
    last_ts = ""

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        content = msg.get("content", "")

        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            content = " ".join(parts)
        content = str(content)

        if role == "user":
            if content.startswith("[SYSTEM]"):
                continue
            # Find timestamp from transcript
            content_key = content[:80]
            ts = ts_map.get(content_key, "")
            if ts:
                last_ts = ts
            steps.append({
                "type": "student",
                "text": content,
                "ts": ts,
            })

        elif role == "assistant":
            scene_title = _parse_scene_title(content)
            beats = _parse_vb_beats(content)
            if beats:
                for i, beat in enumerate(beats):
                    step = {
                        "type": "tutor-beat",
                        "scene": scene_title if i == 0 else "",
                        "say": beat["say"],
                        "draw": beat["draw"],
                        "ts": "",
                    }
                    steps.append(step)
            else:
                # No beats parsed — show raw content (trimmed of XML tags)
                clean = re.sub(r'<[^>]+>', '', content).strip()
                if clean:
                    steps.append({
                        "type": "tutor-raw",
                        "text": clean[:3000],
                        "ts": "",
                    })

    intent = s.get("intent") or {}
    raw_intent = intent.get("raw", "") if isinstance(intent, dict) else str(intent)
    meta = {
        "student": s.get("studentName", "?"),
        "title": s.get("title") or s.get("headline") or "(no title)",
        "intent": raw_intent,
        "createdAt": str(s.get("createdAt", ""))[:19],
        "totalSteps": len(steps),
        "metrics": s.get("metrics") or {},
    }
    result = {"steps": steps, "meta": meta}
    cache_set(f"replay_{session_id}", result)
    return result


# ── HTTP server ─────────────────────────────────────────────────────

# Dedicated async event loop running in a background thread
_bg_loop = asyncio.new_event_loop()

def _start_bg_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

_bg_thread = threading.Thread(target=_start_bg_loop, args=(_bg_loop,), daemon=True)
_bg_thread.start()


def run_async(coro):
    """Submit a coroutine to the background event loop and wait for the result (thread-safe)."""
    future = asyncio.run_coroutine_threadsafe(coro, _bg_loop)
    return future.result(timeout=60)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            if path == "" or path == "/dashboard":
                self._html(DASHBOARD_HTML)
            elif path.startswith("/replay/"):
                self._html(REPLAY_HTML)
            elif path == "/api/stats":
                self._json(run_async(fetch_stats()))
            elif path == "/api/users":
                self._json(run_async(fetch_users()))
            elif path == "/api/sessions":
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or "")
                limit = max(1, min(200, int((qs.get("limit") or ["50"])[0])))
                offset = max(0, int((qs.get("offset") or ["0"])[0]))
                q = (qs.get("q") or [""])[0]
                self._json(run_async(fetch_sessions(limit=limit, offset=offset, q=q)))
            elif path == "/api/analytics":
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or "")
                days = int((qs.get("days") or ["30"])[0])
                self._json(run_async(fetch_analytics(days)))
            elif path == "/api/feedback":
                self._json(run_async(fetch_feedback()))
            elif path.startswith("/api/session-detail/"):
                sid = path.split("/api/session-detail/", 1)[1]
                self._json(run_async(fetch_session_detail(sid)))
            elif path.startswith("/api/transcript/"):
                sid = path.split("/api/transcript/", 1)[1]
                self._json(run_async(fetch_transcript(sid)))
            elif path.startswith("/api/replay/"):
                sid = path.split("/api/replay/", 1)[1]
                self._json(run_async(fetch_replay(sid)))
            else:
                self.send_error(404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ── Dashboard HTML ──────────────────────────────────────────────────

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Euler Admin Dashboard</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d2e; --surface2: #232738; --border: #2a2e45;
    --text: #e2e4ed; --text2: #8b8fa7; --accent: #818cf8;
    --accent2: #a78bfa; --green: #34d399; --orange: #fbbf24;
    --red: #f87171; --blue: #60a5fa; --cyan: #22d3ee;
    --radius: 10px; --shadow: 0 2px 8px rgba(0,0,0,.3);
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif;
         background: var(--bg); color: var(--text); line-height: 1.5; }
  .container { max-width: 1440px; margin: 0 auto; padding: 20px 24px; }

  .header { display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
  .header h1 { font-size: 20px; font-weight: 700; color: var(--accent);
               display: flex; align-items: center; gap: 10px; }
  .header h1 .clock { color: var(--text2); font-weight: 400; font-size: 13px;
                      font-family: 'SF Mono', Monaco, monospace; }
  .controls { display: flex; align-items: center; gap: 10px; }
  .controls label { font-size: 12px; color: var(--text2); }
  .controls select, .controls button {
    padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px;
    font-size: 12px; background: var(--surface); color: var(--text); cursor: pointer;
  }
  .controls button { background: var(--accent); color: #0f1117; border-color: var(--accent);
                     font-weight: 600; }
  .controls button:hover { opacity: .85; }
  .pulse { width: 8px; height: 8px; background: var(--green); border-radius: 50%;
           animation: pulse 2s infinite; flex-shrink: 0; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .25; } }
  .status-bar { font-size: 11px; color: var(--text2); margin-bottom: 16px;
                font-family: 'SF Mono', Monaco, monospace; }

  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
           gap: 14px; margin-bottom: 24px; }
  .stat-card { background: var(--surface); border-radius: var(--radius); padding: 16px 18px;
               box-shadow: var(--shadow); border: 1px solid var(--border); }
  .stat-card .label { font-size: 11px; text-transform: uppercase; letter-spacing: .6px;
                      color: var(--text2); margin-bottom: 4px; }
  .stat-card .value { font-size: 30px; font-weight: 800; letter-spacing: -.5px; }
  .stat-card .value.c1 { color: var(--accent); }
  .stat-card .value.c2 { color: var(--blue); }
  .stat-card .value.c3 { color: var(--green); }
  .stat-card .value.c4 { color: var(--orange); }

  .tabs { display: flex; gap: 2px; margin-bottom: 14px;
          background: var(--surface); border-radius: 8px; padding: 3px; width: fit-content; }
  .tabs button { padding: 7px 20px; border: none; background: transparent; font-size: 13px;
                 font-weight: 500; color: var(--text2); cursor: pointer; border-radius: 6px;
                 transition: all .15s; }
  .tabs button.active { color: #fff; background: var(--accent); }
  .tabs button:hover:not(.active) { color: var(--text); }

  .search-bar { margin-bottom: 14px; }
  .search-bar input { width: 100%; max-width: 380px; padding: 8px 14px; border: 1px solid var(--border);
                      border-radius: 8px; font-size: 13px; outline: none;
                      background: var(--surface); color: var(--text); }
  .search-bar input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(129,140,248,.15); }
  .search-bar input::placeholder { color: var(--text2); }

  .table-wrap { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow);
                border: 1px solid var(--border); overflow-x: auto; max-height: 70vh; overflow-y: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: var(--surface2); padding: 9px 14px; text-align: left; font-weight: 600;
       font-size: 11px; text-transform: uppercase; letter-spacing: .4px; color: var(--text2);
       border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 2;
       cursor: pointer; user-select: none; white-space: nowrap; }
  th:hover { color: var(--accent); }
  th .arr { font-size: 9px; margin-left: 3px; opacity: .3; }
  th .arr.on { opacity: 1; color: var(--accent); }
  td { padding: 9px 14px; border-bottom: 1px solid var(--border); vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(129,140,248,.04); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px;
           font-weight: 600; white-space: nowrap; }
  .b-active { background: rgba(52,211,153,.15); color: var(--green); }
  .b-ended { background: rgba(248,113,113,.12); color: var(--red); }
  .b-voice { background: rgba(167,139,250,.15); color: var(--accent2); }
  .b-text { background: rgba(96,165,250,.12); color: var(--blue); }
  tr.user-group-header { background: var(--surface2); cursor: pointer; }
  tr.user-group-header:hover { background: var(--border); }
  tr.user-group-header td { padding: 8px 10px; font-weight: 700; font-size: 13px;
    border-bottom: 2px solid var(--border); }
  tr.user-group-header .grp-toggle { display: inline-block; width: 16px; font-size: 11px;
    transition: transform .15s; color: var(--text2); }
  tr.user-group-header .grp-toggle.collapsed { transform: rotate(-90deg); }
  tr.user-group-header .grp-stats { font-weight: 400; font-size: 11px; color: var(--text2); margin-left: 10px; }
  tr.grp-session.grp-hidden { display: none; }
  .mono { font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 11px; }
  .muted { color: var(--text2); }
  .sm { font-size: 12px; }
  .dur { font-weight: 700; color: var(--cyan); }
  .dur-raw { font-size: 11px; color: var(--text2); text-decoration: line-through; }
  .link { cursor: pointer; color: var(--accent); text-decoration: underline;
          text-decoration-style: dotted; text-underline-offset: 2px; }
  .link:hover { color: var(--accent2); }
  .bold { font-weight: 600; }
  .zero { opacity: .35; }

  .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.6);
                   z-index: 1000; align-items: center; justify-content: center;
                   backdrop-filter: blur(4px); }
  .modal-overlay.show { display: flex; }
  .modal { background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
           width: 92%; max-width: 740px; max-height: 82vh; display: flex; flex-direction: column;
           box-shadow: 0 24px 80px rgba(0,0,0,.5); }
  .modal-header { padding: 14px 20px; border-bottom: 1px solid var(--border);
                  display: flex; justify-content: space-between; align-items: center; }
  .modal-header h3 { font-size: 15px; color: var(--text); }
  .modal-close { background: none; border: none; font-size: 22px; cursor: pointer;
                 color: var(--text2); line-height: 1; }
  .modal-close:hover { color: var(--text); }
  .modal-body { padding: 16px 20px; overflow-y: auto; flex: 1; }
  .turn { margin-bottom: 14px; }
  .turn .role { font-size: 10px; font-weight: 700; text-transform: uppercase;
                letter-spacing: .5px; margin-bottom: 3px; display: flex; gap: 8px; align-items: center; }
  .turn .role.user { color: var(--accent); }
  .turn .role.assistant { color: var(--green); }
  .turn .role .ts { font-weight: 400; color: var(--text2); font-size: 10px; }
  .turn .msg { font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-word;
               padding: 10px 14px; border-radius: 8px; }
  .turn .msg.u { background: rgba(129,140,248,.08); border: 1px solid rgba(129,140,248,.12); }
  .turn .msg.a { background: rgba(52,211,153,.06); border: 1px solid rgba(52,211,153,.1); }
  .gap-marker { text-align: center; padding: 6px; font-size: 11px; color: var(--orange);
                font-style: italic; opacity: .7; }

  .hidden { display: none !important; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  /* ── Cost-related styles ── */
  .cost { font-weight: 700; color: var(--orange); font-family: 'SF Mono', Monaco, monospace; }
  .cost-sm { font-size: 11px; font-weight: 500; color: var(--text2); font-family: 'SF Mono', Monaco, monospace; }
  .stat-card .value.c5 { color: var(--red); }
  .stat-card .value.c6 { color: var(--accent2); }
  .stat-card .sub { font-size: 10px; color: var(--text2); margin-top: 3px; letter-spacing: .3px; }

  /* ── Analytics tab ── */
  .analytics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
                    gap: 16px; margin-bottom: 20px; }
  .chart-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
                padding: 18px; box-shadow: var(--shadow); }
  .chart-card h3 { font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 4px;
                   display: flex; justify-content: space-between; align-items: center; }
  .chart-card .hdr-sub { font-size: 10px; color: var(--text2); font-weight: 400;
                         text-transform: uppercase; letter-spacing: .5px; }
  .chart-card .desc { font-size: 11px; color: var(--text2); margin-bottom: 12px; }

  /* Bar chart (time series) */
  .bar-chart { display: flex; align-items: flex-end; gap: 2px; height: 120px;
               padding: 4px 0; border-bottom: 1px solid var(--border); position: relative; }
  .bar-chart .bar { flex: 1; background: var(--accent); border-radius: 2px 2px 0 0;
                    min-height: 2px; position: relative; transition: opacity .15s; opacity: .85; }
  .bar-chart .bar:hover { opacity: 1; background: var(--accent2); }
  .bar-chart .bar[data-mode="sessions"] { background: var(--blue); }
  .bar-chart .bar[data-mode="cost"] { background: var(--orange); }
  .bar-labels { display: flex; justify-content: space-between; font-size: 9px;
                color: var(--text2); margin-top: 4px; font-family: 'SF Mono', monospace; }

  /* Pie/donut replacement: horizontal bars */
  .pct-bar { margin-bottom: 8px; }
  .pct-bar-row { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 3px; }
  .pct-bar-row .lbl { color: var(--text); font-weight: 500; }
  .pct-bar-row .val { color: var(--text2); font-family: 'SF Mono', monospace; }
  .pct-bar-track { height: 6px; background: var(--surface2); border-radius: 3px; overflow: hidden; }
  .pct-bar-fill { height: 100%; background: var(--accent); transition: width .3s ease; }
  .pct-bar-fill.c-voice { background: var(--accent2); }
  .pct-bar-fill.c-text { background: var(--blue); }
  .pct-bar-fill.c-active { background: var(--green); }
  .pct-bar-fill.c-ended { background: var(--red); }
  .pct-bar-fill.c-paused { background: var(--orange); }

  /* Metric grid inside chart card */
  .metric-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .metric-row .m { text-align: center; }
  .metric-row .m .n { font-size: 22px; font-weight: 800; color: var(--accent); line-height: 1; }
  .metric-row .m .n.c2 { color: var(--green); }
  .metric-row .m .n.c3 { color: var(--blue); }
  .metric-row .m .l { font-size: 10px; color: var(--text2); text-transform: uppercase;
                       letter-spacing: .5px; margin-top: 4px; }

  /* NPS histogram */
  .nps-hist { display: flex; align-items: flex-end; gap: 3px; height: 100px;
              border-bottom: 1px solid var(--border); padding-top: 4px; }
  .nps-hist .nb { flex: 1; border-radius: 2px 2px 0 0; position: relative; min-height: 2px;
                  transition: opacity .15s; }
  .nps-hist .nb.detractor { background: var(--red); }
  .nps-hist .nb.passive { background: var(--orange); }
  .nps-hist .nb.promoter { background: var(--green); }
  .nps-hist .nb:hover { opacity: .8; }
  .nps-labels { display: flex; gap: 3px; margin-top: 4px; font-size: 9px;
                color: var(--text2); font-family: 'SF Mono', monospace; }
  .nps-labels div { flex: 1; text-align: center; }

  /* Comment card */
  .fb-comment { background: var(--surface2); border-radius: 8px; padding: 10px 14px;
                margin-bottom: 10px; font-size: 12px; }
  .fb-comment .fb-meta { display: flex; justify-content: space-between; gap: 8px;
                          margin-bottom: 6px; font-size: 10px; color: var(--text2); }
  .fb-comment .fb-rating { display: inline-block; padding: 1px 8px; border-radius: 999px;
                            font-weight: 700; font-size: 11px; }
  .fb-rating.d { background: rgba(248,113,113,.15); color: var(--red); }
  .fb-rating.p { background: rgba(251,191,36,.15); color: var(--orange); }
  .fb-rating.m { background: rgba(52,211,153,.15); color: var(--green); }

  /* Per-turn cost table in session modal */
  .turn-cost-table { width: 100%; font-size: 11px; margin-top: 10px; border-collapse: collapse; }
  .turn-cost-table th { padding: 6px 8px; font-size: 10px; }
  .turn-cost-table td { padding: 5px 8px; font-family: 'SF Mono', monospace; }
  .turn-cost-table .mdl { font-size: 9.5px; color: var(--text2); }

  /* Topic list */
  .topic-list { list-style: none; }
  .topic-list li { padding: 6px 0; border-bottom: 1px solid var(--border);
                    font-size: 12px; display: flex; justify-content: space-between; align-items: center; }
  .topic-list li:last-child { border-bottom: none; }
  .topic-list .tn { color: var(--text); flex: 1; margin-right: 12px; overflow: hidden;
                     text-overflow: ellipsis; white-space: nowrap; }
  .topic-list .tc { color: var(--accent); font-weight: 700; font-family: 'SF Mono', monospace; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>
      <span class="pulse"></span>
      Euler Dashboard
      <span class="clock" id="clock"></span>
    </h1>
    <div class="controls">
      <label>Auto-refresh</label>
      <select id="interval">
        <option value="10">10s</option>
        <option value="30" selected>30s</option>
        <option value="60">60s</option>
        <option value="0">Off</option>
      </select>
      <button onclick="refreshAll()">Refresh Now</button>
    </div>
  </div>
  <div class="status-bar" id="statusBar">connecting...</div>

  <div class="stats" id="statsCards"></div>

  <div class="tabs">
    <button class="active" data-tab="users" onclick="switchTab('users')">Users</button>
    <button data-tab="sessions" onclick="switchTab('sessions')">Sessions</button>
    <button data-tab="analytics" onclick="switchTab('analytics')">Analytics</button>
    <button data-tab="feedback" onclick="switchTab('feedback')">Feedback</button>
  </div>

  <div class="search-bar">
    <input type="text" id="searchInput" placeholder="Filter by name, email, topic..." oninput="filterTable()" />
  </div>

  <div id="tab-users" class="tab-panel active">
    <div class="table-wrap"><table id="usersTable">
      <thead><tr>
        <th>#</th>
        <th onclick="sortTable('users','name')">Name <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('users','email')">Email <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('users','createdAt')">Signed Up <span class="arr on">&#9660;</span></th>
        <th onclick="sortTable('users','sessions')">Sessions <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('users','totalActive')">Active Time <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('users','totalTurns')">Turns <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('users','totalCostCents')">$ Spent <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('users','lastSession')">Last Session <span class="arr">&#9650;</span></th>
      </tr></thead>
      <tbody></tbody>
    </table></div>
  </div>

  <div id="tab-sessions" class="tab-panel">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
      <label style="font-size:12px;color:var(--text2);display:flex;align-items:center;gap:6px;cursor:pointer">
        <input type="checkbox" id="groupByUser" checked onchange="renderSessions()" style="accent-color:var(--accent)">
        Group by user
      </label>
    </div>
    <div class="table-wrap"><table id="sessionsTable">
      <thead><tr>
        <th>#</th>
        <th onclick="sortTable('sessions','user')">User <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('sessions','title')">Topic <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('sessions','createdAt')">Started <span class="arr on">&#9660;</span></th>
        <th onclick="sortTable('sessions','activeSec')">Active Time <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('sessions','turns')">Turns <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('sessions','costCents')">Cost <span class="arr">&#9650;</span></th>
        <th>Mode</th>
        <th onclick="sortTable('sessions','status')">Status <span class="arr">&#9650;</span></th>
      </tr></thead>
      <tbody></tbody>
    </table></div>
    <div id="sessions-footer" style="text-align:center;padding:14px;color:var(--text2)"></div>
  </div>

  <div id="tab-analytics" class="tab-panel">
    <div class="analytics-grid" id="analyticsGrid">
      <div class="chart-card"><p class="muted">Loading analytics...</p></div>
    </div>
  </div>

  <div id="tab-feedback" class="tab-panel">
    <div class="analytics-grid" id="feedbackGrid">
      <div class="chart-card"><p class="muted">Loading feedback...</p></div>
    </div>
  </div>
</div>

<div class="modal-overlay" id="modal">
  <div class="modal">
    <div class="modal-header">
      <h3 id="modalTitle">Transcript</h3>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div class="modal-body" id="modalBody"></div>
  </div>
</div>

<script>
const API = '';
let usersData = [], sessionsData = [];
let sortState = { users: { col: 'createdAt', dir: -1 }, sessions: { col: 'createdAt', dir: -1 } };
let refreshTimer = null;

function fmtDur(s) {
  if (!s) return '\\u2014';
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h > 0) return h + 'h ' + m + 'm';
  if (m > 0) return m + 'm ' + sec + 's';
  return sec + 's';
}
function fmtDate(d) { return d ? d.replace('T', ' ') : '\\u2014'; }
function ago(d) {
  if (!d) return '';
  const diff = (Date.now() - new Date(d + 'Z').getTime()) / 1000;
  if (diff < 0) return 'just now';
  if (diff < 60) return Math.floor(diff) + 's ago';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}
function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function zeroWrap(v) { return v ? String(v) : '<span class="zero">0</span>'; }

function fmtCost(cents, compact) {
  if (cents == null || cents === 0) return compact ? '$0' : '<span class="zero">$0</span>';
  const d = cents / 100;
  if (d >= 100) return '$' + d.toFixed(0);
  if (d >= 1) return '$' + d.toFixed(2);
  if (d >= 0.01) return '$' + d.toFixed(3);
  return '<\\$0.01';
}

function renderStats(d) {
  const llmPct = d.costAllCents > 0 ? Math.round(d.costAllLlmCents / d.costAllCents * 100) : 0;
  const ttsPct = d.costAllCents > 0 ? Math.round(d.costAllTtsCents / d.costAllCents * 100) : 0;
  document.getElementById('statsCards').innerHTML = `
    <div class="stat-card"><div class="label">Total Users</div><div class="value c1">${d.totalUsers}</div></div>
    <div class="stat-card"><div class="label">Total Sessions</div><div class="value c2">${d.totalSessions}</div></div>
    <div class="stat-card"><div class="label">Active Sessions</div><div class="value c3">${d.activeSessions}</div></div>
    <div class="stat-card"><div class="label">Total Spend</div><div class="value c5">${fmtCost(d.costAllCents, true)}</div><div class="sub">${llmPct}% LLM · ${ttsPct}% TTS</div></div>
    <div class="stat-card"><div class="label">This Month</div><div class="value c6">${fmtCost(d.costMonthCents, true)}</div><div class="sub">month to date</div></div>
    <div class="stat-card"><div class="label">Today</div><div class="value c4">${fmtCost(d.costTodayCents, true)}</div><div class="sub">UTC midnight</div></div>
  `;
}

function sortData(data, col, dir) {
  return [...data].sort((a, b) => {
    let va = a[col], vb = b[col];
    if (typeof va === 'number') return (va - vb) * dir;
    va = String(va || '').toLowerCase(); vb = String(vb || '').toLowerCase();
    return va < vb ? -dir : va > vb ? dir : 0;
  });
}

function sortTable(table, col) {
  const st = sortState[table];
  if (st.col === col) st.dir *= -1; else { st.col = col; st.dir = -1; }
  if (table === 'users') renderUsers(); else renderSessions();
}

function getQ() { return (document.getElementById('searchInput').value || '').toLowerCase(); }

function renderUsers() {
  const q = getQ();
  let data = sortData(usersData, sortState.users.col, sortState.users.dir);
  if (q) data = data.filter(u =>
    (u.name||'').toLowerCase().includes(q) || (u.email||'').toLowerCase().includes(q));
  document.querySelector('#usersTable tbody').innerHTML = data.map((u, i) => {
    const costLabel = (u.totalCostCents && u.totalCostCents > 0)
      ? '<span class="cost">' + fmtCost(u.totalCostCents) + '</span>' +
        '<br><span class="cost-sm">' + fmtCost(u.totalLlmCents) + ' LLM · ' + fmtCost(u.totalTtsCents) + ' TTS</span>'
      : '<span class="zero">$0</span>';
    return `<tr>
    <td class="muted">${i + 1}</td>
    <td class="bold">${esc(u.name)}</td>
    <td class="mono">${esc(u.email)}</td>
    <td class="sm">${fmtDate(u.createdAt)}<br><span class="muted">${ago(u.createdAt)}</span></td>
    <td class="bold">${zeroWrap(u.sessions)}</td>
    <td class="dur">${fmtDur(u.totalActive)}</td>
    <td>${zeroWrap(u.totalTurns)}</td>
    <td>${costLabel}</td>
    <td class="sm">${u.lastSession ? fmtDate(u.lastSession) : '\\u2014'}</td>
  </tr>`;}).join('');
}

let _collapsedGroups = {};

function _sessionRow(s, idx) {
  const activeStr = fmtDur(s.activeSec);
  const spanStr = s.spanSec > 0 && s.spanSec !== s.activeSec ? ' <span class="dur-raw">(' + fmtDur(s.spanSec) + ' span)</span>' : '';
  const costLabel = (s.costCents && s.costCents > 0)
    ? '<span class="cost">' + fmtCost(s.costCents) + '</span>' +
      '<br><span class="cost-sm">' + fmtCost(s.llmCents) + '/' + fmtCost(s.ttsCents) + '</span>'
    : '<span class="zero">$0</span>';
  return `<tr>
  <td class="muted">${idx}</td>
  <td><span class="bold">${esc(s.user)}</span><br><span class="mono muted">${esc(s.email)}</span></td>
  <td><span class="link" onclick="viewTranscript('${s._idx}')" title="View transcript + cost breakdown">${esc(s.title)}</span>
      <br><a class="mono muted" href="/replay/${s._id}" target="_blank" style="font-size:10px;color:var(--accent2);text-decoration:none" title="Open replay">&#9654; replay</a></td>
  <td class="sm">${fmtDate(s.createdAt)}<br><span class="muted">${ago(s.createdAt)}</span></td>
  <td><span class="dur">${activeStr}</span>${spanStr}</td>
  <td>${zeroWrap(s.turns)}</td>
  <td>${costLabel}</td>
  <td>${s.mode ? `<span class="badge ${s.mode==='voice'?'b-voice':'b-text'}">${s.mode}</span>` : '\\u2014'}</td>
  <td><span class="badge ${s.status==='active'?'b-active':'b-ended'}">${s.status}</span></td>
</tr>`;
}

function renderSessions() {
  const grouped = document.getElementById('groupByUser') && document.getElementById('groupByUser').checked;
  let data = sortData(sessionsData, sortState.sessions.col, sortState.sessions.dir);
  const tbody = document.querySelector('#sessionsTable tbody');

  if (!grouped) {
    tbody.innerHTML = data.map((s, i) => _sessionRow(s, i + 1)).join('');
  } else {
    // Group by email, preserving sort order (first appearance = group order)
    const groups = [];
    const seen = {};
    for (const s of data) {
      const key = s.email || s.user;
      if (!seen[key]) {
        seen[key] = { email: s.email, user: s.user, items: [] };
        groups.push(seen[key]);
      }
      seen[key].items.push(s);
    }

    let html = '';
    let idx = 0;
    for (const g of groups) {
      const gid = g.email.replace(/[^a-zA-Z0-9]/g, '_');
      const collapsed = !!_collapsedGroups[gid];
      const totalTurns = g.items.reduce((a, s) => a + (s.turns || 0), 0);
      const totalCost = g.items.reduce((a, s) => a + (s.costCents || 0), 0);
      const totalActive = g.items.reduce((a, s) => a + (s.activeSec || 0), 0);
      html += `<tr class="user-group-header" onclick="toggleGroup('${gid}')">
        <td colspan="9">
          <span class="grp-toggle ${collapsed ? 'collapsed' : ''}">&#9660;</span>
          ${esc(g.user)} <span class="mono" style="color:var(--text2)">${esc(g.email)}</span>
          <span class="grp-stats">${g.items.length} session${g.items.length > 1 ? 's' : ''}
            &middot; ${totalTurns} turns &middot; ${fmtDur(totalActive)}
            &middot; ${fmtCost(totalCost)}</span>
        </td></tr>`;
      for (const s of g.items) {
        idx++;
        const row = _sessionRow(s, idx);
        html += row.replace('<tr>', `<tr class="grp-session ${collapsed ? 'grp-hidden' : ''}" data-grp="${gid}">`);
      }
    }
    tbody.innerHTML = html;
  }

  const footer = document.getElementById('sessions-footer');
  if (footer) {
    if (_sessionsPagination.hasMore) {
      footer.innerHTML = '<button onclick="loadSessions(false)" style="padding:8px 18px;border:1px solid var(--border);background:var(--surface2);color:var(--text);border-radius:6px;cursor:pointer;font-size:12px">Load more (' + (_sessionsPagination.total - sessionsData.length) + ' remaining)</button>';
    } else {
      footer.innerHTML = '<span class="muted sm">' + sessionsData.length + ' of ' + _sessionsPagination.total + ' sessions</span>';
    }
  }
}

function toggleGroup(gid) {
  _collapsedGroups[gid] = !_collapsedGroups[gid];
  const rows = document.querySelectorAll('tr[data-grp="' + gid + '"]');
  const header = document.querySelector('tr.user-group-header[onclick*="' + gid + '"] .grp-toggle');
  rows.forEach(r => r.classList.toggle('grp-hidden'));
  if (header) header.classList.toggle('collapsed');
}

// Debounced server-side search (sessions tab only)
let _searchTimer = null;
function filterTable() {
  // Users tab still client-side filter (light data)
  renderUsers();
  // Sessions tab → debounced server-side query
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => {
    _sessionsPagination.query = getQ();
    loadSessions(true);
  }, 250);
}

function switchTab(tab) {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tab));
  // Lazy-load each tab's data on first switch
  if (tab === 'users') loadUsers();
  else if (tab === 'sessions' && !_sessionsLoaded) loadSessions(true);
  else if (tab === 'analytics') loadAnalytics();
  else if (tab === 'feedback') loadFeedback();
}

// ── Analytics ──
let analyticsLoaded = false;
async function loadAnalytics() {
  if (analyticsLoaded) return;
  analyticsLoaded = true;
  try {
    const r = await fetch(API + '/api/analytics?days=30');
    const a = await r.json();
    renderAnalytics(a);
  } catch (e) {
    document.getElementById('analyticsGrid').innerHTML =
      '<div class="chart-card"><p style="color:var(--red)">Failed to load: ' + e.message + '</p></div>';
  }
}

function renderBarChart(series, accessor, mode, emptyMsg) {
  if (!series || !series.length) return '<p class="muted">' + (emptyMsg || 'No data') + '</p>';
  const vals = series.map(accessor);
  const max = Math.max(...vals, 1);
  const bars = series.map((d, i) => {
    const h = Math.max(2, Math.round(vals[i] / max * 100));
    const title = d.date + '\\n' + vals[i] + (mode === 'cost' ? ' cents' : '');
    return '<div class="bar" data-mode="' + mode + '" style="height:' + h + '%" title="' + title + '"></div>';
  }).join('');
  const first = series[0].date.slice(5);
  const last = series[series.length - 1].date.slice(5);
  return '<div class="bar-chart">' + bars + '</div>' +
         '<div class="bar-labels"><span>' + first + '</span><span>' + last + '</span></div>';
}

function renderPctBars(map, order) {
  const total = Object.values(map).reduce((a, b) => a + b, 0) || 1;
  const keys = order ? order.filter(k => map[k]) : Object.keys(map).sort((a,b) => map[b] - map[a]);
  return keys.map(k => {
    const v = map[k] || 0;
    const pct = Math.round(v / total * 100);
    const cls = 'c-' + k.replace(/[^a-z]/gi, '').toLowerCase();
    return '<div class="pct-bar">' +
      '<div class="pct-bar-row"><span class="lbl">' + esc(k) + '</span><span class="val">' + v + ' (' + pct + '%)</span></div>' +
      '<div class="pct-bar-track"><div class="pct-bar-fill ' + cls + '" style="width:' + pct + '%"></div></div>' +
      '</div>';
  }).join('');
}

function renderAnalytics(a) {
  const html = `
    <div class="chart-card">
      <h3>Signups per day <span class="hdr-sub">last ${a.windowDays}d</span></h3>
      <p class="desc">New user registrations.</p>
      ${renderBarChart(a.signupSeries, d => d.count, 'signups', 'No signups in window')}
    </div>

    <div class="chart-card">
      <h3>Sessions per day <span class="hdr-sub">last ${a.windowDays}d</span></h3>
      <p class="desc">${a.totals.sessions} total sessions, ${fmtCost(a.totals.costCents)} spend.</p>
      ${renderBarChart(a.sessionSeries, d => d.count, 'sessions', 'No sessions in window')}
    </div>

    <div class="chart-card">
      <h3>Daily spend <span class="hdr-sub">last ${a.windowDays}d</span></h3>
      <p class="desc">Total cost (LLM + TTS) per day.</p>
      ${renderBarChart(a.sessionSeries, d => d.costCents, 'cost', 'No cost data in window')}
    </div>

    <div class="chart-card">
      <h3>Active users <span class="hdr-sub">rolling</span></h3>
      <p class="desc">Unique users who had a session in the window.</p>
      <div class="metric-row">
        <div class="m"><div class="n">${a.dau}</div><div class="l">DAU</div></div>
        <div class="m"><div class="n c2">${a.wau}</div><div class="l">WAU</div></div>
        <div class="m"><div class="n c3">${a.mau}</div><div class="l">MAU</div></div>
      </div>
    </div>

    <div class="chart-card">
      <h3>Return rate <span class="hdr-sub">cohort → returned</span></h3>
      <p class="desc">% of cohort who came back within the window.</p>
      <div class="metric-row">
        <div class="m"><div class="n">${a.returnRate1d.rate}%</div><div class="l">1-day (${a.returnRate1d.returned}/${a.returnRate1d.cohort})</div></div>
        <div class="m"><div class="n c2">${a.returnRate7d.rate}%</div><div class="l">7-day (${a.returnRate7d.returned}/${a.returnRate7d.cohort})</div></div>
        <div class="m"><div class="n c3">${a.returnRate30d.rate}%</div><div class="l">30-day (${a.returnRate30d.returned}/${a.returnRate30d.cohort})</div></div>
      </div>
    </div>

    <div class="chart-card">
      <h3>Session averages <span class="hdr-sub">last ${a.windowDays}d</span></h3>
      <div class="metric-row">
        <div class="m"><div class="n">${a.avgTurnsPerSession}</div><div class="l">Turns/session</div></div>
        <div class="m"><div class="n c2">${fmtCost(a.avgCostPerSessionCents)}</div><div class="l">Cost/session</div></div>
        <div class="m"><div class="n c3">${fmtCost(a.avgCostPerTurnCents)}</div><div class="l">Cost/turn</div></div>
      </div>
    </div>

    <div class="chart-card">
      <h3>Mode split <span class="hdr-sub">voice vs text</span></h3>
      <p class="desc">Which experience students choose.</p>
      ${renderPctBars(a.modeSplit, ['voice', 'text'])}
    </div>

    <div class="chart-card">
      <h3>Session status <span class="hdr-sub">last ${a.windowDays}d</span></h3>
      <p class="desc">Lifecycle of sessions in window.</p>
      ${renderPctBars(a.statusBreakdown, ['active', 'ended', 'paused', 'completed'])}
    </div>

    <div class="chart-card" style="grid-column: span 2">
      <h3>Top topics <span class="hdr-sub">last ${a.windowDays}d</span></h3>
      <p class="desc">What students are asking about most.</p>
      <ul class="topic-list">
        ${(a.topTopics || []).map(t => '<li><span class="tn">' + esc(t.topic) + '</span><span class="tc">' + t.count + '</span></li>').join('')
          || '<li class="muted">No topics in window</li>'}
      </ul>
    </div>
  `;
  document.getElementById('analyticsGrid').innerHTML = html;
}

// ── Feedback ──
let feedbackLoaded = false;
async function loadFeedback() {
  if (feedbackLoaded) return;
  feedbackLoaded = true;
  try {
    const r = await fetch(API + '/api/feedback');
    const f = await r.json();
    renderFeedback(f);
  } catch (e) {
    document.getElementById('feedbackGrid').innerHTML =
      '<div class="chart-card"><p style="color:var(--red)">Failed to load: ' + e.message + '</p></div>';
  }
}

function renderFeedback(f) {
  const max = Math.max(...Object.values(f.histogram || {}), 1);
  const bars = [];
  for (let i = 1; i <= 10; i++) {
    const v = f.histogram[String(i)] || 0;
    const h = Math.max(2, Math.round(v / max * 100));
    const cls = i <= 6 ? 'detractor' : (i <= 8 ? 'passive' : 'promoter');
    bars.push('<div class="nb ' + cls + '" style="height:' + h + '%" title="' + i + ': ' + v + ' responses"></div>');
  }
  let labels = '';
  for (let i = 1; i <= 10; i++) labels += '<div>' + i + '</div>';

  const comments = (f.comments || []).map(c => {
    const r = c.rating;
    const rCls = r == null ? '' : (r <= 6 ? 'd' : (r <= 8 ? 'p' : 'm'));
    const rLbl = r == null ? '' : '<span class="fb-rating ' + rCls + '">' + r + '</span>';
    return '<div class="fb-comment">' +
      '<div class="fb-meta"><span>' + esc(c.email || 'anonymous') + ' · ' + (c.createdAt ? fmtDate(c.createdAt) : '') + '</span>' + rLbl + '</div>' +
      '<div>' + esc(c.comment) + '</div></div>';
  }).join('') || '<p class="muted">No qualitative feedback yet.</p>';

  document.getElementById('feedbackGrid').innerHTML = `
    <div class="chart-card">
      <h3>NPS <span class="hdr-sub">${f.totalResponses} responses</span></h3>
      <p class="desc">Promoters (9-10) minus Detractors (0-6).</p>
      <div class="metric-row">
        <div class="m"><div class="n">${f.npsScore}</div><div class="l">NPS</div></div>
        <div class="m"><div class="n c2">${f.avgRating}</div><div class="l">Avg rating</div></div>
        <div class="m"><div class="n c3">${f.totalResponses}</div><div class="l">Total</div></div>
      </div>
    </div>

    <div class="chart-card">
      <h3>Rating distribution <span class="hdr-sub">1 → 10</span></h3>
      <p class="desc">Red = detractors, orange = passives, green = promoters.</p>
      <div class="nps-hist">${bars.join('')}</div>
      <div class="nps-labels">${labels}</div>
    </div>

    <div class="chart-card" style="grid-column: span 2">
      <h3>Latest comments <span class="hdr-sub">up to 50</span></h3>
      <div style="max-height: 500px; overflow-y: auto">${comments}</div>
    </div>
  `;
}

function renderPerTurnCosts(detail) {
  const rows = (detail.perTurnCosts || []);
  if (!rows.length) return '';
  let html = '<div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--border)">' +
    '<h4 style="font-size:12px;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Per-turn cost</h4>' +
    '<table class="turn-cost-table">' +
    '<thead><tr><th>Turn</th><th>Calls</th><th>Input</th><th>Output</th><th>LLM</th><th>TTS</th><th>Total</th></tr></thead><tbody>';
  for (const t of rows) {
    const total = (t.llmCents || 0) + (t.ttsCents || 0);
    const models = t.models || {};
    const modelBits = Object.entries(models)
      .map(([m, v]) => m.replace('anthropic/', '').replace('openai/', '') + ': ' + fmtCost(v.cents) + '×' + v.calls)
      .join(' · ');
    html += '<tr>' +
      '<td><strong>#' + t.turn + '</strong>' + (modelBits ? '<br><span class="mdl">' + esc(modelBits) + '</span>' : '') + '</td>' +
      '<td>' + (t.calls || 0) + '</td>' +
      '<td>' + (t.inputTokens || 0).toLocaleString() + '</td>' +
      '<td>' + (t.outputTokens || 0).toLocaleString() + '</td>' +
      '<td>' + fmtCost(t.llmCents) + '</td>' +
      '<td>' + fmtCost(t.ttsCents) + '</td>' +
      '<td class="cost">' + fmtCost(total) + '</td>' +
      '</tr>';
  }
  const grand = (detail.llmCents || 0) + (detail.ttsCents || 0);
  html += '<tr style="background:var(--surface2)"><td><strong>Total</strong></td>' +
    '<td>' + (detail.llmCalls || 0) + '</td>' +
    '<td>' + (detail.inputTokens || 0).toLocaleString() + '</td>' +
    '<td>' + (detail.outputTokens || 0).toLocaleString() + '</td>' +
    '<td>' + fmtCost(detail.llmCents) + '</td>' +
    '<td>' + fmtCost(detail.ttsCents) + '</td>' +
    '<td class="cost">' + fmtCost(grand) + '</td></tr>';
  html += '</tbody></table></div>';
  return html;
}

async function viewTranscript(idx) {
  const s = sessionsData[idx];
  if (!s || !s._id) return;
  const title = (s.user || '?') + ' \\u2014 ' + (s.title || 'Session');
  const costStr = (s.costCents && s.costCents > 0)
    ? ' | ' + fmtCost(s.costCents) + ' (' + fmtCost(s.llmCents) + ' LLM, ' + fmtCost(s.ttsCents) + ' TTS)'
    : '';
  const subtitle = 'Active: ' + fmtDur(s.activeSec) + ' | Span: ' + fmtDur(s.spanSec) + ' | ' + s.turns + ' turns' + costStr;
  document.getElementById('modalTitle').innerHTML = esc(title) + '<br><span class="muted sm">' + subtitle + '</span>';
  document.getElementById('modalBody').innerHTML = '<p class="muted">Loading transcript...</p>';
  document.getElementById('modal').classList.add('show');
  try {
    // Load transcript + detail in parallel
    const [transResp, detailResp] = await Promise.all([
      fetch(API + '/api/transcript/' + s._id),
      fetch(API + '/api/session-detail/' + s._id),
    ]);
    const data = await transResp.json();
    const detail = await detailResp.json();
    const turns = data.transcript || [];
    if (!turns.length) {
      document.getElementById('modalBody').innerHTML = '<p class="muted">No transcript data.</p>';
      return;
    }
    let html = '';
    for (let i = 0; i < turns.length; i++) {
      const t = turns[i];
      // Show gap markers for pauses > 5 min
      if (i > 0 && t.ts && turns[i-1].ts) {
        const prev = new Date(turns[i-1].ts + 'Z').getTime();
        const curr = new Date(t.ts + 'Z').getTime();
        const gapMin = Math.round((curr - prev) / 60000);
        if (gapMin >= 5) {
          html += '<div class="gap-marker">\\u23f1 ' + gapMin + ' min gap</div>';
        }
      }
      const tsLabel = t.ts ? t.ts.replace('T', ' ') : '';
      html += '<div class="turn">' +
        '<div class="role ' + t.role + '">' + esc(t.role) + (tsLabel ? ' <span class="ts">' + tsLabel + '</span>' : '') + '</div>' +
        '<div class="msg ' + (t.role === 'user' ? 'u' : 'a') + '">' + esc(t.content) + '</div></div>';
    }
    // Append per-turn cost breakdown below the transcript
    html += renderPerTurnCosts(detail || {});
    document.getElementById('modalBody').innerHTML = html;
  } catch (e) {
    document.getElementById('modalBody').innerHTML = '<p style="color:var(--red)">Failed to load transcript.</p>';
  }
}
function closeModal() { document.getElementById('modal').classList.remove('show'); }
document.getElementById('modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ── Pagination state ──
let _sessionsPagination = { offset: 0, limit: 50, total: 0, hasMore: false, query: '' };
let _usersLoaded = false;
let _sessionsLoaded = false;

// On first load: fetch only stats + the active tab's data (lazy)
async function refreshAll() {
  const t0 = performance.now();
  document.getElementById('statusBar').textContent = 'refreshing...';
  try {
    // Stats card always loads (cheap)
    const sr = await fetch(API + '/api/stats');
    renderStats(await sr.json());

    // Load whichever tab is currently active; defer the rest
    const activeTab = document.querySelector('.tabs button.active')?.dataset.tab || 'users';
    if (activeTab === 'users') await loadUsers();
    else if (activeTab === 'sessions') await loadSessions(true);

    const ms = Math.round(performance.now() - t0);
    document.getElementById('statusBar').textContent =
      'updated ' + new Date().toLocaleTimeString() + ' (' + ms + 'ms)';
  } catch (e) {
    document.getElementById('statusBar').textContent = 'error: ' + e.message;
  }
}

async function loadUsers() {
  if (_usersLoaded) return;
  const t0 = performance.now();
  try {
    const r = await fetch(API + '/api/users');
    usersData = await r.json();
    renderUsers();
    _usersLoaded = true;
    const ms = Math.round(performance.now() - t0);
    document.getElementById('statusBar').textContent =
      'users: ' + usersData.length + ' loaded in ' + ms + 'ms';
  } catch (e) {
    document.getElementById('statusBar').textContent = 'users error: ' + e.message;
  }
}

async function loadSessions(reset) {
  if (reset) {
    _sessionsPagination.offset = 0;
    sessionsData = [];
  }
  const t0 = performance.now();
  const p = _sessionsPagination;
  const url = API + '/api/sessions?limit=' + p.limit + '&offset=' + p.offset +
    (p.query ? '&q=' + encodeURIComponent(p.query) : '');
  try {
    const r = await fetch(url);
    const data = await r.json();
    const items = (data.items || []).map((s, i) => ({ ...s, _idx: sessionsData.length + i }));
    sessionsData = sessionsData.concat(items);
    _sessionsPagination.total = data.total || sessionsData.length;
    _sessionsPagination.hasMore = !!data.hasMore;
    _sessionsPagination.offset += items.length;
    renderSessions();
    _sessionsLoaded = true;
    const ms = Math.round(performance.now() - t0);
    document.getElementById('statusBar').textContent =
      'sessions: ' + sessionsData.length + ' / ' + _sessionsPagination.total + ' loaded (' + ms + 'ms)';
  } catch (e) {
    document.getElementById('statusBar').textContent = 'sessions error: ' + e.message;
  }
}

function startAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer);
  const sec = parseInt(document.getElementById('interval').value);
  if (sec > 0) refreshTimer = setInterval(refreshAll, sec * 1000);
}
document.getElementById('interval').addEventListener('change', startAutoRefresh);

function tick() { document.getElementById('clock').textContent = new Date().toLocaleTimeString(); }
setInterval(tick, 1000); tick();

refreshAll();
startAutoRefresh();
</script>
</body>
</html>
"""


# ── Replay HTML ─────────────────────────────────────────────────────

REPLAY_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Session Replay — Euler</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d2e; --surface2: #232738; --border: #2a2e45;
    --text: #e2e4ed; --text2: #8b8fa7; --accent: #818cf8;
    --accent2: #a78bfa; --green: #34d399; --orange: #fbbf24;
    --red: #f87171; --blue: #60a5fa; --cyan: #22d3ee;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif;
         background: var(--bg); color: var(--text); }

  .top-bar { background: var(--surface); border-bottom: 1px solid var(--border);
             padding: 12px 24px; display: flex; align-items: center; gap: 16px;
             position: sticky; top: 0; z-index: 10; }
  .top-bar a { color: var(--accent); text-decoration: none; font-size: 13px; }
  .top-bar a:hover { text-decoration: underline; }
  .top-bar .title { font-weight: 700; font-size: 15px; flex: 1; }
  .top-bar .meta { font-size: 12px; color: var(--text2); }

  .main { display: flex; height: calc(100vh - 49px); }

  /* Board panel */
  .board-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .board { flex: 1; padding: 24px 32px; overflow-y: auto; background: #0a0d14; }
  .board-item { margin-bottom: 8px; animation: fadeIn .3s ease; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  .board-item.scene-title { font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
                            color: var(--orange); margin-top: 20px; margin-bottom: 8px; font-weight: 700; }
  .board-item.draw-text { font-size: 15px; line-height: 1.6; }
  .board-item.draw-text.h1 { font-size: 24px; font-weight: 800; color: var(--orange); text-align: center; margin: 16px 0; }
  .board-item.draw-text.h2 { font-size: 18px; font-weight: 700; color: var(--cyan); margin-top: 12px; }
  .board-item.draw-text.h3 { font-size: 16px; font-weight: 600; color: var(--accent); }
  .board-item.draw-equation { font-family: 'SF Mono', Monaco, monospace; font-size: 16px;
                              color: var(--green); padding: 8px 14px; background: rgba(52,211,153,.06);
                              border-left: 3px solid var(--green); border-radius: 4px; margin: 8px 0; }
  .board-item.draw-step { padding: 6px 14px; border-left: 3px solid var(--accent);
                          background: rgba(129,140,248,.05); border-radius: 4px; margin: 4px 0; }
  .board-item.draw-callout { padding: 10px 14px; background: rgba(251,191,36,.08);
                             border: 1px solid rgba(251,191,36,.2); border-radius: 8px; margin: 8px 0; }
  .board-item.draw-check { color: var(--green); }
  .board-item.draw-check::before { content: "\\2713  "; font-weight: 700; }
  .board-item.draw-cross { color: var(--red); }
  .board-item.draw-cross::before { content: "\\2717  "; font-weight: 700; }
  .board-item.draw-list li { margin: 3px 0 3px 18px; }
  .board-item.draw-figure { border-radius: 10px; margin: 12px 0; overflow: hidden;
                            border: 1px solid rgba(96,165,250,.2); }
  .board-item.draw-figure .fig-title { padding: 8px 14px; font-size: 12px; font-weight: 600;
                                       color: var(--cyan); background: rgba(96,165,250,.06); }
  .board-item.draw-figure canvas { display: block; width: 100%; background: #060e11; }
  .board-item.draw-figure .fig-legend { padding: 6px 14px; font-size: 11px; color: var(--text2);
                                        background: rgba(0,0,0,.2); display: flex; gap: 14px; flex-wrap: wrap; }
  .board-item.draw-figure .fig-legend .lg { display: flex; align-items: center; gap: 4px; }
  .board-item.draw-figure .fig-legend .dot { width: 8px; height: 8px; border-radius: 50%; }
  .board-item.draw-divider { border-top: 1px solid var(--border); margin: 14px 0; }
  .board-item.draw-note { font-size: 13px; color: var(--text2); font-style: italic; padding: 4px 0; }

  /* Chat panel */
  .chat-panel { width: 380px; border-left: 1px solid var(--border); display: flex;
                flex-direction: column; background: var(--surface); }
  .chat-header { padding: 12px 16px; border-bottom: 1px solid var(--border);
                 font-size: 12px; color: var(--text2); font-weight: 600;
                 text-transform: uppercase; letter-spacing: .5px; }
  .chat-messages { flex: 1; overflow-y: auto; padding: 16px; }
  .chat-msg { margin-bottom: 14px; animation: fadeIn .3s ease; }
  .chat-msg .bubble { padding: 10px 14px; border-radius: 12px; font-size: 13px;
                      line-height: 1.5; max-width: 90%; word-break: break-word; }
  .chat-msg.student .bubble { background: rgba(129,140,248,.12); border: 1px solid rgba(129,140,248,.15);
                              margin-left: 0; border-bottom-left-radius: 4px; }
  .chat-msg.tutor .bubble { background: rgba(52,211,153,.08); border: 1px solid rgba(52,211,153,.12);
                            margin-left: auto; border-bottom-right-radius: 4px; }
  .chat-msg .who { font-size: 10px; font-weight: 700; text-transform: uppercase;
                   letter-spacing: .5px; margin-bottom: 3px;
                   display: flex; align-items: center; gap: 6px; }
  .chat-msg.student .who { color: var(--accent); }
  .chat-msg.tutor .who { color: var(--green); text-align: right; justify-content: flex-end; }
  .chat-msg .who .ts { font-weight: 400; color: var(--text2); font-size: 10px; }

  /* Controls */
  .controls-bar { padding: 14px 24px; background: var(--surface2); border-top: 1px solid var(--border);
                  display: flex; align-items: center; gap: 12px; justify-content: center; }
  .controls-bar button { padding: 8px 18px; border: 1px solid var(--border); border-radius: 8px;
                         font-size: 13px; font-weight: 600; cursor: pointer;
                         background: var(--surface); color: var(--text); transition: all .1s; }
  .controls-bar button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .controls-bar button:disabled { opacity: .3; cursor: default; }
  .controls-bar button.primary { background: var(--accent); color: #0f1117; border-color: var(--accent); }
  .controls-bar button.primary:hover:not(:disabled) { opacity: .85; color: #0f1117; }
  .controls-bar .progress { font-size: 12px; color: var(--text2); font-family: monospace; min-width: 80px; text-align: center; }
  .controls-bar .speed { padding: 5px 8px; border: 1px solid var(--border); border-radius: 6px;
                         background: var(--surface); color: var(--text); font-size: 12px; }
  .controls-bar label { font-size: 11px; color: var(--text2); }

  .loading { display: flex; align-items: center; justify-content: center; height: 100%;
             font-size: 14px; color: var(--text2); }
</style>
</head>
<body>
<div class="top-bar">
  <a href="/">&larr; Dashboard</a>
  <div class="title" id="replayTitle">Loading...</div>
  <div class="meta" id="replayMeta"></div>
</div>
<div class="main">
  <div class="board-panel">
    <div class="board" id="board"><div class="loading">Loading session...</div></div>
    <div class="controls-bar">
      <button onclick="goStart()" title="Start">&laquo;</button>
      <button onclick="goPrev()" id="btnPrev" title="Previous">&larr; Prev</button>
      <button onclick="goNext()" id="btnNext" class="primary" title="Next (Space)">Next &rarr;</button>
      <button onclick="goEnd()" title="End">&raquo;</button>
      <div class="progress" id="progress">0 / 0</div>
      <span style="width:1px;height:20px;background:var(--border)"></span>
      <button onclick="toggleAuto()" id="btnAuto" title="Auto-play">&#9654; Play</button>
      <label>Speed</label>
      <select class="speed" id="speedSelect">
        <option value="500">Fast</option>
        <option value="1500" selected>Normal</option>
        <option value="3000">Slow</option>
        <option value="5000">Very Slow</option>
      </select>
    </div>
  </div>
  <div class="chat-panel">
    <div class="chat-header">Conversation</div>
    <div class="chat-messages" id="chat"></div>
  </div>
</div>

<script>
let steps = [], meta = {}, cursor = -1, autoTimer = null;

function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function renderDrawItem(draw) {
  if (!draw) return '';
  const cmd = draw.cmd || 'text';
  const text = draw.text || draw.label || '';
  const size = draw.size || 'text';
  const color = draw.color || '';
  const style = color ? `color:${color}` : '';

  switch (cmd) {
    case 'text':
    case 'label':
      return `<div class="board-item draw-text ${size}" style="${style}">${esc(text)}</div>`;
    case 'equation':
    case 'latex':
      return `<div class="board-item draw-equation" style="${style}">${esc(text || draw.equation || draw.latex || '')}</div>`;
    case 'step':
      return `<div class="board-item draw-step" style="${style}">${esc(text)}</div>`;
    case 'callout':
      return `<div class="board-item draw-callout" style="${style}">${esc(text)}</div>`;
    case 'check':
      return `<div class="board-item draw-check" style="${style}">${esc(text)}</div>`;
    case 'cross':
      return `<div class="board-item draw-cross" style="${style}">${esc(text)}</div>`;
    case 'note':
      return `<div class="board-item draw-note">${esc(text)}</div>`;
    case 'divider':
    case 'clear':
      return '<div class="board-item draw-divider"></div>';
    case 'list': {
      const items = draw.items || [];
      return `<div class="board-item draw-list"><ul>${items.map(i => `<li>${esc(typeof i === 'string' ? i : i.text || '')}</li>`).join('')}</ul></div>`;
    }
    case 'figure':
    case 'animation': {
      const fid = 'fig-' + (draw.id || Math.random().toString(36).slice(2, 8));
      const title = draw.title || draw.id || 'Visual';
      let legendHtml = '';
      if (draw.legend) {
        try {
          const items = typeof draw.legend === 'string' ? JSON.parse(draw.legend.replace(/'/g, '"')) : draw.legend;
          if (Array.isArray(items)) {
            legendHtml = '<div class="fig-legend">' + items.map(l =>
              `<span class="lg"><span class="dot" style="background:${l.color || '#888'}"></span>${esc(l.text || '')}</span>`
            ).join('') + '</div>';
          }
        } catch(e) {}
      }
      const codeB64 = draw.code ? btoa(unescape(encodeURIComponent(draw.code))) : '';
      return `<div class="board-item draw-figure">
        <div class="fig-title">${esc(title)}</div>
        <canvas id="${fid}" width="700" height="420" data-code="${codeB64}"></canvas>
        ${legendHtml}
      </div>`;
    }
    default:
      return text ? `<div class="board-item draw-text" style="${style}">${esc(text)}</div>` : '';
  }
}

const _figAnimations = [];

function bootFigure(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !canvas.dataset.code) return;
  try {
    const code = decodeURIComponent(escape(atob(canvas.dataset.code)));
    const W = canvas.width, H = canvas.height;
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#060e11');
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir1 = new THREE.DirectionalLight(0xffffff, 0.8);
    dir1.position.set(5, 10, 7);
    scene.add(dir1);
    const dir2 = new THREE.DirectionalLight(0x8888ff, 0.3);
    dir2.position.set(-5, -3, -5);
    scene.add(dir2);

    const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 1000);
    camera.position.set(0, 0, 18);
    camera.lookAt(0, 0, 0);

    const fn = new Function('THREE', 'scene', 'camera', 'renderer', code);
    fn(THREE, scene, camera, renderer);

    renderer.render(scene, camera);

    // Auto-rotate
    let angle = 0;
    function animate() {
      const id = requestAnimationFrame(animate);
      angle += 0.003;
      scene.rotation.y = angle;
      renderer.render(scene, camera);
    }
    const animId = requestAnimationFrame(animate);
    _figAnimations.push({ canvasId, animId, renderer });
  } catch (e) {
    console.warn('Figure render failed:', canvasId, e);
    canvas.style.display = 'none';
    const fallback = document.createElement('div');
    fallback.style.cssText = 'padding:14px;color:#60a5fa;font-style:italic;font-size:13px;background:rgba(96,165,250,.06)';
    fallback.textContent = '[3D Visual — render error: ' + e.message + ']';
    canvas.parentNode.insertBefore(fallback, canvas.nextSibling);
  }
}

function cleanupFigures() {
  _figAnimations.forEach(f => {
    cancelAnimationFrame(f.animId);
    f.renderer.dispose();
  });
  _figAnimations.length = 0;
}

function showStep(idx) {
  if (idx < 0 || idx >= steps.length) return;
  const step = steps[idx];
  const board = document.getElementById('board');
  const chat = document.getElementById('chat');

  if (step.type === 'student') {
    const div = document.createElement('div');
    div.className = 'chat-msg student';
    div.innerHTML = `<div class="who">Student${step.ts ? ' <span class="ts">' + step.ts.replace('T',' ') + '</span>' : ''}</div>
      <div class="bubble">${esc(step.text)}</div>`;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  } else if (step.type === 'tutor-beat') {
    if (step.scene) {
      const scDiv = document.createElement('div');
      scDiv.className = 'board-item scene-title';
      scDiv.textContent = step.scene;
      board.appendChild(scDiv);
    }
    if (step.draw) {
      const html = renderDrawItem(step.draw);
      if (html) board.insertAdjacentHTML('beforeend', html);
      // Boot Three.js figures after DOM insert
      if (step.draw.cmd === 'figure' || step.draw.cmd === 'animation') {
        const fid = 'fig-' + (step.draw.id || '');
        setTimeout(() => {
          const canvases = board.querySelectorAll('canvas[data-code]');
          canvases.forEach(c => { if (!c._booted) { c._booted = true; bootFigure(c.id); } });
        }, 50);
      }
    }
    if (step.say) {
      const div = document.createElement('div');
      div.className = 'chat-msg tutor';
      div.innerHTML = `<div class="who">Tutor</div><div class="bubble">${esc(step.say)}</div>`;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }
    board.scrollTop = board.scrollHeight;
  } else if (step.type === 'tutor-raw') {
    const div = document.createElement('div');
    div.className = 'chat-msg tutor';
    div.innerHTML = `<div class="who">Tutor</div><div class="bubble">${esc(step.text)}</div>`;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }
}

function rebuildUpTo(idx) {
  cleanupFigures();
  document.getElementById('board').innerHTML = '';
  document.getElementById('chat').innerHTML = '';
  for (let i = 0; i <= idx; i++) showStep(i);
  updateButtons();
}

function goNext() {
  if (cursor >= steps.length - 1) return;
  cursor++;
  showStep(cursor);
  updateButtons();
}

function goPrev() {
  if (cursor <= 0) { cursor = -1; document.getElementById('board').innerHTML = ''; document.getElementById('chat').innerHTML = ''; updateButtons(); return; }
  cursor--;
  rebuildUpTo(cursor);
}

function goStart() { cursor = -1; cleanupFigures(); document.getElementById('board').innerHTML = ''; document.getElementById('chat').innerHTML = ''; updateButtons(); }
function goEnd() { cursor = steps.length - 1; rebuildUpTo(cursor); }

function updateButtons() {
  document.getElementById('btnPrev').disabled = cursor < 0;
  document.getElementById('btnNext').disabled = cursor >= steps.length - 1;
  document.getElementById('progress').textContent = (cursor + 1) + ' / ' + steps.length;
}

function toggleAuto() {
  if (autoTimer) { stopAuto(); return; }
  document.getElementById('btnAuto').innerHTML = '&#9724; Stop';
  const ms = parseInt(document.getElementById('speedSelect').value);
  autoTimer = setInterval(() => {
    if (cursor >= steps.length - 1) { stopAuto(); return; }
    goNext();
  }, ms);
}
function stopAuto() {
  if (autoTimer) clearInterval(autoTimer);
  autoTimer = null;
  document.getElementById('btnAuto').innerHTML = '&#9654; Play';
}

document.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); goNext(); }
  if (e.key === 'ArrowLeft') { e.preventDefault(); goPrev(); }
  if (e.key === 'Home') goStart();
  if (e.key === 'End') goEnd();
});

async function loadReplay() {
  const sid = location.pathname.split('/replay/')[1];
  if (!sid) { document.getElementById('board').innerHTML = '<div class="loading">No session ID</div>'; return; }
  try {
    const resp = await fetch('/api/replay/' + sid);
    const data = await resp.json();
    if (data.error) { document.getElementById('board').innerHTML = '<div class="loading">' + esc(data.error) + '</div>'; return; }
    steps = data.steps || [];
    meta = data.meta || {};
    document.getElementById('replayTitle').textContent = (meta.student || '?') + ' — ' + (meta.title || 'Session');
    document.getElementById('replayMeta').textContent =
      (meta.createdAt || '').replace('T', ' ') + ' | ' + steps.length + ' steps | ' +
      (meta.metrics?.totalTurns || 0) + ' turns';
    document.getElementById('board').innerHTML = '';
    cursor = -1;
    updateButtons();
  } catch (e) {
    document.getElementById('board').innerHTML = '<div class="loading">Failed to load: ' + esc(e.message) + '</div>';
  }
}

loadReplay();
</script>
</body>
</html>
"""


# ── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Euler Admin Dashboard")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    print(f"\n  Euler Admin Dashboard")
    print(f"  http://localhost:{args.port}")

    # One-time index creation (no-op if they exist)
    try:
        run_async(ensure_indexes())
    except Exception as _e:
        print(f"  ⚠ index creation error (continuing): {_e}")
    print()

    server = ThreadedHTTPServer(("0.0.0.0", args.port), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
        if _client:
            _client.close()
