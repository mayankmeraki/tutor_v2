"""Tests for auth endpoints — signup, login, /me."""

import pytest
import httpx


class TestSignup:
    async def test_signup_success(self, test_client: httpx.AsyncClient):
        resp = await test_client.post("/api/v1/auth/signup", json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "securepass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == "alice@example.com"
        assert data["user"]["name"] == "Alice"
        assert data["user"]["role"] == "student"

    async def test_signup_duplicate_email(self, test_client: httpx.AsyncClient):
        payload = {
            "name": "Bob",
            "email": "bob@example.com",
            "password": "password123",
        }
        # First signup should succeed
        resp1 = await test_client.post("/api/v1/auth/signup", json=payload)
        assert resp1.status_code == 200

        # Second signup with same email should fail
        resp2 = await test_client.post("/api/v1/auth/signup", json=payload)
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"]

    async def test_signup_short_password(self, test_client: httpx.AsyncClient):
        resp = await test_client.post("/api/v1/auth/signup", json={
            "name": "Charlie",
            "email": "charlie@example.com",
            "password": "abc",
        })
        assert resp.status_code == 400
        assert "at least 6" in resp.json()["detail"]


class TestLogin:
    async def test_login_success(self, test_client: httpx.AsyncClient):
        # Create user first
        await test_client.post("/api/v1/auth/signup", json={
            "name": "Dana",
            "email": "dana@example.com",
            "password": "danapass",
        })

        # Login with correct credentials
        resp = await test_client.post("/api/v1/auth/login", json={
            "email": "dana@example.com",
            "password": "danapass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == "dana@example.com"

    async def test_login_wrong_password(self, test_client: httpx.AsyncClient):
        # Create user
        await test_client.post("/api/v1/auth/signup", json={
            "name": "Eve",
            "email": "eve@example.com",
            "password": "evepassword",
        })

        # Login with wrong password
        resp = await test_client.post("/api/v1/auth/login", json={
            "email": "eve@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]


class TestMe:
    async def test_me_authenticated(self, test_client: httpx.AsyncClient, auth_headers):
        resp = await test_client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"

    async def test_me_no_token(self, test_client: httpx.AsyncClient):
        resp = await test_client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]
