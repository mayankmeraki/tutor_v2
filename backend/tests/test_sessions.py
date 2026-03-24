"""Tests for session REST endpoints."""

import pytest
import httpx
from datetime import datetime, timezone


class TestCreateSession:
    async def test_create_session(self, test_client: httpx.AsyncClient):
        resp = await test_client.post("/api/v1/sessions", json={
            "sessionId": "sess-create-001",
            "courseId": 1,
            "studentName": "Alice",
            "userEmail": "alice@example.com",
            "intent": {"raw": "study waves", "scenario": "course"},
            "sections": [],
            "transcript": [],
            "startedAt": datetime.now(timezone.utc).isoformat(),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessionId"] == "sess-create-001"
        assert data["studentName"] == "Alice"

    async def test_create_session_missing_id(self, test_client: httpx.AsyncClient):
        resp = await test_client.post("/api/v1/sessions", json={
            "courseId": 1,
            "studentName": "Bob",
        })
        assert resp.status_code == 400
        assert "sessionId" in resp.json()["detail"]


class TestGetSession:
    async def test_get_session(self, test_client: httpx.AsyncClient, test_session):
        resp = await test_client.get("/api/v1/sessions/test-session-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessionId"] == "test-session-001"
        assert data["studentName"] == "Test User"

    async def test_get_session_not_found(self, test_client: httpx.AsyncClient):
        resp = await test_client.get("/api/v1/sessions/nonexistent-id")
        assert resp.status_code == 404


class TestPatchSession:
    async def test_patch_session(self, test_client: httpx.AsyncClient, test_session):
        resp = await test_client.patch("/api/v1/sessions/test-session-001", json={
            "status": "completed",
            "durationSec": 1200,
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify the update persisted
        get_resp = await test_client.get("/api/v1/sessions/test-session-001")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "completed"
        assert get_resp.json()["durationSec"] == 1200

    async def test_patch_session_not_found(self, test_client: httpx.AsyncClient):
        resp = await test_client.patch("/api/v1/sessions/nonexistent-id", json={
            "status": "completed",
        })
        assert resp.status_code == 404


class TestGetMySessions:
    async def test_get_my_sessions(self, test_client: httpx.AsyncClient, auth_headers):
        # Create a session tied to the authenticated user's email
        await test_client.post("/api/v1/sessions", json={
            "sessionId": "my-sess-001",
            "courseId": 42,
            "studentName": "Test User",
            "userEmail": "test@example.com",
            "intent": {"raw": "review", "scenario": "course"},
            "sections": [],
            "transcript": [],
            "startedAt": datetime.now(timezone.utc).isoformat(),
        })

        resp = await test_client.get(
            "/api/v1/sessions/me/42",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["sessionId"] == "my-sess-001"

    async def test_get_my_sessions_empty(self, test_client: httpx.AsyncClient, auth_headers):
        resp = await test_client.get(
            "/api/v1/sessions/me/999",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []
