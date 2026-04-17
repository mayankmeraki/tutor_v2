"""Tests for byo.retrieval.rerank.cohere_rerank."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from byo.retrieval import rerank as rerank_mod
from byo.retrieval.rerank import cohere_rerank
from byo.shared.models import ChunkAnchor
from byo.shared.results import RetrievedChunk


pytestmark = pytest.mark.asyncio


def _mk_hit(chunk_id: str, content: str, score: float = 0.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        segment_id=chunk_id,
        resource_id="r",
        collection_id="c",
        content=content,
        anchor=ChunkAnchor(),
        score=score,
    )


def _mock_settings(api_key: str = "test-openrouter-key"):
    # Rerank routes through OpenRouter; the settings lookup reads
    # OPENROUTER_API_KEY. Keep COHERE_API_KEY populated too for any
    # code path that still references the old key.
    s = MagicMock()
    s.OPENROUTER_API_KEY = api_key
    s.COHERE_API_KEY = api_key
    return s


class _MockResponse:
    def __init__(self, status_code=200, json_body=None, text=""):
        self.status_code = status_code
        self._json = json_body or {}
        self.text = text or str(json_body)

    def json(self):
        return self._json


class _MockAsyncClient:
    """Context-manager + async post, returns a configurable response."""

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
        if self._exc is not None:
            raise self._exc
        return self._response


def _patch_httpx_client(monkeypatch, *, response=None, exc=None):
    client = _MockAsyncClient(response=response, exc=exc)

    def _factory(*a, **kw):
        return client

    monkeypatch.setattr(rerank_mod.httpx, "AsyncClient", _factory)
    return client


class TestHappyPath:
    async def test_reorders_hits_by_cohere_score(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings())
        hits = [
            _mk_hit("a", "foo"),
            _mk_hit("b", "bar"),
            _mk_hit("c", "baz"),
        ]
        # Cohere returns: index 2 first (best), then 0, then 1
        body = {
            "results": [
                {"index": 2, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.8},
                {"index": 1, "relevance_score": 0.3},
            ]
        }
        client = _patch_httpx_client(
            monkeypatch, response=_MockResponse(200, body)
        )

        out = await cohere_rerank("query?", hits, top_n=3)
        assert [h.chunk_id for h in out] == ["c", "a", "b"]
        # Relevance scores attached
        assert out[0].rerank_score == pytest.approx(0.95)
        assert out[1].rerank_score == pytest.approx(0.8)
        assert out[2].rerank_score == pytest.approx(0.3)
        # Correct endpoint + payload
        assert client.posted_url == rerank_mod.RERANK_URL
        assert client.posted_headers["Authorization"].startswith("Bearer ")
        assert client.posted_json["query"] == "query?"
        assert client.posted_json["documents"] == ["foo", "bar", "baz"]
        assert client.posted_json["top_n"] == 3
        assert client.posted_json["model"] == rerank_mod.RERANK_MODEL

    async def test_top_n_truncates(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings())
        hits = [_mk_hit(str(i), f"c{i}") for i in range(5)]
        body = {
            "results": [
                {"index": 4, "relevance_score": 1.0},
                {"index": 3, "relevance_score": 0.9},
                {"index": 2, "relevance_score": 0.8},
                {"index": 1, "relevance_score": 0.7},
                {"index": 0, "relevance_score": 0.6},
            ]
        }
        _patch_httpx_client(monkeypatch, response=_MockResponse(200, body))
        out = await cohere_rerank("q", hits, top_n=2)
        # Cohere was told top_n=2, but even if it returns more, we clamp
        assert len(out) == 2
        assert [h.chunk_id for h in out] == ["4", "3"]


class TestGracefulDegradation:
    async def test_no_api_key_returns_input(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings(""))
        hits = [_mk_hit("a", "foo"), _mk_hit("b", "bar")]
        out = await cohere_rerank("q", hits, top_n=5)
        assert out == hits[:5]
        # No rerank_score attached
        for h in out:
            assert h.rerank_score is None

    async def test_timeout_returns_input(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings())
        hits = [_mk_hit("a", "foo"), _mk_hit("b", "bar")]
        _patch_httpx_client(monkeypatch, exc=httpx.TimeoutException("slow"))
        out = await cohere_rerank("q", hits, top_n=5)
        assert out == hits[:5]

    async def test_non_200_returns_input(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings())
        hits = [_mk_hit("a", "foo"), _mk_hit("b", "bar")]
        _patch_httpx_client(
            monkeypatch, response=_MockResponse(500, {"error": "down"})
        )
        out = await cohere_rerank("q", hits, top_n=5)
        assert out == hits[:5]

    async def test_bad_json_returns_input(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings())
        hits = [_mk_hit("a", "foo"), _mk_hit("b", "bar")]

        class _BadJSON:
            status_code = 200
            text = "nope"

            def json(self):
                raise ValueError("not json")

        _patch_httpx_client(monkeypatch, response=_BadJSON())
        out = await cohere_rerank("q", hits, top_n=5)
        assert out == hits[:5]

    async def test_unexpected_payload_empty_results(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings())
        hits = [_mk_hit("a", "foo"), _mk_hit("b", "bar")]
        _patch_httpx_client(
            monkeypatch,
            response=_MockResponse(200, {"results": []}),
        )
        out = await cohere_rerank("q", hits, top_n=5)
        assert out == hits[:2]

    async def test_results_all_bad_indexes_returns_input(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings())
        hits = [_mk_hit("a", "foo")]
        _patch_httpx_client(
            monkeypatch,
            response=_MockResponse(
                200,
                {
                    "results": [
                        {"index": 99, "relevance_score": 0.5},
                        {"index": -1, "relevance_score": 0.4},
                    ]
                },
            ),
        )
        out = await cohere_rerank("q", hits, top_n=5)
        assert out == hits[:1]

    async def test_empty_hits_returns_empty(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings())
        out = await cohere_rerank("q", [], top_n=5)
        assert out == []

    async def test_unknown_exception_returns_input(self, monkeypatch):
        monkeypatch.setattr(rerank_mod, "_settings", lambda: _mock_settings())
        hits = [_mk_hit("a", "foo")]
        _patch_httpx_client(monkeypatch, exc=RuntimeError("boom"))
        out = await cohere_rerank("q", hits, top_n=5)
        assert out == hits[:1]
