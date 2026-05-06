#!/usr/bin/env python3
"""
Euler Admin Dashboard — standalone monitoring server.

Usage:
    python server.py                         # defaults: port 4000
    python server.py --port 4001

Reads MONGODB_URI and MONGODB_DB from ../backend/.env, then optional ./.env here.
Use Capacity Atlas + myprofessor for production Seek users; DASHBOARD_MONGODB_URI
can override the URI for this process only.
"""

import asyncio
import hashlib
import json
import os
import re
import sys
import time
import threading
from datetime import datetime, timedelta as datetime_timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

import certifi
from motor.motor_asyncio import AsyncIOMotorClient

# ── Config — load backend .env, then admin-dashboard/.env (override) ─

_BACKEND_ENV = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
_ADMIN_ENV = os.path.join(os.path.dirname(__file__), ".env")


def _parse_env_file(path: str, override: bool) -> None:
    if not os.path.exists(path):
        return
    with open(path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
                if not _k:
                    continue
                if override or _k not in os.environ:
                    os.environ[_k] = _v


try:
    from dotenv import load_dotenv
    # Admin dashboard must follow repo .env: shell-exported MONGODB_URI (old cluster)
    # would otherwise win if we used override=False.
    load_dotenv(_BACKEND_ENV, override=True)
    load_dotenv(_ADMIN_ENV, override=True)
except ImportError:
    _parse_env_file(_BACKEND_ENV, override=True)
    _parse_env_file(_ADMIN_ENV, override=True)

MONGO_URI = (os.environ.get("DASHBOARD_MONGODB_URI") or os.environ.get("MONGODB_URI", "")).strip()
if not MONGO_URI:
    sys.exit(
        "No Mongo URI: set DASHBOARD_MONGODB_URI or MONGODB_URI "
        "(admin-dashboard/.env or ../backend/.env)."
    )

# Same DB name as backend (e.g. myprofessor on Capacity Atlas, tutor_v2 elsewhere)
MONGO_DB_NAME = os.environ.get("MONGODB_DB", "tutor_v2").strip() or "tutor_v2"

PORT = int(os.environ.get("DASHBOARD_PORT", "4000"))


def _qs_first(qs: dict, key: str, default: str = "") -> str:
    vals = qs.get(key) or []
    if not vals:
        return default
    v = vals[0]
    return str(v) if v is not None else default


def parse_unified_filter_string(raw: str) -> tuple[str, list[str], list[str]]:
    """Parse a single ``filter`` string into (domain, includes, excludes).

    Tokens are whitespace-separated. Examples that work:
      ``@seekcapacity.com``  → restrict to that domain
      ``mayank``             → email/name contains "mayank"
      ``-test.com``          → exclude anything containing "test.com"
      ``!gmail.com``         → exclude anything containing "gmail.com"

    Combine freely:
      ``@seekcapacity.com -test``  → @seekcapacity.com but not "test"
      ``mayank -@gmail.com``       → has "mayank" but not on gmail

    Multiple includes are AND-ed (must match all). Domain takes the
    last ``@x`` seen — there's only one domain in play at a time.
    """
    domain = ""
    includes: list[str] = []
    excludes: list[str] = []
    for tok in (raw or "").split():
        tok = tok.strip()
        if not tok:
            continue
        # Negation prefix → exclude (also supports `-@gmail.com` to
        # exclude an entire domain by treating it as a substring).
        if tok[0] in ("-", "!"):
            seg = tok[1:].strip()
            if seg:
                excludes.append(seg)
            continue
        # Bare domain (starts with @) → restrict to that domain.
        if tok.startswith("@"):
            domain = tok[1:].lower()
            continue
        # Looks like a domain (no @ but has a dot and no spaces and
        # ends with a TLD-ish segment). Treat as domain too — common
        # case: user types ``seekcapacity.com`` without the @.
        if (
            "." in tok
            and "@" not in tok
            and "/" not in tok
            and len(tok.split(".")[-1]) >= 2
        ):
            domain = tok.lower()
            continue
        includes.append(tok)
    return domain, includes, excludes


def parse_email_filter_parts(qs: dict) -> tuple[str, list[str], list[str]]:
    """Build (domain, includes, excludes) from the query string.

    Prefers the new single ``filter`` param when present. Falls back to
    the legacy ``domain`` / ``email_contains`` / ``email_exclude`` params
    so saved URLs and bookmarks keep working.
    """
    raw = _qs_first(qs, "filter").strip()
    if raw:
        return parse_unified_filter_string(raw)

    domain = _qs_first(qs, "domain").strip().lower()
    if domain.startswith("@"):
        domain = domain[1:]
    contains = _qs_first(qs, "email_contains").strip()
    includes = [contains] if contains else []
    exclude_raw = _qs_first(qs, "email_exclude").strip()
    excludes = [s.strip() for s in exclude_raw.split(",") if s.strip()]
    return domain, includes, excludes


def filter_fingerprint_parts(domain: str, includes: list[str], excludes: list[str]) -> str:
    if not domain and not includes and not excludes:
        return "all"
    raw = f"{domain}|{','.join(includes)}|{','.join(excludes)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _filters_payload(domain: str, includes: list[str], excludes: list[str]) -> dict:
    """Echo the active filter back to the FE in a single shape.

    The FE renders one chip per part so users can see exactly what's
    being applied without re-parsing the input string. ``filterRaw`` is
    a faithful round-trip of the input so the FE can pre-fill the box
    after a hard reload.
    """
    raw_parts: list[str] = []
    if domain:
        raw_parts.append("@" + domain)
    raw_parts.extend(includes)
    raw_parts.extend("-" + e for e in excludes)
    return {
        "active": bool(domain or includes or excludes),
        "filterRaw": " ".join(raw_parts),
        "domain": domain,
        "includes": includes,
        "excludes": excludes,
        # Legacy fields for any old code/links still reading the
        # old shape — mirrors the new structure as best it can.
        "email_contains": ",".join(includes),
        "email_exclude": ",".join(excludes),
    }


def email_match_for_field(field: str, domain: str,
                          includes: list[str], excludes: list[str]):
    """Mongo fragment for one field (userEmail on sessions, email on users).
    Returns None when there's no active filter.
    """
    parts: list[dict] = []
    if domain:
        parts.append({field: {"$regex": re.escape("@" + domain) + "$", "$options": "i"}})
    for inc in includes:
        parts.append({field: {"$regex": re.escape(inc), "$options": "i"}})
    for exc in excludes:
        parts.append({field: {"$not": {"$regex": re.escape(exc), "$options": "i"}}})
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}


def merge_mongo_filters(*parts: dict | None) -> dict:
    fs = [p for p in parts if p]
    if not fs:
        return {}
    if len(fs) == 1:
        return fs[0]
    return {"$and": fs}


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
    return get_client()[MONGO_DB_NAME]


async def ensure_indexes():
    """Create indexes used by dashboard queries — idempotent / no-op if exist."""
    print(
        "  ... Connecting to MongoDB and ensuring indexes (first run can take ~10-30s) ...",
        flush=True,
    )
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
        print("  OK Indexes ensured", flush=True)
    except Exception as e:
        print(f"  WARN Could not ensure indexes: {e}", flush=True)


# ── TTL cache ───────────────────────────────────────────────────────

_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()
CACHE_TTL = 60  # seconds — stats/users/analytics
CACHE_TTL_SESSIONS = 12  # shorter: session list should feel up to date when switching tabs / refreshing

def cache_get(key: str):
    ttl = CACHE_TTL_SESSIONS if key.startswith("sessions_") else CACHE_TTL
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry[0]) < ttl:
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


def _shorten_text(text: str, n: int = 140) -> str:
    """Collapse whitespace + truncate a long string with an ellipsis on a word boundary."""
    if not text:
        return ""
    s = re.sub(r"\s+", " ", str(text)).strip()
    if len(s) <= n:
        return s
    cut = s[: n - 1]
    sp = cut.rfind(" ")
    if sp > int(n * 0.6):
        cut = cut[:sp]
    return cut + "\u2026"


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

def _mongo_stats_meta() -> dict:
    """Non-sensitive cluster identity for /api/stats (so DevTools can confirm the active URI)."""
    return {
        "mongoHost": urlparse(MONGO_URI).hostname or "",
        "mongoDb": MONGO_DB_NAME,
    }


async def fetch_stats(qs: dict | None = None):
    qs = qs or {}
    domain, includes, excludes = parse_email_filter_parts(qs)
    fp = filter_fingerprint_parts(domain, includes, excludes)
    cache_key = f"stats_v3_{fp}"
    cached = cache_get(cache_key)
    if cached:
        out = dict(cached)
        out.update(_mongo_stats_meta())
        return out
    db = get_db()
    sess_email = email_match_for_field("userEmail", domain, includes, excludes)
    user_email = email_match_for_field("email", domain, includes, excludes)

    total_users = await db.users.count_documents(user_email or {})
    total_sessions = await db.sessions.count_documents(sess_email or {})
    active_sessions = await db.sessions.count_documents(
        merge_mongo_filters(sess_email, {"status": "active"})
    )
    external_sessions = await db.sessions.count_documents(
        merge_mongo_filters(sess_email, {"userEmail": {"$ne": "mayank@test.com"}})
    )

    # Cost aggregation via MongoDB $group (pushes math to the DB)
    # createdAt is stored as an ISO string, so we compare lexically with .isoformat()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    async def _sum_cost(date_match: dict) -> dict:
        merged = merge_mongo_filters(sess_email, date_match)
        pipeline = [
            {"$match": merged},
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

    # ── Path adoption: how many sessions / users came in via a path ──
    # A "path session" is one where backendState.pathId is populated —
    # set when the student clicked Learn from a path or subtopic. Anything
    # without a pathId is a "single" entry (chat-box / direct intent).
    path_session_match = merge_mongo_filters(
        sess_email,
        {"backendState.pathId": {"$exists": True, "$nin": [None, ""]}},
    )
    path_sessions = await db.sessions.count_documents(path_session_match)
    single_sessions = max(0, total_sessions - path_sessions)

    # Distinct users who ever launched a path session
    path_user_emails = await db.sessions.distinct("userEmail", path_session_match)
    path_users = len({e for e in path_user_emails if e})

    # Total paths created (any status) — independent of sessions.
    # Reuse the same email filter so a stakeholder filtering by
    # `@seekcapacity.com` sees the same scoped numbers everywhere.
    # Paths collection uses `userEmail` (same as sessions), so reuse
    # the session email filter directly.
    paths_filter = sess_email or {}
    paths_total = 0
    paths_active = 0
    try:
        paths_total = await db.paths.count_documents(paths_filter)
        paths_active = await db.paths.count_documents(
            merge_mongo_filters(paths_filter, {"status": "active"})
        )
    except Exception:
        # paths collection may not yet exist on fresh installs
        pass

    result = {
        "totalUsers": total_users,
        "totalSessions": total_sessions,
        "activeSessions": active_sessions,
        "externalSessions": external_sessions,
        "pathSessions": path_sessions,
        "singleSessions": single_sessions,
        "pathUsers": path_users,
        "pathAdoptionPct": round(path_users / total_users * 100, 1) if total_users else 0,
        "pathSessionsPct": round(path_sessions / total_sessions * 100, 1) if total_sessions else 0,
        "pathsTotal": paths_total,
        "pathsActive": paths_active,
        "costAllCents": cost_all["llm"] + cost_all["tts"],
        "costAllLlmCents": cost_all["llm"],
        "costAllTtsCents": cost_all["tts"],
        "costMonthCents": cost_month["llm"] + cost_month["tts"],
        "costTodayCents": cost_today["llm"] + cost_today["tts"],
        "ts": datetime.now(timezone.utc).isoformat(),
        "filters": _filters_payload(domain, includes, excludes),
    }
    result.update(_mongo_stats_meta())
    cache_set(cache_key, result)
    return result


async def fetch_users(qs: dict | None = None):
    """Optimized user-aggregation:
      1. Mongo $group — counts/costs/per-session min/max timestamps (server-side, fast)
      2. For sessions whose span exceeds the active-period gap, pull
         transcript timestamps and refine via active-period split.
      3. For sessions whose span is short (under the active-period gap),
         span ≈ active by construction (no internal idle gap can fit).

    Why the 4h threshold was wrong: a 1h session with one 30-minute idle
    gap genuinely had ~30min of active dwell, but the old code reported
    1h because 1h < 4h ("not an outlier") and just used span as active.
    Sessions with span > ACTIVE_PERIOD_GAP_SEC (15min) are the ones that
    CAN have an internal gap, so those are the ones we must refine.
    """
    qs = qs or {}
    domain, includes, excludes = parse_email_filter_parts(qs)
    fp = filter_fingerprint_parts(domain, includes, excludes)
    cached = cache_get(f"users_v2_{fp}")
    if cached:
        return cached
    db = get_db()
    # Refine any session whose span could plausibly contain an idle gap
    # large enough to skew the active-time number. Equal to the
    # active-period gap so the same definition is enforced everywhere.
    OUTLIER_GAP_SEC = ACTIVE_PERIOD_GAP_SEC

    sess_email = email_match_for_field("userEmail", domain, includes, excludes)
    user_email = email_match_for_field("email", domain, includes, excludes)

    # Single aggregation: counts + costs + min/max timestamp per session, then
    # group by user. We sum span-from-min/max here and tag outlier sessions for
    # later refinement.
    users_fut = db.users.find(
        user_email or {},
        {"name": 1, "email": 1, "createdAt": 1},
    ).sort("createdAt", -1).to_list(length=500)

    agg_pipeline: list = []
    if sess_email:
        agg_pipeline.append({"$match": sess_email})
    agg_pipeline.extend([
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
    ])
    sessions_agg_fut = db.sessions.aggregate(agg_pipeline, allowDiskUse=True).to_list(length=1000)

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
    cache_set(f"users_v2_{fp}", result)
    return result


async def fetch_sessions(limit: int = 50, offset: int = 0, q: str = "", qs: dict | None = None):
    """Paginated sessions list. Default 50/page; supports search filter on
    userEmail / studentName / title / intent.
    """
    qs = qs or {}
    domain, includes, excludes = parse_email_filter_parts(qs)
    fp = filter_fingerprint_parts(domain, includes, excludes)
    cache_key = f"sessions_v6_{limit}_{offset}_{q.lower()}_{fp}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    db = get_db()

    # Build search filter — server-side, uses indexes when possible
    match = {}
    if q:
        ql = q.strip()
        if ql:
            # Case-insensitive substring across the relevant fields
            qre = re.compile(re.escape(ql), re.IGNORECASE)
            match = {"$or": [
                {"userEmail": qre},
                {"studentName": qre},
                {"title": qre},
                {"headline": qre},
                {"intent.raw": qre},
            ]}

    sess_email = email_match_for_field("userEmail", domain, includes, excludes)
    if sess_email and match:
        match = {"$and": [match, sess_email]}
    elif sess_email:
        match = sess_email

    # Get total count (cached separately so we don't recount each page)
    count_key = f"sessions_count_{q.lower()}_{fp}"
    cached_count = cache_get(count_key)
    if cached_count is None:
        total = await db.sessions.count_documents(match)
        cache_set(count_key, total)
    else:
        total = cached_count

    # Pull a small slice of transcript so we can compute active time AND show
    # what the user actually typed without opening the modal. Content is bounded
    # by the per-row truncation below so it stays cheap on the wire.
    sessions = await db.sessions.find(
        match,
        {
            "userEmail": 1, "studentName": 1, "title": 1, "headline": 1,
            "createdAt": 1, "durationSec": 1, "metrics": 1, "intent": 1,
            "status": 1, "teachingMode": 1,
            "transcript": {"$slice": 12},
            "backendState.sessionMode": 1,
            "backendState.studentIntent": 1,
            "backendState.problemData.name": 1,
            "backendState.problemData.slug": 1,
            "backendState.problemData.difficulty": 1,
            "backendState.llmCostCents": 1,
            "backendState.ttsCostCents": 1,
            "backendState.llmCallCount": 1,
            "backendState.llmTotalInputTokens": 1,
            "backendState.llmTotalOutputTokens": 1,
            "backendState.ttsCharCount": 1,
            # Path linkage — set on sessions started from a path's
            # Learn button. Drives the PATH badge in the UI and lets
            # us split overall metrics into "path" vs "single-session".
            "backendState.pathId": 1,
            "backendState.nodeId": 1,
        },
    ).sort("createdAt", -1).skip(offset).limit(limit).to_list(length=limit)

    # Resolve path titles + node positions for any session linked to a
    # path. Single round trip per page (max 50 paths) — uses the indexed
    # pathId field. We strip out the nodes payload to keep this cheap.
    path_ids = list({(s.get("backendState") or {}).get("pathId")
                     for s in sessions
                     if (s.get("backendState") or {}).get("pathId")})
    path_lookup: dict = {}
    if path_ids:
        async for p in db.paths.find(
            {"pathId": {"$in": path_ids}},
            {"pathId": 1, "title": 1, "nodes.nodeId": 1, "nodes.order": 1,
             "nodes.phase": 1, "nodes.title": 1},
        ):
            path_lookup[p["pathId"]] = p

    result = []
    for s in sessions:
        metrics = s.get("metrics") or {}
        intent = s.get("intent") or {}
        raw_intent = intent.get("raw", "") if isinstance(intent, dict) else str(intent)
        dur = s.get("durationSec") or 0
        bs = s.get("backendState") or {}
        llm_c = bs.get("llmCostCents") or 0
        tts_c = bs.get("ttsCostCents") or 0
        transcript_slice = s.get("transcript", []) or []
        timing = compute_interaction_time(transcript_slice)
        pd = bs.get("problemData") if isinstance(bs.get("problemData"), dict) else {}

        first_user_msg = ""
        user_msg_count = 0
        for turn in transcript_slice:
            if not isinstance(turn, dict):
                continue
            role = str(turn.get("role", turn.get("speaker", ""))).lower()
            if role not in ("user", "student"):
                continue
            content = _flatten_message_content(
                turn.get("content", turn.get("text", turn.get("message", ""))),
                cap=400,
            )
            if not content or content.startswith("[SYSTEM]"):
                continue
            user_msg_count += 1
            if not first_user_msg:
                first_user_msg = content[:280]
            if user_msg_count >= 6:
                break

        raw_title = s.get("title") or s.get("headline") or "(no title)"

        # Path linkage summary — shown as a PATH badge + tooltip in the
        # Sessions list, and reused by stats / analytics for the
        # "started a path" cohort split.
        path_id = bs.get("pathId") or ""
        node_id = bs.get("nodeId") or ""
        path_title = ""
        node_order = None
        node_phase = None
        node_title = ""
        path_total_nodes = 0
        if path_id and path_id in path_lookup:
            pdoc = path_lookup[path_id]
            path_title = pdoc.get("title", "") or ""
            nodes = pdoc.get("nodes") or []
            path_total_nodes = len(nodes)
            for n in nodes:
                if n.get("nodeId") == node_id:
                    node_order = n.get("order")
                    node_phase = n.get("phase")
                    node_title = (n.get("title") or "")[:80]
                    break

        result.append({
            "_id": str(s.get("_id", "")),
            "user": s.get("studentName", "?"),
            "email": s.get("userEmail", ""),
            "title": _shorten_text(raw_title, 140),
            "titleFull": _shorten_text(raw_title, 4000),
            "sessionMode": bs.get("sessionMode") or "general",
            "studentIntent": (bs.get("studentIntent") or "")[:280],
            "firstUserMsg": first_user_msg,
            "problemSlug": (pd.get("slug") or "")[:120],
            "problemName": (pd.get("name") or "")[:120],
            "problemDifficulty": (pd.get("difficulty") or "")[:32],
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
            "costCents": round(llm_c + tts_c, 2),
            "llmCents": round(llm_c, 2),
            "ttsCents": round(tts_c, 2),
            "llmCalls": bs.get("llmCallCount") or 0,
            "inputTokens": bs.get("llmTotalInputTokens") or 0,
            "outputTokens": bs.get("llmTotalOutputTokens") or 0,
            "ttsChars": bs.get("ttsCharCount") or 0,
            # Entry-point: "path" if this session was launched from a
            # path's Learn button, "single" otherwise. Used to split
            # adoption funnels in the dashboard.
            "entryType": "path" if path_id else "single",
            "pathId": path_id,
            "pathTitle": path_title,
            "nodeId": node_id,
            "nodeOrder": node_order,
            "nodePhase": node_phase,
            "nodeTitle": node_title,
            "pathTotalNodes": path_total_nodes,
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


async def fetch_analytics(days: int = 30, qs: dict | None = None):
    """Time-series + aggregates for the Analytics tab."""
    qs = qs or {}
    domain, includes, excludes = parse_email_filter_parts(qs)
    fp = filter_fingerprint_parts(domain, includes, excludes)
    cache_key = f"analytics_v3_{days}_{fp}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    db = get_db()
    now = datetime.now(timezone.utc)
    sess_f = email_match_for_field("userEmail", domain, includes, excludes)
    user_f = email_match_for_field("email", domain, includes, excludes)

    def _iso(dt: datetime) -> str:
        return dt.isoformat()

    since = _iso(now - datetime_timedelta(days=days))
    week_ago = _iso(now - datetime_timedelta(days=7))
    day_ago = _iso(now - datetime_timedelta(days=1))
    month_ago = _iso(now - datetime_timedelta(days=30))

    # ── Signups per day (last N days) — substring on string createdAt ──
    signup_match = merge_mongo_filters({"createdAt": {"$gte": since}}, user_f)
    signup_pipeline = [
        {"$match": signup_match},
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
    sess_day_match = merge_mongo_filters({"createdAt": {"$gte": since}}, sess_f)
    sess_pipeline = [
        {"$match": sess_day_match},
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
    async def _unique_active_users(gte_iso: str) -> int:
        pipeline = [
            {"$match": merge_mongo_filters(
                {"transcript.timestamp": {"$gte": gte_iso}},
                sess_f,
            )},
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
        {"$match": sess_day_match},
        {"$group": {"_id": "$teachingMode", "count": {"$sum": 1}}},
    ]
    mode_split = {r["_id"] or "unknown": r["count"] async for r in db.sessions.aggregate(mode_pipeline)}

    # ── Status breakdown ──
    status_pipeline = [
        {"$match": sess_day_match},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    status_breakdown = {r["_id"] or "unknown": r["count"] async for r in db.sessions.aggregate(status_pipeline)}

    # ── Top topics (from intent.raw / headline / title, whichever populated) ──
    topic_pipeline = [
        {"$match": sess_day_match},
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
        {"$match": sess_day_match},
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
        cohort_q = merge_mongo_filters(
            {"createdAt": {"$gte": cohort_start_iso, "$lt": cohort_end_iso}},
            sess_f,
        )
        cohort = await db.sessions.distinct("userEmail", cohort_q)
        cohort = {u for u in cohort if u}
        if not cohort:
            return {"cohort": 0, "returned": 0, "rate": 0}
        returned_q = merge_mongo_filters(
            {
                "userEmail": {"$in": list(cohort)},
                "createdAt": {"$gte": return_since_iso},
            },
            sess_f,
        )
        returned = await db.sessions.distinct("userEmail", returned_q)
        returned = {u for u in returned if u}
        rate = len(returned) / len(cohort) * 100 if cohort else 0
        return {"cohort": len(cohort), "returned": len(returned), "rate": round(rate, 1)}

    td = datetime_timedelta
    # 1-day return: cohort = users with a session 2d-1d ago, returned = had another session in last 24h
    ret_1d = await _return_rate(_iso(now - td(days=2)), _iso(now - td(days=1)), _iso(now - td(days=1)))
    # 2-day return: cohort = users with a session 3d-2d ago, returned = had another session in last 48h
    ret_2d = await _return_rate(_iso(now - td(days=3)), _iso(now - td(days=2)), _iso(now - td(days=2)))
    # 7-day return: cohort = users with a session 14d-7d ago, returned = had another session in last 7d
    ret_7d = await _return_rate(_iso(now - td(days=14)), _iso(now - td(days=7)), _iso(now - td(days=7)))
    # 30-day return: cohort = users with a session 60d-30d ago, returned = had another session in last 30d
    ret_30d = await _return_rate(_iso(now - td(days=60)), _iso(now - td(days=30)), _iso(now - td(days=30)))

    # ── Path adoption funnel + per-cohort averages ───────────────────
    path_match_window = merge_mongo_filters(
        sess_day_match,
        {"backendState.pathId": {"$exists": True, "$nin": [None, ""]}},
    )
    path_sessions_window = await db.sessions.count_documents(path_match_window)
    path_users_window = len({u for u in await db.sessions.distinct("userEmail", path_match_window) if u})
    single_match_window = merge_mongo_filters(
        sess_day_match,
        {"$or": [
            {"backendState.pathId": {"$exists": False}},
            {"backendState.pathId": None},
            {"backendState.pathId": ""},
        ]},
    )
    single_sessions_window = await db.sessions.count_documents(single_match_window)
    single_users_window = len({u for u in await db.sessions.distinct("userEmail", single_match_window) if u})

    # ── Avg sessions per active user + avg session active time ───────
    # Active user = any user with at least one session in the window.
    # Sessions/user is the headline "stickiness" number stakeholders ask
    # for. Avg session length uses the same active-period definition as
    # the Users tab so the two screens agree.
    active_users_window = await db.sessions.distinct("userEmail", sess_day_match)
    active_users_window = [u for u in active_users_window if u]
    avg_sessions_per_user = (
        totals["sessions"] / len(active_users_window)
        if active_users_window else 0
    )

    # Pull session spans + flag potential idle-gap outliers, then refine
    # the long ones by reading transcript timestamps. Same approach as
    # fetch_users so the numbers reconcile. We cap to 2000 sessions in
    # the window to keep this responsive on large datasets.
    span_pipeline = [
        {"$match": sess_day_match},
        {"$addFields": {
            "_minTs": {"$min": "$transcript.timestamp"},
            "_maxTs": {"$max": "$transcript.timestamp"},
        }},
        {"$addFields": {
            "_spanSec": {
                "$cond": {
                    "if": {"$and": [{"$ne": ["$_minTs", None]}, {"$ne": ["$_maxTs", None]}]},
                    "then": {"$divide": [
                        {"$subtract": [
                            {"$dateFromString": {"dateString": "$_maxTs", "onError": None}},
                            {"$dateFromString": {"dateString": "$_minTs", "onError": None}},
                        ]},
                        1000,
                    ]},
                    "else": 0,
                }
            },
        }},
        {"$project": {"_id": 1, "_spanSec": 1}},
        {"$limit": 2000},
    ]
    span_rows = [r async for r in db.sessions.aggregate(span_pipeline, allowDiskUse=True)]
    short_sum = 0
    short_count = 0
    long_ids = []
    for r in span_rows:
        sp = r.get("_spanSec") or 0
        if sp <= ACTIVE_PERIOD_GAP_SEC:
            short_sum += sp
            short_count += 1
        else:
            long_ids.append(r["_id"])

    long_active_sum = 0
    long_count = 0
    if long_ids:
        cur = db.sessions.find(
            {"_id": {"$in": long_ids}},
            {"transcript.timestamp": 1},
        )
        async for s in cur:
            timing = compute_interaction_time(s.get("transcript", []))
            long_active_sum += timing["activeSec"]
            long_count += 1
    total_active = short_sum + long_active_sum
    total_session_count = short_count + long_count
    avg_session_active_sec = (total_active / total_session_count) if total_session_count else 0

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
        "avgSessionsPerUser": round(avg_sessions_per_user, 2),
        "avgSessionActiveSec": int(avg_session_active_sec),
        "activeUsersWindow": len(active_users_window),
        "pathFunnel": {
            "pathSessions": path_sessions_window,
            "pathUsers": path_users_window,
            "singleSessions": single_sessions_window,
            "singleUsers": single_users_window,
            # Use the unbounded totals["sessions"] count as the denominator
            # so the percentage stays accurate even if span_pipeline was
            # capped at 2000 docs.
            "pathPctOfSessions": round(
                path_sessions_window / max(1, totals["sessions"]) * 100, 1
            ),
            "pathPctOfUsers": round(
                path_users_window / max(1, len(active_users_window)) * 100, 1
            ),
        },
        "returnRate1d": ret_1d,
        "returnRate2d": ret_2d,
        "returnRate7d": ret_7d,
        "returnRate30d": ret_30d,
        "filters": _filters_payload(domain, includes, excludes),
    }
    cache_set(cache_key, result)
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
    """Per-session details: costs + full visibility (intent, DSA/SD, blueprint, inputs)."""
    cache_key = f"detail_v4_{session_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    from bson import ObjectId
    db = get_db()
    s = None
    proj = {
        "backendState": 1,
        "intent": 1,
        "headline": 1,
        "title": 1,
        "teachingMode": 1,
        "status": 1,
        "metrics": 1,
        "dsaState": 1,
        "userEmail": 1,
        "studentName": 1,
        "transcript": {"$slice": -80},
    }
    try:
        s = await db.sessions.find_one({"_id": ObjectId(session_id)}, proj)
    except Exception:
        pass
    if not s:
        try:
            s = await db.sessions.find_one({"sessionId": session_id}, proj)
        except Exception:
            s = None
    if not s:
        return {"error": "not found"}
    bs = s.get("backendState") or {}
    raw_title_d = s.get("title") or s.get("headline") or ""

    # ── Path context: enrich the insight with full path linkage so the
    # session-detail modal can show "Session 3 of 14, Phase 2, focus
    # subtopic = X" with a link to the path doc. Cheap: one find_one
    # per detail open.
    path_ctx = None
    p_id = bs.get("pathId")
    n_id = bs.get("nodeId")
    if p_id:
        try:
            pdoc = await db.paths.find_one(
                {"pathId": p_id},
                {"pathId": 1, "title": 1, "description": 1, "status": 1,
                 "nodes": 1, "userEmail": 1, "createdAt": 1},
            )
        except Exception:
            pdoc = None
        if pdoc:
            nodes = pdoc.get("nodes") or []
            this_node = next((n for n in nodes if n.get("nodeId") == n_id), None)
            done = sum(1 for n in nodes if (n.get("status") or "") in ("complete", "completed", "done"))
            path_ctx = {
                "pathId": pdoc.get("pathId"),
                "pathTitle": pdoc.get("title"),
                "pathDescription": (pdoc.get("description") or "")[:400],
                "pathStatus": pdoc.get("status"),
                "pathOwnerEmail": pdoc.get("userEmail"),
                "totalNodes": len(nodes),
                "completedNodes": done,
                "completedPct": round(done / len(nodes) * 100, 1) if nodes else 0,
                "currentNodeId": n_id,
                "currentNodeOrder": this_node.get("order") if this_node else None,
                "currentNodePhase": this_node.get("phase") if this_node else None,
                "currentNodeTitle": (this_node.get("title") or "")[:160] if this_node else "",
                "currentNodeStatus": this_node.get("status") if this_node else "",
                "currentNodeTopics": (this_node.get("topics") or [])[:12] if this_node else [],
                "currentNodeStudentNote": ((this_node.get("studentNote") or "")[:600]
                                           if this_node else ""),
            }

    insight = _build_session_insight(s)
    if path_ctx:
        insight["pathContext"] = path_ctx
        insight["entryType"] = "path"
    else:
        insight["entryType"] = "single"

    result = {
        "title": _shorten_text(raw_title_d, 200),
        "titleFull": _shorten_text(raw_title_d, 8000),
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
        "sessionInsight": insight,
    }
    cache_set(cache_key, result)
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


def _flatten_message_content(content, cap: int = 12000) -> str:
    """Turn transcript / message content into a single string (truncated)."""
    if content is None:
        return ""
    if isinstance(content, str):
        t = content
    elif isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        t = " ".join(parts)
    else:
        t = str(content)
    t = t.strip()
    if len(t) > cap:
        return t[:cap] + "\n… [truncated]"
    return t


def _sanitize_dsa_state(d: dict | None) -> dict | None:
    if not d or not isinstance(d, dict):
        return None
    out = dict(d)
    code = out.get("code")
    if isinstance(code, str) and len(code) > 16000:
        out["code"] = code[:16000] + "\n… [truncated]"
    for k in ("canvasJSON", "lldCanvasJSON"):
        v = out.get(k)
        if isinstance(v, str) and len(v) > 4000:
            out[k] = v[:4000] + "… [truncated]"
    tr = out.get("testResults")
    if isinstance(tr, dict) and len(json.dumps(tr, default=str)) > 8000:
        out["testResults"] = {"_truncated": True, "summary": str(tr.get("summary", tr))[:2000]}
    return out


def _blueprint_summary(bp: dict | None) -> dict | None:
    if not bp or not isinstance(bp, dict):
        return None
    return {
        "mode": bp.get("mode"),
        "interaction": bp.get("interaction"),
        "ui_layout": bp.get("ui_layout"),
        "problem_slug": bp.get("problem_slug"),
        "mock_company": bp.get("mock_company"),
        "mock_timer_minutes": bp.get("mock_timer_minutes"),
        "tools_enable": bp.get("tools_enable"),
        "tools_disable": bp.get("tools_disable"),
        "prompt_sections_count": len(bp.get("prompt_sections") or []),
    }


def _problem_data_summary(pd) -> dict | None:
    if not pd or not isinstance(pd, dict):
        return None
    return {
        "name": pd.get("name"),
        "slug": pd.get("slug"),
        "difficulty": pd.get("difficulty"),
        "num": pd.get("num"),
    }


def _build_session_insight(doc: dict) -> dict:
    """Structured view of what the student did (intent, DSA/SD, blueprint, inputs)."""
    bs = doc.get("backendState") or {}
    intent = doc.get("intent") or {}
    intent_raw = intent.get("raw", "") if isinstance(intent, dict) else str(intent)
    transcript = doc.get("transcript") or []
    recent_user_lines: list[str] = []
    for turn in transcript[-30:]:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role", turn.get("speaker", ""))).lower()
        if role not in ("user", "student"):
            continue
        line = _flatten_message_content(
            turn.get("content", turn.get("text", turn.get("message", ""))),
            cap=4000,
        )
        if line and not line.startswith("[SYSTEM]"):
            recent_user_lines.append(line[:4000])
    tail = recent_user_lines[-8:]  # last 8 user-visible inputs in window

    msgs = bs.get("messages") or []
    msg_tail = []
    if isinstance(msgs, list):
        for m in msgs[-25:]:
            if not isinstance(m, dict):
                continue
            role = m.get("role", "?")
            msg_tail.append({
                "role": role,
                "content": _flatten_message_content(m.get("content"), cap=6000),
            })

    return {
        "intentRaw": _shorten_text(intent_raw, 4000),
        "headline": _shorten_text(doc.get("headline") or doc.get("title") or "", 240),
        "sessionTeachingMode": doc.get("teachingMode") or "",
        "sessionStatus": doc.get("status") or "",
        "backendSessionMode": bs.get("sessionMode") or "general",
        "studentIntent": (bs.get("studentIntent") or "")[:4000],
        "phase": bs.get("phase"),
        "blueprint": _blueprint_summary(bs.get("blueprint")),
        "problemData": _problem_data_summary(bs.get("problemData")),
        "dsaState": _sanitize_dsa_state(doc.get("dsaState")),
        "codeCanvas": {
            "hasCodeState": bool(bs.get("codeState")),
            "hasCanvasState": bool(bs.get("canvasState")),
        },
        "mock": {
            "phase": bs.get("mockPhase"),
            "company": bs.get("mockCompany"),
            "hintsUsed": bs.get("mockHintsUsed"),
        },
        "recentUserInputs": tail,
        "serverMessageTail": msg_tail,
        "metrics": doc.get("metrics") if isinstance(doc.get("metrics"), dict) else {},
    }


# ── Replay data ─────────────────────────────────────────────────────

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


# ── Follow-up email (Resend) ─────────────────────────────────────────

RESEND_API_URL = "https://api.resend.com/emails"

# Default From: address. Resend requires a verified sender domain. The free
# default `onboarding@resend.dev` works without verification but goes to spam
# more often. Override via FOLLOWUP_FROM in env once a domain is verified.
FOLLOWUP_FROM_DEFAULT = "myprofessor.live <onboarding@resend.dev>"


def _short(text: str, n: int = 240) -> str:
    s = (text or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "\u2026"


def _build_followup_draft(doc: dict) -> dict:
    """Compose a short, kind follow-up email based on a session document.

    Returns: { to, fromEmail, subject, text, html, meta }
    """
    bs = doc.get("backendState") or {}
    intent = doc.get("intent") or {}
    intent_raw = intent.get("raw", "") if isinstance(intent, dict) else str(intent)
    transcript = doc.get("transcript") or []

    student_name = doc.get("studentName") or ""
    first_name = (student_name.split(" ")[0] if student_name else "").strip() or "there"

    user_lines: list[str] = []
    for turn in transcript:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role", turn.get("speaker", ""))).lower()
        if role not in ("user", "student"):
            continue
        line = _flatten_message_content(
            turn.get("content", turn.get("text", turn.get("message", ""))),
            cap=400,
        )
        if line and not line.startswith("[SYSTEM]"):
            user_lines.append(line)

    first_user = _short(user_lines[0] if user_lines else (intent_raw or bs.get("studentIntent") or ""), 220)
    last_user = _short(user_lines[-1] if user_lines else "", 220)

    pd = bs.get("problemData") if isinstance(bs.get("problemData"), dict) else {}
    problem_name = pd.get("name") or ""
    problem_slug = pd.get("slug") or ""
    session_mode = bs.get("sessionMode") or "general"

    metrics = doc.get("metrics") if isinstance(doc.get("metrics"), dict) else {}
    turns = metrics.get("totalTurns") or 0
    duration_sec = doc.get("durationSec") or 0

    short_session = (turns and turns <= 3) or (duration_sec and duration_sec < 180)

    topic_label = problem_name or problem_slug or doc.get("title") or doc.get("headline") or ""
    topic_phrase = f" while working on {topic_label}" if topic_label else ""

    if short_session:
        subject = "Quick check-in from myprofessor.live"
        opener = (
            f"Hi {first_name},\n\n"
            f"I am writing from myprofessor.live, and I noticed your session ended "
            f"pretty quickly{topic_phrase}. I wanted to reach out personally before "
            f"assuming the worst."
        )
    else:
        subject = "Following up on your myprofessor.live session"
        opener = (
            f"Hi {first_name},\n\n"
            f"Thanks for spending time on myprofessor.live today"
            f"{topic_phrase}. I wanted to make sure it actually moved you forward."
        )

    context_lines: list[str] = []
    if first_user:
        context_lines.append(f"You started with: \u201C{first_user}\u201D")
    if last_user and last_user != first_user:
        context_lines.append(f"You ended on: \u201C{last_user}\u201D")
    context_block = "\n".join(context_lines)

    ask = (
        "Could you reply with one line on what was missing? For example:\n"
        "  - tutor explanation / pace\n"
        "  - the problem or topic that was picked\n"
        "  - voice, latency, or UI issues\n"
        "  - something else\n\n"
        "Whatever you say goes straight to me. If you are open to it, I will personally "
        "set up a free, redo session and make sure it actually helps."
    )

    sign_off = "\n\nThanks for trying it,\n\u2014 The myprofessor.live team"

    text_body = "\n\n".join([opener] + ([context_block] if context_block else []) + [ask]) + sign_off

    def _p(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html_parts = [f"<p>{_p(opener).replace(chr(10), '<br>')}</p>"]
    if context_block:
        html_parts.append(
            "<blockquote style=\"border-left:3px solid #ccc;margin:0;padding:6px 12px;color:#444;font-style:italic\">"
            + _p(context_block).replace("\n", "<br>")
            + "</blockquote>"
        )
    html_parts.append(
        "<p>Could you reply with one line on what was missing? For example:</p>"
        "<ul>"
        "<li>tutor explanation / pace</li>"
        "<li>the problem or topic that was picked</li>"
        "<li>voice, latency, or UI issues</li>"
        "<li>something else</li>"
        "</ul>"
        "<p>Whatever you say goes straight to me. If you are open to it, I will personally set up a "
        "free, redo session and make sure it actually helps.</p>"
        "<p>Thanks for trying it,<br>\u2014 The myprofessor.live team</p>"
    )
    html_body = "".join(html_parts)

    return {
        "to": (doc.get("userEmail") or "").strip(),
        "fromEmail": os.environ.get("FOLLOWUP_FROM", FOLLOWUP_FROM_DEFAULT),
        "subject": subject,
        "text": text_body,
        "html": html_body,
        "meta": {
            "studentName": student_name,
            "sessionMode": session_mode,
            "problemSlug": problem_slug,
            "problemName": problem_name,
            "turns": turns,
            "durationSec": duration_sec,
            "shortSession": bool(short_session),
        },
    }


async def fetch_followup_draft(session_id: str) -> dict:
    from bson import ObjectId
    db = get_db()
    proj = {
        "userEmail": 1, "studentName": 1, "title": 1, "headline": 1,
        "intent": 1, "metrics": 1, "durationSec": 1,
        "backendState.sessionMode": 1,
        "backendState.studentIntent": 1,
        "backendState.problemData": 1,
        "transcript": {"$slice": 30},
    }
    s = None
    try:
        s = await db.sessions.find_one({"_id": ObjectId(session_id)}, proj)
    except Exception:
        pass
    if not s:
        s = await db.sessions.find_one({"sessionId": session_id}, proj)
    if not s:
        return {"error": "session not found"}
    draft = _build_followup_draft(s)
    return draft


async def log_followup_send(payload: dict) -> None:
    """Persist a record of follow-ups so we don't double-email a student."""
    db = get_db()
    try:
        await db.followup_emails.insert_one(payload)
    except Exception as e:
        sys.stderr.write(f"  [followup] log insert failed: {e}\n")
        sys.stderr.flush()


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _build_session_brief(s: dict) -> str:
    """Compact, model-friendly description of a single session for AI prompts."""
    bs = s.get("backendState") or {}
    intent = s.get("intent") or {}
    intent_raw = intent.get("raw", "") if isinstance(intent, dict) else str(intent)
    pd = bs.get("problemData") if isinstance(bs.get("problemData"), dict) else {}
    metrics = s.get("metrics") if isinstance(s.get("metrics"), dict) else {}
    transcript = s.get("transcript") or []

    user_lines: list[str] = []
    for turn in transcript:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role", turn.get("speaker", ""))).lower()
        if role not in ("user", "student"):
            continue
        line = _flatten_message_content(
            turn.get("content", turn.get("text", turn.get("message", ""))),
            cap=400,
        )
        if line and not line.startswith("[SYSTEM]"):
            user_lines.append(line[:400])

    duration_sec = s.get("durationSec") or 0
    turns = metrics.get("totalTurns") or 0

    lines = [
        f"Student name: {s.get('studentName') or '(unknown)'}",
        f"Email: {s.get('userEmail') or '(unknown)'}",
        f"Topic / title: {_shorten_text(s.get('title') or s.get('headline') or '', 240)}",
        f"Initial intent (raw): {_shorten_text(intent_raw, 600)}",
        f"Backend session mode: {bs.get('sessionMode') or 'general'}",
        f"Problem name: {pd.get('name') or ''}",
        f"Problem slug: {pd.get('slug') or ''}",
        f"Difficulty: {pd.get('difficulty') or ''}",
        f"Turns: {turns}",
        f"Duration (sec): {duration_sec}",
        f"Status: {s.get('status') or '?'}",
    ]
    if user_lines:
        joined = "\n".join(f"  - {ln}" for ln in user_lines[:8])
        lines.append("Recent user messages (oldest first):\n" + joined)
    return "\n".join(lines)


def _ai_compose_email(session_brief: str, instruction: str = "",
                      current_subject: str = "", current_body: str = "") -> dict:
    """Call OpenRouter to generate or refine a follow-up email.

    Returns: { ok: bool, subject?: str, text?: str, error?: str }
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY not set in backend/.env"}
    model = os.environ.get("FOLLOWUP_MODEL") or os.environ.get("TUTOR_MODEL") \
        or "anthropic/claude-sonnet-4"

    system = (
        "You are a thoughtful product founder writing a personal follow-up email "
        "to a student who used myprofessor.live (an AI tutor product). "
        "Goals: be warm, specific (cite what they actually said/did when known), "
        "short (5-9 sentences), no marketing fluff, no emojis. Ask one focused "
        "question about why the session was short or unsatisfying, and offer a "
        "free redo. Sign off as 'The myprofessor.live team'.\n\n"
        "Return ONLY valid JSON of the form:\n"
        "{\"subject\": \"...\", \"text\": \"plain text body, with \\n line breaks\"}\n"
        "No other text outside the JSON object."
    )
    if instruction or current_body:
        user_prompt = (
            "Refine the existing email below using the operator's instruction. "
            "Keep it grounded in the session evidence; do not invent facts.\n\n"
            f"Session evidence:\n{session_brief}\n\n"
            f"Operator instruction (apply this):\n{instruction or '(no extra instruction)'}\n\n"
            f"Current subject:\n{current_subject}\n\n"
            f"Current body:\n{current_body}\n"
        )
    else:
        user_prompt = (
            "Write the first draft of the follow-up email based on this session evidence. "
            "If the session was very short (a couple of turns or under 3 min), tone is "
            "apologetic and curious about why. If it was longer, tone is grateful and "
            "asks for one piece of feedback.\n\n"
            f"Session evidence:\n{session_brief}\n"
        )

    payload = {
        "model": model,
        "max_tokens": 900,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }

    import urllib.request as _ur
    import urllib.error as _ue
    body = json.dumps(payload).encode("utf-8")
    req = _ur.Request(
        OPENROUTER_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://myprofessor.live/admin",
            "X-Title": "myprofessor.live admin",
        },
    )
    try:
        with _ur.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except _ue.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        return {"ok": False, "error": f"OpenRouter HTTP {e.code}: {err_body[:400]}"}
    except Exception as e:
        return {"ok": False, "error": f"OpenRouter call failed: {e}"}

    try:
        data = json.loads(raw)
    except Exception:
        return {"ok": False, "error": f"OpenRouter returned non-JSON: {raw[:300]}"}

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "error": f"OpenRouter response missing content: {str(data)[:400]}"}

    content = (content or "").strip()
    # Strip ```json ... ``` fences if the model added them.
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    parsed = None
    try:
        parsed = json.loads(content)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", content)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None

    if not isinstance(parsed, dict):
        return {"ok": False, "error": "AI response was not parseable JSON",
                "raw": content[:600]}

    subject = (parsed.get("subject") or "").strip()
    text = (parsed.get("text") or parsed.get("body") or "").strip()
    if not subject or not text:
        return {"ok": False, "error": "AI response missing subject or text"}
    return {"ok": True, "subject": subject, "text": text, "model": model}


async def fetch_ai_followup(session_id: str, instruction: str = "",
                            current_subject: str = "",
                            current_body: str = "") -> dict:
    from bson import ObjectId
    db = get_db()
    proj = {
        "userEmail": 1, "studentName": 1, "title": 1, "headline": 1,
        "intent": 1, "metrics": 1, "durationSec": 1, "status": 1,
        "backendState.sessionMode": 1,
        "backendState.studentIntent": 1,
        "backendState.problemData": 1,
        "transcript": {"$slice": 30},
    }
    s = None
    try:
        s = await db.sessions.find_one({"_id": ObjectId(session_id)}, proj)
    except Exception:
        pass
    if not s:
        s = await db.sessions.find_one({"sessionId": session_id}, proj)
    if not s:
        return {"ok": False, "error": "session not found"}

    brief = _build_session_brief(s)

    # Run the blocking HTTP call in a thread so the event loop is not stuck.
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _ai_compose_email(
            brief,
            instruction=instruction,
            current_subject=current_subject,
            current_body=current_body,
        ),
    )
    if result.get("ok"):
        result["to"] = (s.get("userEmail") or "").strip()
        result["fromEmail"] = os.environ.get("FOLLOWUP_FROM", FOLLOWUP_FROM_DEFAULT)
    return result


def send_followup_email(to: str, subject: str, html: str, text: str,
                        from_email: str | None = None,
                        reply_to: str | None = None) -> dict:
    """Send via Resend HTTP API using stdlib only. Runs in a worker thread."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "RESEND_API_KEY not set in backend/.env"}
    if not to or "@" not in to:
        return {"ok": False, "error": "Invalid recipient address"}
    if not subject or not (text or html):
        return {"ok": False, "error": "Subject and body are required"}

    payload = {
        "from": from_email or os.environ.get("FOLLOWUP_FROM", FOLLOWUP_FROM_DEFAULT),
        "to": [to],
        "subject": subject,
        "html": html or f"<pre>{text}</pre>",
        "text": text or "",
    }
    if reply_to:
        payload["reply_to"] = reply_to

    import urllib.request as _ur
    import urllib.error as _ue
    body = json.dumps(payload).encode("utf-8")
    req = _ur.Request(
        RESEND_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with _ur.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except Exception:
                data = {"raw": raw}
            return {"ok": True, "status": resp.status, "data": data}
    except _ue.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        return {"ok": False, "error": f"Resend HTTP {e.code}: {err_body[:400]}"}
    except Exception as e:
        return {"ok": False, "error": f"Resend send failed: {e}"}


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
    allow_reuse_address = True


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "EulerAdmin/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("DASHBOARD_ACCESS_LOG") != "1":
            return
        try:
            line = fmt % args if args else fmt
        except Exception:
            line = str(fmt)
        sys.stderr.write(f"  [access] {line}\n")
        sys.stderr.flush()

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
        # Normalize: empty or "/" -> "/", "/dashboard" stays; avoids missing "/" edge cases
        raw = parsed.path or "/"
        if not raw.startswith("/"):
            raw = "/" + raw
        path = raw.rstrip("/") or "/"

        try:
            if path in ("/", "/dashboard"):
                self._html(DASHBOARD_HTML)
            elif path.startswith("/replay/"):
                self._html(REPLAY_HTML)
            elif path == "/api/stats":
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or "")
                self._json(run_async(fetch_stats(qs)))
            elif path == "/api/users":
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or "")
                self._json(run_async(fetch_users(qs)))
            elif path == "/api/sessions":
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or "")
                limit = max(1, min(200, int((qs.get("limit") or ["50"])[0])))
                offset = max(0, int((qs.get("offset") or ["0"])[0]))
                q = (qs.get("q") or [""])[0]
                self._json(run_async(fetch_sessions(limit=limit, offset=offset, q=q, qs=qs)))
            elif path == "/api/analytics":
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query or "")
                days = int((qs.get("days") or ["30"])[0])
                self._json(run_async(fetch_analytics(days, qs)))
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
            elif path.startswith("/api/followup/draft/"):
                sid = path.split("/api/followup/draft/", 1)[1]
                self._json(run_async(fetch_followup_draft(sid)))
            else:
                self._json({"error": "Not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        raw = parsed.path or "/"
        if not raw.startswith("/"):
            raw = "/" + raw
        path = raw.rstrip("/") or "/"
        try:
            length = int(self.headers.get("Content-Length") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except Exception:
                self._json({"error": "Invalid JSON body"}, 400)
                return

            if path == "/api/followup/ai-compose":
                session_id = (payload.get("sessionId") or "").strip()
                instruction = payload.get("instruction") or ""
                current_subject = payload.get("currentSubject") or ""
                current_body = payload.get("currentBody") or ""
                if not session_id:
                    self._json({"error": "sessionId is required"}, 400)
                    return
                result = run_async(fetch_ai_followup(
                    session_id=session_id,
                    instruction=instruction,
                    current_subject=current_subject,
                    current_body=current_body,
                ))
                if result.get("ok"):
                    self._json({
                        "subject": result.get("subject", ""),
                        "text": result.get("text", ""),
                        "to": result.get("to", ""),
                        "fromEmail": result.get("fromEmail", ""),
                        "model": result.get("model", ""),
                    }, 200)
                else:
                    self._json({"error": result.get("error", "AI compose failed"),
                                "raw": result.get("raw", "")}, 500)
            elif path == "/api/followup/send":
                to = (payload.get("to") or "").strip()
                subject = (payload.get("subject") or "").strip()
                html = payload.get("html") or ""
                text = payload.get("text") or ""
                from_email = (payload.get("fromEmail") or "").strip() or None
                reply_to = (payload.get("replyTo") or "").strip() or None
                session_id = (payload.get("sessionId") or "").strip()

                # Resend call is a blocking HTTP request; run it in a worker
                # thread so we do not stall the event loop.
                result = send_followup_email(
                    to=to,
                    subject=subject,
                    html=html,
                    text=text,
                    from_email=from_email,
                    reply_to=reply_to,
                )
                if result.get("ok"):
                    log_payload = {
                        "sessionId": session_id,
                        "to": to,
                        "subject": subject,
                        "fromEmail": from_email or os.environ.get("FOLLOWUP_FROM", FOLLOWUP_FROM_DEFAULT),
                        "resendId": (result.get("data") or {}).get("id"),
                        "sentAt": datetime.now(timezone.utc),
                    }
                    try:
                        run_async(log_followup_send(log_payload))
                    except Exception:
                        pass
                    self._json({"status": "sent",
                                "id": (result.get("data") or {}).get("id")}, 200)
                else:
                    self._json({"status": "error", "error": result.get("error", "send failed")}, 500)
            else:
                self._json({"error": "Not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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

  .session-title-link { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                        overflow: hidden; text-overflow: ellipsis; max-width: 380px;
                        word-break: break-word; }
  td:has(.session-title-link) { max-width: 400px; }
  .modal-header h3 { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
                     overflow: hidden; word-break: break-word; max-width: 100%; }
  .row-tags { display: flex; flex-wrap: wrap; gap: 4px; margin: 4px 0 2px 0; }
  .row-tags > span { font-size: 10px; padding: 1px 6px; border-radius: 10px; line-height: 1.5;
                     font-family: 'SF Mono', Monaco, monospace; }
  .mode-tag { background: rgba(124, 92, 255, 0.18); color: var(--accent2); border: 1px solid rgba(124, 92, 255, 0.35); }
  .mode-tag.mode-mock { background: rgba(255, 122, 89, 0.18); color: #ff9b78; border-color: rgba(255, 122, 89, 0.35); }
  .mode-tag.mode-dsa { background: rgba(46, 204, 113, 0.18); color: #4ee390; border-color: rgba(46, 204, 113, 0.35); }
  .mode-tag.mode-systemdesign,
  .mode-tag.mode-system_design,
  .mode-tag.mode-sd { background: rgba(255, 196, 0, 0.16); color: #f5c44a; border-color: rgba(255, 196, 0, 0.35); }
  .prob-tag { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }
  .diff-tag { background: var(--surface2); color: var(--text2); border: 1px solid var(--border); text-transform: lowercase; }
  .diff-tag.diff-easy { color: #4ee390; border-color: rgba(46, 204, 113, 0.4); }
  .diff-tag.diff-medium { color: #f5c44a; border-color: rgba(255, 196, 0, 0.45); }
  .diff-tag.diff-hard { color: #ff7a59; border-color: rgba(255, 122, 89, 0.45); }
  .entry-tag { font-weight: 600; letter-spacing: .4px; }
  .entry-tag.entry-path { background: rgba(124, 92, 255, 0.22); color: #b8a4ff;
                          border: 1px solid rgba(124, 92, 255, 0.5); }
  .entry-tag.entry-single { background: rgba(160, 174, 192, 0.10); color: var(--text2);
                            border: 1px solid var(--border); }
  .path-line { font-size: 11px; color: var(--accent2); margin: 3px 0 2px 0;
               max-width: 480px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .path-line .path-title { font-weight: 500; }
  .path-line .path-node { color: var(--text2); }
  .user-said { color: var(--text2); font-size: 11px; line-height: 1.4; margin: 4px 0 4px 0; max-width: 360px;
               display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
               font-style: italic; }
  .replay-link { font-size: 10px; color: var(--accent2); text-decoration: none; display: inline-block; margin-top: 2px; }

  .insight-wrap { background: var(--surface2); border: 1px solid var(--border); border-radius: 10px;
                  padding: 14px 16px; margin-bottom: 18px; }
  .insight-wrap h4 { font-size: 11px; color: var(--accent2); text-transform: uppercase; letter-spacing: .5px;
                     margin: 14px 0 8px 0; }
  .insight-wrap h4:first-child { margin-top: 0; }
  .insight-wrap dl { display: grid; grid-template-columns: 140px 1fr; gap: 4px 12px; font-size: 12px; margin: 0; }
  .insight-wrap dt { color: var(--text2); }
  .insight-wrap dd { margin: 0; color: var(--text); word-break: break-word; }
  .insight-pre { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px;
                 font-size: 11px; line-height: 1.45; max-height: 280px; overflow: auto; white-space: pre-wrap;
                 font-family: 'SF Mono', Monaco, monospace; color: var(--text); }
  .insight-msg { border-left: 3px solid var(--border); padding: 6px 0 6px 10px; margin-bottom: 8px; font-size: 12px; }
  .insight-msg .r { font-size: 10px; color: var(--accent); text-transform: uppercase; margin-bottom: 4px; }

  .followup-bar { display: flex; gap: 8px; align-items: center; margin: 4px 0 14px 0; flex-wrap: wrap; }
  .followup-bar button { padding: 6px 12px; font-size: 12px; border-radius: 6px; cursor: pointer;
                         border: 1px solid var(--border); background: var(--surface2); color: var(--text); }
  .followup-bar button.primary { background: var(--accent); color: #0f1117; border-color: var(--accent);
                                 font-weight: 600; }
  .followup-bar button:disabled { opacity: 0.5; cursor: not-allowed; }
  .followup-panel { background: var(--surface2); border: 1px solid var(--border); border-radius: 10px;
                    padding: 14px 16px; margin-bottom: 18px; }
  .followup-panel h4 { font-size: 11px; color: var(--accent2); text-transform: uppercase; letter-spacing: .5px;
                       margin: 0 0 10px 0; }
  .followup-panel label { display: block; font-size: 11px; color: var(--text2); margin: 8px 0 4px 0;
                          text-transform: uppercase; letter-spacing: .4px; }
  .followup-panel input,
  .followup-panel textarea { width: 100%; background: var(--bg); border: 1px solid var(--border);
                              border-radius: 6px; color: var(--text); padding: 8px 10px; font-size: 13px;
                              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif; }
  .followup-panel textarea { font-family: 'SF Mono', Monaco, monospace; font-size: 12px; line-height: 1.5;
                              min-height: 220px; resize: vertical; }
  .followup-actions { display: flex; gap: 8px; margin-top: 12px; align-items: center; flex-wrap: wrap; }
  .followup-status { font-size: 12px; color: var(--text2); }
  .followup-status.ok { color: var(--green); }
  .followup-status.err { color: var(--red); }
  .followup-ai { margin-top: 14px; padding: 10px 12px; border: 1px dashed var(--border);
                 border-radius: 8px; background: rgba(124,92,255,0.04); }

  .email-filters { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
                   padding: 12px 16px; margin-bottom: 16px; }
  .email-filters .filter-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .email-filters .filter-input { position: relative; flex: 1 1 360px; min-width: 280px; }
  .email-filters .filter-input input { width: 100%; padding: 9px 36px 9px 36px; border-radius: 8px;
                         border: 1px solid var(--border); background: var(--surface2); color: var(--text);
                         font-size: 13px; font-family: 'SF Mono', Monaco, monospace; }
  .email-filters .filter-input input:focus { outline: none; border-color: var(--accent);
                         box-shadow: 0 0 0 2px rgba(124,92,255,0.18); }
  .email-filters .filter-input .icon { position: absolute; left: 11px; top: 50%; transform: translateY(-50%);
                         color: var(--text2); font-size: 14px; pointer-events: none; }
  .email-filters .filter-input .clear { position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
                         background: none; border: none; color: var(--text2); cursor: pointer;
                         font-size: 16px; padding: 4px 6px; line-height: 1; border-radius: 4px; display: none; }
  .email-filters .filter-input .clear:hover { background: var(--surface2); color: var(--text); }
  .email-filters .preset { font-size: 11px; padding: 6px 10px; border-radius: 999px;
                         background: var(--surface2); color: var(--text); border: 1px solid var(--border);
                         cursor: pointer; white-space: nowrap; }
  .email-filters .preset:hover { background: rgba(124,92,255,0.12); border-color: var(--accent);
                         color: var(--accent); }
  .email-filters .preset.active { background: rgba(124,92,255,0.2); color: var(--accent2);
                         border-color: var(--accent); }
  .email-filters .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;
                          align-items: center; min-height: 24px; }
  .email-filters .chip { font-size: 11px; padding: 3px 9px; border-radius: 999px;
                         font-family: 'SF Mono', Monaco, monospace; display: inline-flex;
                         align-items: center; gap: 6px; }
  .email-filters .chip.include { background: rgba(124,92,255,0.18); color: #b8a4ff;
                         border: 1px solid rgba(124,92,255,0.4); }
  .email-filters .chip.domain { background: rgba(64,200,170,0.18); color: #56e0ba;
                         border: 1px solid rgba(64,200,170,0.4); }
  .email-filters .chip.exclude { background: rgba(255,122,89,0.16); color: #ff9b78;
                         border: 1px solid rgba(255,122,89,0.4); }
  .email-filters .chip-x { cursor: pointer; opacity: .6; font-size: 13px; line-height: 1; }
  .email-filters .chip-x:hover { opacity: 1; }
  .email-filters .chip-empty { font-size: 11px; color: var(--text2); font-style: italic; }
  .email-filters .hint { font-size: 11px; color: var(--text2); line-height: 1.5; margin-top: 8px; }
  .email-filters .hint code { background: var(--surface2); padding: 1px 5px; border-radius: 3px;
                         font-size: 10.5px; }
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

  <div class="email-filters" id="emailFilters">
    <div class="row">
      <label>Email domain <input class="wide" type="text" id="filterDomain" placeholder="e.g. seekcapacity.com" autocomplete="off" /></label>
      <label>Contains <input type="text" id="filterEmailContains" placeholder="substring in email" autocomplete="off" /></label>
      <label>Exclude (comma-separated) <input class="wide" type="text" id="filterEmailExclude" placeholder="e.g. test.com, +noise+" autocomplete="off" /></label>
    </div>
    <div class="actions">
      <button type="button" onclick="applyEmailFilters()">Apply email filters</button>
      <button type="button" onclick="clearEmailFilters()" style="opacity:.85">Clear</button>
      <span class="pill" id="filterActivePill" style="display:none">Filtered</span>
    </div>
    <p class="hint">Example: domain <strong>gmail.com</strong> limits stats, users, sessions, and analytics to addresses ending in <strong>@gmail.com</strong>.
      Combine with <strong>Exclude</strong> <code>test.com, mayank@test.com</code> to drop internal addresses. Search box still filters the current table client-side (users) or server-side (sessions).</p>
  </div>

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
  const f = d.filters || {};
  const pill = document.getElementById('filterActivePill');
  if (pill) pill.style.display = f.active ? 'inline-block' : 'none';
  const pathSess = d.pathSessions || 0;
  const singleSess = d.singleSessions || 0;
  const pathUsers = d.pathUsers || 0;
  const pathsTotal = d.pathsTotal || 0;
  const pathSessPct = d.pathSessionsPct || 0;
  const pathUserPct = d.pathAdoptionPct || 0;
  document.getElementById('statsCards').innerHTML = `
    <div class="stat-card"><div class="label">Total Users</div><div class="value c1">${d.totalUsers}</div><div class="sub">${pathUsers} on a path · ${pathUserPct}%</div></div>
    <div class="stat-card"><div class="label">Total Sessions</div><div class="value c2">${d.totalSessions}</div><div class="sub">${pathSess} path · ${singleSess} single</div></div>
    <div class="stat-card"><div class="label">Paths Created</div><div class="value c3">${pathsTotal}</div><div class="sub">${d.pathsActive || 0} active · ${pathSessPct}% of sessions</div></div>
    <div class="stat-card"><div class="label">Active Sessions</div><div class="value c4">${d.activeSessions}</div><div class="sub">in progress now</div></div>
    <div class="stat-card"><div class="label">Total Spend</div><div class="value c5">${fmtCost(d.costAllCents, true)}</div><div class="sub">${llmPct}% LLM · ${ttsPct}% TTS</div></div>
    <div class="stat-card"><div class="label">This Month</div><div class="value c6">${fmtCost(d.costMonthCents, true)}</div><div class="sub">month to date</div></div>
    ${f.active ? `<div class="stat-card" style="grid-column:1/-1;max-width:none"><div class="label">Active email filter</div><div class="sub" style="margin-top:6px;font-size:12px;color:var(--text)">domain: <strong>${esc(f.domain || '(any)')}</strong> &middot; contains: <strong>${esc(f.email_contains || '(none)')}</strong> &middot; exclude: <strong>${esc(f.email_exclude || '(none)')}</strong></div></div>` : ''}
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
  const tagBits = [];
  if (s.entryType === 'path') {
    const pos = (s.nodeOrder && s.pathTotalNodes)
      ? (' ' + s.nodeOrder + '/' + s.pathTotalNodes)
      : '';
    const phase = s.nodePhase ? (' · P' + s.nodePhase) : '';
    const tip = 'Path: ' + (s.pathTitle || '?') +
      (s.nodeTitle ? ('  Session: ' + s.nodeTitle) : '');
    tagBits.push('<span class="entry-tag entry-path" title="' + esc(tip) + '">PATH' + pos + phase + '</span>');
  } else {
    tagBits.push('<span class="entry-tag entry-single" title="Started directly from chat / intent box (not from a path)">SINGLE</span>');
  }
  if (s.sessionMode && s.sessionMode !== 'general') {
    tagBits.push('<span class="mode-tag mode-' + esc(s.sessionMode) + '">' + esc(s.sessionMode) + '</span>');
  }
  if (s.problemSlug) {
    tagBits.push('<span class="prob-tag" title="DSA card / problem">' + esc(s.problemSlug) + '</span>');
  } else if (s.problemName) {
    tagBits.push('<span class="prob-tag" title="DSA card / problem">' + esc(s.problemName) + '</span>');
  }
  if (s.problemDifficulty) {
    tagBits.push('<span class="diff-tag diff-' + esc(s.problemDifficulty.toLowerCase()) + '">' + esc(s.problemDifficulty) + '</span>');
  }
  const tagsRow = tagBits.length ? '<div class="row-tags">' + tagBits.join('') + '</div>' : '';
  const pathLine = (s.entryType === 'path' && (s.pathTitle || s.nodeTitle))
    ? ('<div class="path-line" title="Click row to view path linkage">' +
        '<span class="path-title">\\u279C ' + esc(s.pathTitle || '(untitled path)') + '</span>' +
        (s.nodeTitle ? ('<span class="path-node"> &middot; ' + esc(s.nodeTitle) + '</span>') : '') +
       '</div>')
    : '';

  const userSnippet = s.firstUserMsg || s.studentIntent || s.intent || '';
  const userLine = userSnippet
    ? '<div class="user-said" title="What the student typed/said first">\\u201C' + esc(userSnippet) + '\\u201D</div>'
    : '';

  return `<tr>
  <td class="muted">${idx}</td>
  <td><span class="bold">${esc(s.user)}</span><br><span class="mono muted">${esc(s.email)}</span></td>
  <td><span class="link session-title-link" onclick="viewTranscript('${s._idx}')" title="${esc(s.titleFull || s.title || '')}">${esc(s.title)}</span>
      ${tagsRow}${pathLine}${userLine}
      <a class="mono muted replay-link" href="/replay/${s._id}" target="_blank" title="Open replay">&#9654; replay</a></td>
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
  // Sessions tab only: debounced server-side search (do not run while on other tabs — shared input would hide "latest" sessions)
  const activeTab = document.querySelector('.tabs button.active')?.dataset.tab;
  if (activeTab !== 'sessions') return;
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => {
    _sessionsPagination.query = getQ();
    loadSessions(true);
  }, 250);
}

function switchTab(tab) {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tab));
  if (tab === 'users') loadUsers();
  else if (tab === 'sessions') {
    // Sync shared search box → session query, then refetch (always fresh when opening this tab)
    _sessionsPagination.query = getQ();
    loadSessions(true);
  } else if (tab === 'analytics') loadAnalytics();
  else if (tab === 'feedback') loadFeedback();
}

// ── Analytics ──
let analyticsLoaded = false;
async function loadAnalytics(force) {
  if (analyticsLoaded && !force) return;
  try {
    const r = await fetch(mergeUrl('/api/analytics', new URLSearchParams({ days: '30' })));
    const a = await r.json();
    renderAnalytics(a);
    analyticsLoaded = true;
  } catch (e) {
    analyticsLoaded = false;
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
      <h3>Return rate <span class="hdr-sub">cohort \\u2192 returned</span></h3>
      <p class="desc">% of cohort who came back within the window. Cohort = had a session in
        an earlier window; returned = came back in the named window.</p>
      <div class="metric-row">
        <div class="m"><div class="n">${a.returnRate1d.rate}%</div><div class="l">1-day (${a.returnRate1d.returned}/${a.returnRate1d.cohort})</div></div>
        <div class="m"><div class="n c2">${(a.returnRate2d || {rate:0}).rate}%</div><div class="l">2-day (${(a.returnRate2d||{}).returned||0}/${(a.returnRate2d||{}).cohort||0})</div></div>
        <div class="m"><div class="n c3">${a.returnRate7d.rate}%</div><div class="l">7-day (${a.returnRate7d.returned}/${a.returnRate7d.cohort})</div></div>
        <div class="m"><div class="n c4">${a.returnRate30d.rate}%</div><div class="l">30-day (${a.returnRate30d.returned}/${a.returnRate30d.cohort})</div></div>
      </div>
    </div>

    <div class="chart-card">
      <h3>Engagement averages <span class="hdr-sub">last ${a.windowDays}d</span></h3>
      <p class="desc">Per-active-user and per-session figures. Active session length is
        based on the same active-period definition (15-min idle gap) used on the Users tab,
        so these reconcile.</p>
      <div class="metric-row">
        <div class="m"><div class="n">${a.avgSessionsPerUser || 0}</div><div class="l">Sessions / active user</div></div>
        <div class="m"><div class="n c2">${fmtDur(a.avgSessionActiveSec || 0)}</div><div class="l">Avg session length</div></div>
        <div class="m"><div class="n c3">${a.avgTurnsPerSession}</div><div class="l">Turns / session</div></div>
        <div class="m"><div class="n c4">${a.activeUsersWindow || 0}</div><div class="l">Active users</div></div>
      </div>
    </div>

    <div class="chart-card">
      <h3>Path adoption <span class="hdr-sub">last ${a.windowDays}d</span></h3>
      <p class="desc">How many sessions / active users came in via a path
        (Learn button on a path or subtopic) vs. starting a single session
        directly from the chat box.</p>
      <div class="metric-row">
        <div class="m"><div class="n">${(a.pathFunnel||{}).pathSessions||0}</div><div class="l">Path sessions (${(a.pathFunnel||{}).pathPctOfSessions||0}%)</div></div>
        <div class="m"><div class="n c2">${(a.pathFunnel||{}).singleSessions||0}</div><div class="l">Single sessions</div></div>
        <div class="m"><div class="n c3">${(a.pathFunnel||{}).pathUsers||0}</div><div class="l">Path users (${(a.pathFunnel||{}).pathPctOfUsers||0}%)</div></div>
        <div class="m"><div class="n c4">${(a.pathFunnel||{}).singleUsers||0}</div><div class="l">Single-only users</div></div>
      </div>
    </div>

    <div class="chart-card">
      <h3>Cost per session <span class="hdr-sub">last ${a.windowDays}d</span></h3>
      <div class="metric-row">
        <div class="m"><div class="n">${fmtCost(a.avgCostPerSessionCents)}</div><div class="l">Cost/session</div></div>
        <div class="m"><div class="n c2">${fmtCost(a.avgCostPerTurnCents)}</div><div class="l">Cost/turn</div></div>
        <div class="m"><div class="n c3">${fmtCost(a.totals.costCents)}</div><div class="l">Total spend</div></div>
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

function renderSessionInsight(detail) {
  const ins = detail && detail.sessionInsight;
  if (!ins || typeof ins !== 'object') return '';
  let h = '<div class="insight-wrap">';
  h += '<h4>Session insight</h4>';

  // Path linkage block — surfaces "where in the path is this session?"
  // Stakeholders need this to evaluate whether path students complete
  // their plan vs. drop off mid-way.
  const pc = ins.pathContext;
  if (pc && typeof pc === 'object' && pc.pathId) {
    const pos = (pc.currentNodeOrder && pc.totalNodes)
      ? ('Session ' + pc.currentNodeOrder + ' of ' + pc.totalNodes)
      : '';
    const phase = pc.currentNodePhase ? ('Phase ' + pc.currentNodePhase) : '';
    const meta = [pos, phase].filter(Boolean).join(' &middot; ');
    const topics = (pc.currentNodeTopics || []).slice(0, 8)
      .map(t => esc(typeof t === 'string' ? t : (t && t.title) || ''))
      .filter(x => x).join(', ');
    h += '<div style="background:rgba(124,92,255,0.10);border:1px solid rgba(124,92,255,0.35);' +
         'border-radius:8px;padding:12px 14px;margin:0 0 14px 0">' +
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">' +
        '<span class="entry-tag entry-path">PATH</span>' +
        '<strong style="font-size:13px">' + esc(pc.pathTitle || '(untitled path)') + '</strong>' +
      '</div>' +
      (meta ? '<div style="color:var(--text2);font-size:11px;margin-bottom:6px">' + meta + '</div>' : '') +
      (pc.currentNodeTitle ? ('<div style="font-size:13px;margin:6px 0"><strong>' +
        esc(pc.currentNodeTitle) + '</strong>' +
        (pc.currentNodeStatus ? (' <span class="muted sm">(' + esc(pc.currentNodeStatus) + ')</span>') : '') +
        '</div>') : '') +
      (topics ? ('<div style="font-size:12px;color:var(--text2);margin:4px 0"><strong>Topics:</strong> ' +
        topics + '</div>') : '') +
      (pc.currentNodeStudentNote ? ('<div style="font-size:12px;color:var(--text2);margin:4px 0;font-style:italic">' +
        '<strong>Student note:</strong> \\u201C' + esc(pc.currentNodeStudentNote) + '\\u201D</div>') : '') +
      '<div style="font-size:11px;color:var(--text2);margin-top:8px">' +
        'Path progress: ' + (pc.completedNodes || 0) + '/' + (pc.totalNodes || 0) +
        ' nodes complete (' + (pc.completedPct || 0) + '%) &middot; status: ' +
        esc(pc.pathStatus || 'unknown') +
      '</div>' +
      '<div style="font-size:10px;color:var(--text2);margin-top:6px;font-family:\\'SF Mono\\',monospace">' +
        'pathId=' + esc(pc.pathId) + ' &middot; nodeId=' + esc(pc.currentNodeId || '') +
      '</div>' +
    '</div>';
  } else if (ins.entryType === 'single') {
    h += '<div style="margin:0 0 12px 0">' +
      '<span class="entry-tag entry-single">SINGLE SESSION</span> ' +
      '<span class="muted sm" style="margin-left:6px">Started directly from chat / intent box (no path).</span>' +
    '</div>';
  }

  if (ins.intentRaw) {
    h += '<p style="margin:0 0 10px 0;font-size:13px;line-height:1.45"><strong>Initial intent:</strong> ' +
      esc(String(ins.intentRaw)) + '</p>';
  }
  if (ins.studentIntent) {
    h += '<p style="margin:0 0 10px 0;font-size:13px;line-height:1.45"><strong>Student intent (backend):</strong> ' +
      esc(String(ins.studentIntent)) + '</p>';
  }
  const metaBits = [];
  if (ins.headline) metaBits.push(['Headline', ins.headline]);
  if (ins.backendSessionMode) metaBits.push(['Session mode', ins.backendSessionMode]);
  if (ins.sessionTeachingMode) metaBits.push(['Teaching mode', ins.sessionTeachingMode]);
  if (ins.sessionStatus) metaBits.push(['Status', ins.sessionStatus]);
  if (ins.phase !== undefined && ins.phase !== null && ins.phase !== '') {
    metaBits.push(['Phase', ins.phase]);
  }
  if (metaBits.length) {
    h += '<h4>Session meta</h4><dl>';
    for (const [k, v] of metaBits) {
      h += '<dt>' + esc(k) + '</dt><dd>' + esc(String(v)) + '</dd>';
    }
    h += '</dl>';
  }
  const bp = ins.blueprint;
  if (bp && typeof bp === 'object' && Object.keys(bp).length) {
    h += '<h4>Blueprint / mode</h4><dl>';
    for (const k of Object.keys(bp)) {
      const v = bp[k];
      if (v === undefined || v === null || v === '') continue;
      h += '<dt>' + esc(k) + '</dt><dd>' + esc(String(v)) + '</dd>';
    }
    h += '</dl>';
  }
  const pd = ins.problemData;
  if (pd && typeof pd === 'object' && Object.keys(pd).length) {
    h += '<h4>Problem / DSA selection</h4><dl>';
    for (const k of Object.keys(pd)) {
      const v = pd[k];
      if (v === undefined || v === null || v === '') continue;
      h += '<dt>' + esc(k) + '</dt><dd>' + esc(String(v)) + '</dd>';
    }
    h += '</dl>';
  }
  const mock = ins.mock;
  if (mock && typeof mock === 'object') {
    const mk = Object.keys(mock).filter((k) => mock[k] !== undefined && mock[k] !== null && mock[k] !== '');
    if (mk.length) {
      h += '<h4>Mock interview</h4><dl>';
      for (const k of mk) {
        h += '<dt>' + esc(k) + '</dt><dd>' + esc(String(mock[k])) + '</dd>';
      }
      h += '</dl>';
    }
  }
  const cc = ins.codeCanvas;
  if (cc && typeof cc === 'object' && (cc.hasCodeState || cc.hasCanvasState)) {
    h += '<h4>Workspace flags</h4><dl>' +
      '<dt>Code state</dt><dd>' + (cc.hasCodeState ? 'yes' : 'no') + '</dd>' +
      '<dt>Canvas state</dt><dd>' + (cc.hasCanvasState ? 'yes' : 'no') + '</dd></dl>';
  }
  if (ins.dsaState && typeof ins.dsaState === 'object' && Object.keys(ins.dsaState).length) {
    h += '<h4>DSA workspace (sanitized)</h4><pre class="insight-pre">' +
      esc(JSON.stringify(ins.dsaState, null, 2)) + '</pre>';
  }
  const ru = ins.recentUserInputs;
  if (Array.isArray(ru) && ru.length) {
    h += '<h4>Recent user inputs (transcript)</h4><ul style="margin:0;padding-left:18px;font-size:12px;line-height:1.5">';
    for (const line of ru) {
      h += '<li>' + esc(String(line)) + '</li>';
    }
    h += '</ul>';
  }
  const tail = ins.serverMessageTail;
  if (Array.isArray(tail) && tail.length) {
    h += '<h4>Server message tail (backendState)</h4>';
    for (const m of tail) {
      const role = m && m.role ? String(m.role) : '?';
      const content = m && m.content != null ? String(m.content) : '';
      h += '<div class="insight-msg"><div class="r">' + esc(role) + '</div><div>' + esc(content) + '</div></div>';
    }
  }
  const metrics = ins.metrics;
  if (metrics && typeof metrics === 'object' && Object.keys(metrics).length) {
    h += '<h4>Session metrics</h4><pre class="insight-pre" style="max-height:200px">' +
      esc(JSON.stringify(metrics, null, 2)) + '</pre>';
  }
  h += '</div>';
  const mk = '<h4>Session insight</h4>';
  const p0 = h.indexOf(mk);
  const pos = p0 < 0 ? 0 : p0 + mk.length;
  const ix = h.lastIndexOf('</div>');
  const body = ix > pos ? h.slice(pos, ix).trim() : '';
  if (!body) return '';
  return h;
}

let _activeSession = null;

function _followupBar(s) {
  const to = (s && s.email) ? s.email : '';
  const disabled = to ? '' : 'disabled title="No email on file"';
  return '<div class="followup-bar">' +
    '<button class="primary" ' + disabled + ' onclick="composeFollowup(\\'' + s._id + '\\')">' +
      '\\u2709 Compose follow-up email</button>' +
    (to ? '<span class="muted sm">to <span class="mono">' + esc(to) + '</span></span>' : '') +
    '<span id="followupStatus" class="followup-status"></span>' +
    '</div>' +
    '<div id="followupPanel"></div>';
}

async function composeFollowup(sessionId) {
  const status = document.getElementById('followupStatus');
  const panel = document.getElementById('followupPanel');
  if (!panel) return;
  if (status) { status.className = 'followup-status'; status.textContent = 'Drafting...'; }
  panel.innerHTML = '';
  try {
    const resp = await fetch(API + '/api/followup/draft/' + encodeURIComponent(sessionId));
    const d = await resp.json();
    if (!resp.ok || d.error) {
      if (status) { status.className = 'followup-status err'; status.textContent = d.error || 'Could not load draft'; }
      return;
    }
    panel.innerHTML =
      '<div class="followup-panel">' +
        '<h4>Follow-up email</h4>' +
        '<label>To</label>' +
        '<input id="fuTo" type="email" value="' + esc(d.to || '') + '" />' +
        '<label>From</label>' +
        '<input id="fuFrom" type="text" value="' + esc(d.fromEmail || '') + '" />' +
        '<label>Subject</label>' +
        '<input id="fuSubject" type="text" value="' + esc(d.subject || '') + '" />' +
        '<label>Body (plain text)</label>' +
        '<textarea id="fuText">' + esc(d.text || '') + '</textarea>' +
        '<div class="followup-ai">' +
          '<label>Refine with AI <span class="muted sm">(optional instruction, e.g. "shorter, less corporate, mention voice issue")</span></label>' +
          '<textarea id="fuInstr" placeholder="Type how the email should change, then click Refine. Leave empty + click Generate for a fresh AI draft." style="min-height:60px"></textarea>' +
          '<div class="followup-actions">' +
            '<button onclick="aiCompose(\\'' + sessionId + '\\', false)">\\u2728 Generate with AI</button>' +
            '<button onclick="aiCompose(\\'' + sessionId + '\\', true)">\\u21bb Refine with AI</button>' +
            '<span id="fuAiStatus" class="followup-status"></span>' +
          '</div>' +
        '</div>' +
        '<div class="followup-actions">' +
          '<button class="primary" onclick="sendFollowup(\\'' + sessionId + '\\')">Send via Resend</button>' +
          '<button onclick="document.getElementById(\\'followupPanel\\').innerHTML=\\'\\'">Cancel</button>' +
          '<span id="fuSendStatus" class="followup-status"></span>' +
        '</div>' +
      '</div>';
    if (status) status.textContent = '';
  } catch (e) {
    if (status) { status.className = 'followup-status err'; status.textContent = 'Draft failed: ' + e; }
  }
}

async function aiCompose(sessionId, useCurrent) {
  const st = document.getElementById('fuAiStatus');
  const subjectEl = document.getElementById('fuSubject');
  const textEl = document.getElementById('fuText');
  const instrEl = document.getElementById('fuInstr');
  const instruction = (instrEl && instrEl.value || '').trim();
  if (st) { st.className = 'followup-status'; st.textContent = 'Asking the model\\u2026'; }
  try {
    const body = {
      sessionId,
      instruction: useCurrent ? instruction : '',
      currentSubject: useCurrent ? (subjectEl ? subjectEl.value : '') : '',
      currentBody: useCurrent ? (textEl ? textEl.value : '') : '',
    };
    const resp = await fetch(API + '/api/followup/ai-compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const d = await resp.json();
    if (!resp.ok || d.error) {
      if (st) { st.className = 'followup-status err';
                st.textContent = 'AI failed: ' + (d.error || ('HTTP ' + resp.status)); }
      return;
    }
    if (subjectEl && d.subject) subjectEl.value = d.subject;
    if (textEl && d.text) textEl.value = d.text;
    if (st) {
      st.className = 'followup-status ok';
      const tag = useCurrent ? 'Refined' : 'Generated';
      st.textContent = '\\u2713 ' + tag + (d.model ? ' (' + d.model + ')' : '') +
                       '. Review, edit if needed, then send.';
    }
  } catch (e) {
    if (st) { st.className = 'followup-status err'; st.textContent = 'AI failed: ' + e; }
  }
}

async function sendFollowup(sessionId) {
  const to = (document.getElementById('fuTo') || {}).value || '';
  const fromEmail = (document.getElementById('fuFrom') || {}).value || '';
  const subject = (document.getElementById('fuSubject') || {}).value || '';
  const text = (document.getElementById('fuText') || {}).value || '';
  const st = document.getElementById('fuSendStatus');
  if (!to.trim() || !subject.trim() || !text.trim()) {
    if (st) { st.className = 'followup-status err'; st.textContent = 'To, subject and body are required.'; }
    return;
  }
  if (!confirm('Send this follow-up to ' + to + '?')) return;
  if (st) { st.className = 'followup-status'; st.textContent = 'Sending...'; }
  // Convert plain text to lightweight HTML (paragraphs from blank lines).
  const html = text.split(/\\n\\s*\\n/).map(function (p) {
    return '<p>' + esc(p).replace(/\\n/g, '<br>') + '</p>';
  }).join('');
  try {
    const resp = await fetch(API + '/api/followup/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, to, subject, text, html, fromEmail }),
    });
    const d = await resp.json();
    if (resp.ok && d.status === 'sent') {
      if (st) { st.className = 'followup-status ok';
                st.textContent = '\\u2713 Sent (id ' + (d.id || 'ok') + ').'; }
    } else {
      if (st) { st.className = 'followup-status err';
                st.textContent = 'Send failed: ' + (d.error || ('HTTP ' + resp.status)); }
    }
  } catch (e) {
    if (st) { st.className = 'followup-status err'; st.textContent = 'Send failed: ' + e; }
  }
}

function _trimTitle(t, n) {
  if (!t) return '';
  const s = String(t).replace(/\\s+/g, ' ').trim();
  return s.length <= n ? s : s.slice(0, n - 1) + '\\u2026';
}

async function viewTranscript(idx) {
  const s = sessionsData[idx];
  if (!s || !s._id) return;
  _activeSession = s;
  const titleShort = _trimTitle(s.title || 'Session', 160);
  const fullTitle = (s.titleFull || s.title || '').replace(/"/g, '\\u201D');
  const title = (s.user || '?') + ' \\u2014 ' + titleShort;
  const costStr = (s.costCents && s.costCents > 0)
    ? ' | ' + fmtCost(s.costCents) + ' (' + fmtCost(s.llmCents) + ' LLM, ' + fmtCost(s.ttsCents) + ' TTS)'
    : '';
  const subtitle = 'Active: ' + fmtDur(s.activeSec) + ' | Span: ' + fmtDur(s.spanSec) + ' | ' + s.turns + ' turns' + costStr;
  const titleEl = document.getElementById('modalTitle');
  titleEl.innerHTML = esc(title) + '<br><span class="muted sm">' + subtitle + '</span>';
  if (fullTitle && fullTitle.length > titleShort.length) {
    titleEl.setAttribute('title', fullTitle);
  } else {
    titleEl.removeAttribute('title');
  }
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
    const insightHtml = renderSessionInsight(detail || {});
    let html = _followupBar(s);
    if (detail && detail.error) {
      html += '<p style="color:var(--amber);font-size:12px;margin-bottom:10px">Session detail: ' +
        esc(String(detail.error)) + ' (transcript may still load).</p>';
    }
    html += insightHtml;
    if (!turns.length && !insightHtml && !(detail && detail.error)) {
      document.getElementById('modalBody').innerHTML = html +
        '<p class="muted">No transcript or session insight for this session.</p>';
      return;
    }
    if (!turns.length) {
      html += '<p class="muted" style="margin:0 0 12px 0">No transcript rows stored for this session.</p>';
    }
    if (turns.length) {
      html += '<h4 style="font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin:18px 0 8px 0">Transcript</h4>';
    }
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

function emailFilterParams() {
  const p = new URLSearchParams();
  const d = (document.getElementById('filterDomain')?.value || '').trim();
  if (d) p.set('domain', d);
  const c = (document.getElementById('filterEmailContains')?.value || '').trim();
  if (c) p.set('email_contains', c);
  const e = (document.getElementById('filterEmailExclude')?.value || '').trim();
  if (e) p.set('email_exclude', e);
  return p;
}

function mergeUrl(path, baseParams) {
  const p = baseParams ? new URLSearchParams(baseParams) : new URLSearchParams();
  emailFilterParams().forEach((v, k) => p.set(k, v));
  const q = p.toString();
  return API + path + (q ? '?' + q : '');
}

function applyEmailFilters() {
  analyticsLoaded = false;
  _sessionsPagination.offset = 0;
  sessionsData = [];
  refreshAll().then(() => {
    const tab = document.querySelector('.tabs button.active')?.dataset.tab;
    if (tab === 'analytics') loadAnalytics(true);
    if (tab === 'sessions') loadSessions(true);
  });
}

function clearEmailFilters() {
  ['filterDomain', 'filterEmailContains', 'filterEmailExclude'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  applyEmailFilters();
}

// On first load: fetch only stats + the active tab's data (lazy)
async function refreshAll() {
  const t0 = performance.now();
  document.getElementById('statusBar').textContent = 'refreshing...';
  try {
    // Stats card always loads (cheap)
    const sr = await fetch(mergeUrl('/api/stats'));
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
  const t0 = performance.now();
  try {
    const r = await fetch(mergeUrl('/api/users'));
    usersData = await r.json();
    renderUsers();
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
  const base = new URLSearchParams();
  base.set('limit', String(p.limit));
  base.set('offset', String(p.offset));
  if (p.query) base.set('q', p.query);
  const url = mergeUrl('/api/sessions', base);
  try {
    const r = await fetch(url);
    const data = await r.json();
    const items = (data.items || []).map((s, i) => ({ ...s, _idx: sessionsData.length + i }));
    sessionsData = sessionsData.concat(items);
    _sessionsPagination.total = data.total || sessionsData.length;
    _sessionsPagination.hasMore = !!data.hasMore;
    _sessionsPagination.offset += items.length;
    renderSessions();
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
  .top-bar .title { font-weight: 700; font-size: 15px; flex: 1; min-width: 0;
                    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                    overflow: hidden; text-overflow: ellipsis; word-break: break-word;
                    line-height: 1.35; }
  .top-bar .meta { font-size: 12px; color: var(--text2); white-space: nowrap; }
  .top-bar .email-btn { padding: 6px 12px; border-radius: 6px; font-size: 12px;
                        cursor: pointer; background: var(--accent); color: #0f1117;
                        border: 1px solid var(--accent); font-weight: 600; }
  .top-bar .email-btn:hover { opacity: 0.9; }

  .email-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); z-index: 50;
                   display: none; align-items: flex-start; justify-content: center;
                   padding: 40px 16px; overflow-y: auto; }
  .email-overlay.show { display: flex; }
  .email-card { width: min(720px, 100%); background: var(--surface); border: 1px solid var(--border);
                border-radius: 12px; padding: 18px 22px; color: var(--text); }
  .email-card h3 { font-size: 16px; margin-bottom: 12px; color: var(--accent); }
  .email-card label { display: block; font-size: 11px; color: var(--text2);
                      text-transform: uppercase; letter-spacing: .4px; margin: 10px 0 4px 0; }
  .email-card input, .email-card textarea { width: 100%; background: var(--bg);
      border: 1px solid var(--border); border-radius: 6px; color: var(--text);
      padding: 8px 10px; font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif; }
  .email-card textarea { font-family: 'SF Mono', Monaco, monospace; font-size: 12px;
                         line-height: 1.5; min-height: 200px; resize: vertical; }
  .email-card .actions { display: flex; gap: 8px; margin-top: 14px; align-items: center; flex-wrap: wrap; }
  .email-card .actions button { padding: 7px 14px; font-size: 12px; border-radius: 6px;
      cursor: pointer; border: 1px solid var(--border); background: var(--surface2); color: var(--text); }
  .email-card .actions button.primary { background: var(--accent); color: #0f1117;
                                        border-color: var(--accent); font-weight: 600; }
  .email-card .ai-box { margin-top: 12px; padding: 10px 12px; border: 1px dashed var(--border);
                        border-radius: 8px; background: rgba(124,92,255,0.05); }
  .email-card .status { font-size: 12px; color: var(--text2); }
  .email-card .status.ok { color: var(--green); }
  .email-card .status.err { color: var(--red); }

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
  <button class="email-btn" id="emailBtn" onclick="openEmail()" title="Compose follow-up email">
    &#9993; Email student
  </button>
  <div class="meta" id="replayMeta"></div>
</div>

<div class="email-overlay" id="emailOverlay" onclick="if(event.target===this)closeEmail()">
  <div class="email-card">
    <h3>Follow-up email</h3>
    <label>To</label>
    <input id="emTo" type="email" />
    <label>From</label>
    <input id="emFrom" type="text" />
    <label>Subject</label>
    <input id="emSubject" type="text" />
    <label>Body (plain text)</label>
    <textarea id="emText"></textarea>
    <div class="ai-box">
      <label>Refine with AI <span style="text-transform:none;color:var(--text2);font-size:11px">(optional instruction)</span></label>
      <textarea id="emInstr" placeholder='e.g. "shorter, less corporate, mention voice issue"' style="min-height:60px"></textarea>
      <div class="actions">
        <button onclick="emailAi(false)">&#x2728; Generate with AI</button>
        <button onclick="emailAi(true)">&#x21bb; Refine with AI</button>
        <span id="emAiStatus" class="status"></span>
      </div>
    </div>
    <div class="actions">
      <button class="primary" onclick="emailSend()">Send via Resend</button>
      <button onclick="closeEmail()">Cancel</button>
      <span id="emSendStatus" class="status"></span>
    </div>
  </div>
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

function _trimReplayTitle(t, n) {
  if (!t) return '';
  const s = String(t).replace(/\\s+/g, ' ').trim();
  return s.length <= n ? s : s.slice(0, n - 1) + '\\u2026';
}

const SESSION_ID = (location.pathname.split('/replay/')[1] || '').split(/[?#]/)[0];

async function loadReplay() {
  if (!SESSION_ID) { document.getElementById('board').innerHTML = '<div class="loading">No session ID</div>'; return; }
  try {
    const resp = await fetch('/api/replay/' + SESSION_ID);
    const data = await resp.json();
    if (data.error) { document.getElementById('board').innerHTML = '<div class="loading">' + esc(data.error) + '</div>'; return; }
    steps = data.steps || [];
    meta = data.meta || {};
    const fullTitle = (meta.student || '?') + ' \\u2014 ' + (meta.title || 'Session');
    const titleEl = document.getElementById('replayTitle');
    titleEl.textContent = _trimReplayTitle(fullTitle, 220);
    titleEl.setAttribute('title', fullTitle);
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

function _setStatus(id, cls, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = 'status' + (cls ? ' ' + cls : '');
  el.textContent = text || '';
}

async function openEmail() {
  if (!SESSION_ID) return;
  document.getElementById('emailOverlay').classList.add('show');
  _setStatus('emAiStatus', '', 'Loading draft\\u2026');
  _setStatus('emSendStatus', '', '');
  try {
    const resp = await fetch('/api/followup/draft/' + encodeURIComponent(SESSION_ID));
    const d = await resp.json();
    if (!resp.ok || d.error) {
      _setStatus('emAiStatus', 'err', d.error || 'Could not load draft');
      return;
    }
    document.getElementById('emTo').value = d.to || '';
    document.getElementById('emFrom').value = d.fromEmail || '';
    document.getElementById('emSubject').value = d.subject || '';
    document.getElementById('emText').value = d.text || '';
    document.getElementById('emInstr').value = '';
    _setStatus('emAiStatus', '', '');
  } catch (e) {
    _setStatus('emAiStatus', 'err', 'Draft load failed: ' + e);
  }
}

function closeEmail() {
  document.getElementById('emailOverlay').classList.remove('show');
}

async function emailAi(useCurrent) {
  if (!SESSION_ID) return;
  const instr = (document.getElementById('emInstr').value || '').trim();
  _setStatus('emAiStatus', '', 'Asking the model\\u2026');
  try {
    const body = {
      sessionId: SESSION_ID,
      instruction: useCurrent ? instr : '',
      currentSubject: useCurrent ? document.getElementById('emSubject').value : '',
      currentBody: useCurrent ? document.getElementById('emText').value : '',
    };
    const resp = await fetch('/api/followup/ai-compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const d = await resp.json();
    if (!resp.ok || d.error) {
      _setStatus('emAiStatus', 'err', 'AI failed: ' + (d.error || ('HTTP ' + resp.status)));
      return;
    }
    if (d.subject) document.getElementById('emSubject').value = d.subject;
    if (d.text) document.getElementById('emText').value = d.text;
    const tag = useCurrent ? 'Refined' : 'Generated';
    _setStatus('emAiStatus', 'ok',
               '\\u2713 ' + tag + (d.model ? ' (' + d.model + ')' : '') +
               '. Review, edit, then send.');
  } catch (e) {
    _setStatus('emAiStatus', 'err', 'AI failed: ' + e);
  }
}

async function emailSend() {
  const to = (document.getElementById('emTo').value || '').trim();
  const fromEmail = (document.getElementById('emFrom').value || '').trim();
  const subject = (document.getElementById('emSubject').value || '').trim();
  const text = (document.getElementById('emText').value || '').trim();
  if (!to || !subject || !text) {
    _setStatus('emSendStatus', 'err', 'To, subject and body are required.');
    return;
  }
  if (!confirm('Send this follow-up to ' + to + '?')) return;
  _setStatus('emSendStatus', '', 'Sending\\u2026');
  const html = text.split(/\\n\\s*\\n/).map(function (p) {
    return '<p>' + esc(p).replace(/\\n/g, '<br>') + '</p>';
  }).join('');
  try {
    const resp = await fetch('/api/followup/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId: SESSION_ID, to, subject, text, html, fromEmail }),
    });
    const d = await resp.json();
    if (resp.ok && d.status === 'sent') {
      _setStatus('emSendStatus', 'ok',
                 '\\u2713 Sent (id ' + (d.id || 'ok') + ').');
    } else {
      _setStatus('emSendStatus', 'err',
                 'Send failed: ' + (d.error || ('HTTP ' + resp.status)));
    }
  } catch (e) {
    _setStatus('emSendStatus', 'err', 'Send failed: ' + e);
  }
}

document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') closeEmail();
});

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

    print("\n  Euler Admin Dashboard", flush=True)
    print(f"  Open: http://127.0.0.1:{args.port}/  (same UI at /dashboard)", flush=True)
    _mongo_host = urlparse(MONGO_URI).hostname or "(unknown host)"
    print(
        f"  MongoDB: {_mongo_host} / db={MONGO_DB_NAME} (from ../backend/.env + MONGODB_DB)",
        flush=True,
    )
    print(
        f"  Tip: response header Server: {DashboardHandler.server_version} confirms this app.",
        flush=True,
    )

    # One-time index creation (no-op if they exist)
    try:
        run_async(ensure_indexes())
    except Exception as _e:
        print(f"  WARN index creation error (continuing): {_e}", flush=True)

    print(f"  Binding HTTP server to 0.0.0.0:{args.port} ...", flush=True)
    server = ThreadedHTTPServer(("0.0.0.0", args.port), DashboardHandler)
    addr = server.server_address
    host, port = addr[0], addr[1]
    print(f"  OK Bound to {host}:{port}", flush=True)
    print(
        "  Listening (process is idle until you open the URL or call /api/*).",
        flush=True,
    )
    print(
        "  Optional: set DASHBOARD_ACCESS_LOG=1 to log each HTTP request to stderr.",
        flush=True,
    )
    print("  Press Ctrl+C to stop.\n", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
        server.server_close()
        if _client:
            _client.close()
