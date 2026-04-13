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
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
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


def compute_interaction_time(transcript: list) -> dict:
    """Compute actual interaction time from transcript message timestamps.

    Returns {
        activeSec: int — sum of gaps between consecutive msgs, each capped at INTERACTION_GAP_CAP_SEC,
        spanSec: int — wall-clock from first to last message,
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
    active = 0
    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i - 1]
        active += int(min(gap, INTERACTION_GAP_CAP_SEC))

    first_dt = datetime.fromtimestamp(timestamps[0], tz=timezone.utc)
    last_dt = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)
    return {
        "activeSec": active,
        "spanSec": span,
        "firstMsg": first_dt.isoformat()[:19],
        "lastMsg": last_dt.isoformat()[:19],
    }


# ── API handlers ────────────────────────────────────────────────────

async def fetch_stats():
    db = get_db()
    total_users = await db.users.count_documents({})
    total_sessions = await db.sessions.count_documents({})
    active_sessions = await db.sessions.count_documents({"status": "active"})
    external_sessions = await db.sessions.count_documents({"userEmail": {"$ne": "mayank@test.com"}})
    return {
        "totalUsers": total_users,
        "totalSessions": total_sessions,
        "activeSessions": active_sessions,
        "externalSessions": external_sessions,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


async def fetch_users():
    db = get_db()
    users = await db.users.find(
        {}, {"name": 1, "email": 1, "createdAt": 1}
    ).sort("createdAt", -1).to_list(length=500)

    # Fetch all sessions with transcripts for accurate time calculation
    all_sessions = await db.sessions.find(
        {},
        {"userEmail": 1, "metrics": 1, "createdAt": 1, "transcript.timestamp": 1},
    ).to_list(length=5000)

    # Aggregate per user
    user_stats: dict[str, dict] = {}
    for s in all_sessions:
        email = s.get("userEmail", "")
        if email not in user_stats:
            user_stats[email] = {
                "sessionCount": 0, "totalActive": 0, "totalSpan": 0,
                "totalTurns": 0, "totalStudentResponses": 0, "lastSession": "",
            }
        st = user_stats[email]
        st["sessionCount"] += 1
        metrics = s.get("metrics") or {}
        st["totalTurns"] += metrics.get("totalTurns", 0)
        st["totalStudentResponses"] += metrics.get("studentResponses", 0)
        created = str(s.get("createdAt", ""))[:19]
        if created > st["lastSession"]:
            st["lastSession"] = created

        timing = compute_interaction_time(s.get("transcript", []))
        st["totalActive"] += timing["activeSec"]
        st["totalSpan"] += timing["spanSec"]

    result = []
    for u in users:
        email = u.get("email", "")
        st = user_stats.get(email, {})
        result.append({
            "name": u.get("name", "?"),
            "email": email,
            "createdAt": str(u.get("createdAt", ""))[:19],
            "sessions": st.get("sessionCount", 0),
            "totalActive": st.get("totalActive", 0),
            "totalSpan": st.get("totalSpan", 0),
            "totalTurns": st.get("totalTurns", 0),
            "studentResponses": st.get("totalStudentResponses", 0),
            "lastSession": st.get("lastSession", ""),
        })
    return result


async def fetch_sessions():
    db = get_db()
    sessions = await db.sessions.find(
        {},
        {
            "userEmail": 1, "studentName": 1, "title": 1, "headline": 1,
            "createdAt": 1, "durationSec": 1, "metrics": 1, "intent": 1,
            "status": 1, "teachingMode": 1, "courseId": 1,
            "transcript.timestamp": 1, "transcript.role": 1,
        },
    ).sort("createdAt", -1).to_list(length=200)

    result = []
    for s in sessions:
        metrics = s.get("metrics") or {}
        intent = s.get("intent") or {}
        raw_intent = intent.get("raw", "") if isinstance(intent, dict) else str(intent)
        timing = compute_interaction_time(s.get("transcript", []))
        result.append({
            "_id": str(s.get("_id", "")),
            "user": s.get("studentName", "?"),
            "email": s.get("userEmail", ""),
            "title": s.get("title") or s.get("headline") or "(no title)",
            "createdAt": str(s.get("createdAt", ""))[:19],
            "durationRaw": s.get("durationSec") or 0,
            "activeSec": timing["activeSec"],
            "spanSec": timing["spanSec"],
            "firstMsg": timing["firstMsg"],
            "lastMsg": timing["lastMsg"],
            "turns": metrics.get("totalTurns", 0),
            "studentResponses": metrics.get("studentResponses", 0),
            "status": s.get("status", "?"),
            "intent": raw_intent[:120],
            "mode": s.get("teachingMode", ""),
            "courseId": s.get("courseId", ""),
        })
    return result


async def fetch_transcript(session_id: str):
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
    return {"transcript": cleaned}


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
    from bson import ObjectId
    db = get_db()
    s = None
    try:
        s = await db.sessions.find_one(
            {"_id": ObjectId(session_id)},
            {"transcript": 1, "backendState.messages": 1,
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
    return {"steps": steps, "meta": meta}


# ── HTTP server ─────────────────────────────────────────────────────

_loop = None

def run_async(coro):
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop.run_until_complete(coro)


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
                self._json(run_async(fetch_sessions()))
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
        <th onclick="sortTable('users','studentResponses')">Student Msgs <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('users','lastSession')">Last Session <span class="arr">&#9650;</span></th>
      </tr></thead>
      <tbody></tbody>
    </table></div>
  </div>

  <div id="tab-sessions" class="tab-panel">
    <div class="table-wrap"><table id="sessionsTable">
      <thead><tr>
        <th>#</th>
        <th onclick="sortTable('sessions','user')">User <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('sessions','title')">Topic <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('sessions','createdAt')">Started <span class="arr on">&#9660;</span></th>
        <th onclick="sortTable('sessions','activeSec')">Active Time <span class="arr">&#9650;</span></th>
        <th onclick="sortTable('sessions','turns')">Turns <span class="arr">&#9650;</span></th>
        <th>Intent</th>
        <th>Mode</th>
        <th onclick="sortTable('sessions','status')">Status <span class="arr">&#9650;</span></th>
      </tr></thead>
      <tbody></tbody>
    </table></div>
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

function renderStats(d) {
  document.getElementById('statsCards').innerHTML = `
    <div class="stat-card"><div class="label">Total Users</div><div class="value c1">${d.totalUsers}</div></div>
    <div class="stat-card"><div class="label">Total Sessions</div><div class="value c2">${d.totalSessions}</div></div>
    <div class="stat-card"><div class="label">Active Sessions</div><div class="value c3">${d.activeSessions}</div></div>
    <div class="stat-card"><div class="label">External Sessions</div><div class="value c4">${d.externalSessions}</div></div>
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
  document.querySelector('#usersTable tbody').innerHTML = data.map((u, i) => `<tr>
    <td class="muted">${i + 1}</td>
    <td class="bold">${esc(u.name)}</td>
    <td class="mono">${esc(u.email)}</td>
    <td class="sm">${fmtDate(u.createdAt)}<br><span class="muted">${ago(u.createdAt)}</span></td>
    <td class="bold">${zeroWrap(u.sessions)}</td>
    <td class="dur">${fmtDur(u.totalActive)}</td>
    <td>${zeroWrap(u.totalTurns)}</td>
    <td>${zeroWrap(u.studentResponses)}</td>
    <td class="sm">${u.lastSession ? fmtDate(u.lastSession) : '\\u2014'}</td>
  </tr>`).join('');
}

function renderSessions() {
  const q = getQ();
  let data = sortData(sessionsData, sortState.sessions.col, sortState.sessions.dir);
  if (q) data = data.filter(s =>
    (s.user||'').toLowerCase().includes(q) || (s.email||'').toLowerCase().includes(q) ||
    (s.title||'').toLowerCase().includes(q) || (s.intent||'').toLowerCase().includes(q));
  document.querySelector('#sessionsTable tbody').innerHTML = data.map((s, i) => {
    const activeStr = fmtDur(s.activeSec);
    const spanStr = s.spanSec > 0 && s.spanSec !== s.activeSec ? ' <span class="dur-raw">(' + fmtDur(s.spanSec) + ' span)</span>' : '';
    return `<tr>
    <td class="muted">${i + 1}</td>
    <td><span class="bold">${esc(s.user)}</span><br><span class="mono muted">${esc(s.email)}</span></td>
    <td><span class="link" onclick="viewTranscript('${s._idx}')" title="View transcript">${esc(s.title)}</span>
        <br><a class="mono muted" href="/replay/${s._id}" target="_blank" style="font-size:10px;color:var(--accent2);text-decoration:none" title="Open replay">&#9654; replay</a></td>
    <td class="sm">${fmtDate(s.createdAt)}<br><span class="muted">${ago(s.createdAt)}</span></td>
    <td><span class="dur">${activeStr}</span>${spanStr}</td>
    <td>${zeroWrap(s.turns)}</td>
    <td class="sm muted" style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s.intent)}</td>
    <td>${s.mode ? `<span class="badge ${s.mode==='voice'?'b-voice':'b-text'}">${s.mode}</span>` : '\\u2014'}</td>
    <td><span class="badge ${s.status==='active'?'b-active':'b-ended'}">${s.status}</span></td>
  </tr>`;}).join('');
}

function filterTable() { renderUsers(); renderSessions(); }

function switchTab(tab) {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tab));
}

async function viewTranscript(idx) {
  const s = sessionsData[idx];
  if (!s || !s._id) return;
  const title = (s.user || '?') + ' \\u2014 ' + (s.title || 'Session');
  const subtitle = 'Active: ' + fmtDur(s.activeSec) + ' | Span: ' + fmtDur(s.spanSec) + ' | ' + s.turns + ' turns';
  document.getElementById('modalTitle').innerHTML = esc(title) + '<br><span class="muted sm">' + subtitle + '</span>';
  document.getElementById('modalBody').innerHTML = '<p class="muted">Loading transcript...</p>';
  document.getElementById('modal').classList.add('show');
  try {
    const resp = await fetch(API + '/api/transcript/' + s._id);
    const data = await resp.json();
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
    document.getElementById('modalBody').innerHTML = html;
  } catch (e) {
    document.getElementById('modalBody').innerHTML = '<p style="color:var(--red)">Failed to load transcript.</p>';
  }
}
function closeModal() { document.getElementById('modal').classList.remove('show'); }
document.getElementById('modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

async function refreshAll() {
  const t0 = performance.now();
  document.getElementById('statusBar').textContent = 'refreshing...';
  try {
    const [sr, ur, sesr] = await Promise.all([
      fetch(API + '/api/stats'), fetch(API + '/api/users'), fetch(API + '/api/sessions'),
    ]);
    const stats = await sr.json();
    usersData = await ur.json();
    const raw = await sesr.json();
    sessionsData = raw.map((s, i) => ({ ...s, _idx: i }));

    renderStats(stats);
    renderUsers();
    renderSessions();

    const ms = Math.round(performance.now() - t0);
    document.getElementById('statusBar').textContent =
      'updated ' + new Date().toLocaleTimeString() + ' (' + ms + 'ms) \\u2014 ' +
      usersData.length + ' users, ' + sessionsData.length + ' sessions loaded';
  } catch (e) {
    document.getElementById('statusBar').textContent = 'error: ' + e.message;
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
  .board-item.draw-figure { padding: 14px; background: rgba(96,165,250,.06);
                            border: 1px dashed var(--blue); border-radius: 8px; margin: 10px 0;
                            color: var(--blue); font-style: italic; font-size: 13px; }
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
    case 'animation':
      return `<div class="board-item draw-figure">[Animation: ${esc(draw.id || text || 'visual')}]</div>`;
    default:
      return text ? `<div class="board-item draw-text" style="${style}">${esc(text)}</div>` : '';
  }
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

function goStart() { cursor = -1; document.getElementById('board').innerHTML = ''; document.getElementById('chat').innerHTML = ''; updateButtons(); }
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
    print(f"  http://localhost:{args.port}\n")

    server = HTTPServer(("0.0.0.0", args.port), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
        if _client:
            _client.close()
