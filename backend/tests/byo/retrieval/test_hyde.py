"""Tests for byo.retrieval.query.hyde_expand."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from byo.retrieval import query as query_mod
from byo.retrieval.query import hyde_expand


pytestmark = pytest.mark.asyncio


def _mock_settings(api_key="or-key", fast="anthropic/claude-haiku-4.5"):
    s = MagicMock()
    s.OPENROUTER_API_KEY = api_key
    s.MODEL_FAST = fast
    return s


class _MockResponse:
    def __init__(self, status_code=200, json_body=None, text=""):
        self.status_code = status_code
        self._json = json_body or {}
        self.text = text or str(json_body)

    def json(self):
        return self._json


class _MockAsyncClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.posted_url = None
        self.posted_headers = None
        self.posted_json = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        self.posted_url = url
        self.posted_headers = headers
        self.posted_json = json
        if self._exc:
            raise self._exc
        return self._response


def _patch_client(monkeypatch, *, response=None, exc=None):
    client = _MockAsyncClient(response=response, exc=exc)
    monkeypatch.setattr(query_mod.httpx, "AsyncClient", lambda *a, **kw: client)
    return client


class TestHappyPath:
    async def test_returns_passage_on_success(self, monkeypatch):
        monkeypatch.setattr(query_mod, "_settings", lambda: _mock_settings())
        body = {
            "choices": [
                {"message": {"content": "A hypothetical passage about mitochondria."}}
            ]
        }
        client = _patch_client(monkeypatch, response=_MockResponse(200, body))
        out = await hyde_expand("what are mitochondria?")
        assert out == "A hypothetical passage about mitochondria."
        # Prompt includes the query
        assert "what are mitochondria?" in client.posted_json["messages"][0]["content"]
        assert client.posted_json["model"] == "anthropic/claude-haiku-4.5"
        assert client.posted_url == query_mod.OPENROUTER_CHAT_URL

    async def test_passage_stripped(self, monkeypatch):
        monkeypatch.setattr(query_mod, "_settings", lambda: _mock_settings())
        body = {
            "choices": [{"message": {"content": "   a passage   "}}]
        }
        _patch_client(monkeypatch, response=_MockResponse(200, body))
        out = await hyde_expand("q")
        assert out == "a passage"


class TestGracefulDegradation:
    async def test_empty_query_returned_unchanged(self, monkeypatch):
        monkeypatch.setattr(query_mod, "_settings", lambda: _mock_settings())
        # Should not make a network call
        called = {"n": 0}

        def _factory(*a, **kw):
            called["n"] += 1

            class _C:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *a):
                    return False

                async def post(self, *a, **kw):
                    raise AssertionError("should not be called")

            return _C()

        monkeypatch.setattr(query_mod.httpx, "AsyncClient", _factory)

        assert await hyde_expand("") == ""
        assert await hyde_expand("   ") == "   "
        assert called["n"] == 0

    async def test_no_api_key_returns_query(self, monkeypatch):
        monkeypatch.setattr(query_mod, "_settings", lambda: _mock_settings(api_key=""))
        out = await hyde_expand("my query")
        assert out == "my query"

    async def test_timeout_returns_query(self, monkeypatch):
        monkeypatch.setattr(query_mod, "_settings", lambda: _mock_settings())
        _patch_client(monkeypatch, exc=httpx.TimeoutException("slow"))
        out = await hyde_expand("my query")
        assert out == "my query"

    async def test_non_200_returns_query(self, monkeypatch):
        monkeypatch.setattr(query_mod, "_settings", lambda: _mock_settings())
        _patch_client(monkeypatch, response=_MockResponse(500, {"error": "x"}))
        out = await hyde_expand("my query")
        assert out == "my query"

    async def test_network_error_returns_query(self, monkeypatch):
        monkeypatch.setattr(query_mod, "_settings", lambda: _mock_settings())
        _patch_client(monkeypatch, exc=RuntimeError("boom"))
        out = await hyde_expand("my query")
        assert out == "my query"

    async def test_missing_choices_returns_query(self, monkeypatch):
        monkeypatch.setattr(query_mod, "_settings", lambda: _mock_settings())
        _patch_client(monkeypatch, response=_MockResponse(200, {}))
        out = await hyde_expand("my query")
        assert out == "my query"

    async def test_empty_passage_falls_back_to_query(self, monkeypatch):
        monkeypatch.setattr(query_mod, "_settings", lambda: _mock_settings())
        body = {"choices": [{"message": {"content": "   "}}]}
        _patch_client(monkeypatch, response=_MockResponse(200, body))
        out = await hyde_expand("my query")
        assert out == "my query"
