"""Shared pytest fixtures for backend tests."""

import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest
import httpx

# Set required env vars BEFORE any app imports
os.environ.setdefault("MOCKUP_JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

# Ensure directories that app.main expects at module level
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(_backend_dir, "rendered"), exist_ok=True)
# frontend dir — create if missing so StaticFiles doesn't error
_frontend_dir = os.path.join(os.path.dirname(_backend_dir), "frontend")
os.makedirs(_frontend_dir, exist_ok=True)


# ---------------------------------------------------------------------------
# Mock MongoDB — must be patched before FastAPI app is imported
# ---------------------------------------------------------------------------

class FakeCursor:
    """Async iterator that yields documents from a list."""

    def __init__(self, docs: list[dict]):
        self._docs = list(docs)
        self._sorted_key = None
        self._sorted_dir = None

    def sort(self, key, direction=-1):
        self._sorted_key = key
        self._sorted_dir = direction
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._docs:
            raise StopAsyncIteration
        return self._docs.pop(0)


class FakeCollection:
    """In-memory mock of a Motor collection supporting basic CRUD."""

    def __init__(self):
        self._docs: list[dict] = []
        self._id_counter = 0

    async def insert_one(self, doc: dict):
        self._id_counter += 1
        doc = dict(doc)
        from bson import ObjectId
        try:
            oid = ObjectId()
        except Exception:
            oid = f"fake_id_{self._id_counter}"
        doc["_id"] = oid
        self._docs.append(doc)
        result = MagicMock()
        result.inserted_id = oid
        return result

    async def find_one(self, query: dict, projection=None):
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items() if not k.startswith("$")):
                return dict(doc)
        return None

    def find(self, query: dict):
        matched = []
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items()):
                matched.append(dict(doc))
        return FakeCursor(matched)

    async def find_one_and_update(self, query, update, return_document=False):
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items()):
                if "$set" in update:
                    doc.update(update["$set"])
                return dict(doc)
        return None

    async def update_one(self, query, update, upsert=False):
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items() if not k.startswith("$")):
                if "$set" in update:
                    doc.update(update["$set"])
                result = MagicMock()
                result.modified_count = 1
                return result
        result = MagicMock()
        result.modified_count = 0
        return result

    async def create_index(self, *args, **kwargs):
        pass


class FakeDatabase:
    """In-memory mock of a Motor database with dynamic collections."""

    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self._collections:
            self._collections[name] = FakeCollection()
        return self._collections[name]


_fake_tutor_db = FakeDatabase()


def _mock_get_tutor_db():
    return _fake_tutor_db


@pytest.fixture(autouse=True)
def mock_mongodb():
    """Patch get_tutor_db so all services use in-memory collections.

    Resets the fake DB between tests for isolation.
    """
    global _fake_tutor_db
    _fake_tutor_db = FakeDatabase()

    with patch("app.core.mongodb.get_tutor_db", _mock_get_tutor_db), \
         patch("app.services.session.user_service.get_tutor_db", _mock_get_tutor_db), \
         patch("app.services.session.session_service.get_tutor_db", _mock_get_tutor_db):
        yield _fake_tutor_db


@pytest.fixture
def fake_db(mock_mongodb):
    """Direct access to the fake database for test assertions."""
    return mock_mongodb


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_client(mock_mongodb):
    """Async httpx test client wired to the FastAPI app."""
    from app.main import app as fastapi_app

    # Override lifespan to skip real DB connections (MongoDB, Postgres)
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(a):
        yield

    fastapi_app.router.lifespan_context = _noop_lifespan

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fastapi_app),
        base_url="http://testserver",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

@pytest.fixture
async def auth_headers(test_client: httpx.AsyncClient):
    """Create a test user via signup and return Bearer token headers."""
    resp = await test_client.post("/api/v1/auth/signup", json={
        "name": "Test User",
        "email": "test@example.com",
        "password": "testpass123",
    })
    assert resp.status_code == 200, f"Signup failed: {resp.text}"
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_session(test_client: httpx.AsyncClient):
    """Create a test session and return its data."""
    session_data = {
        "sessionId": "test-session-001",
        "courseId": 1,
        "studentName": "Test User",
        "userEmail": "test@example.com",
        "intent": {"raw": "learn physics", "scenario": "course"},
        "sections": [],
        "transcript": [],
        "startedAt": datetime.now(timezone.utc).isoformat(),
    }
    resp = await test_client.post("/api/v1/sessions", json=session_data)
    assert resp.status_code == 200, f"Session creation failed: {resp.text}"
    return resp.json()
