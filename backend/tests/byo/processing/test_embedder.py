"""Unit tests for byo.processing.embedder.embed_segments_batch.

Mocks httpx.AsyncClient so no real OpenRouter calls are made. Covers:
batch splitting, text capping, graceful error handling, question
generation for SEMANTIC-family modes, and skipping HyQE for
VISUAL_DESCRIPTION segments.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

import byo.processing.embedder as embedder_mod
from byo.processing.embedder import (
    EMBED_BATCH_SIZE,
    MAX_EMBED_CHARS,
    QUESTION_BATCH_SIZE,
    _embed_text,
    _needs_questions,
    embed_segments_batch,
)
from byo.shared.models import RetrievalMode


# ── httpx mock plumbing ────────────────────────────────────────────────

class FakeResponse:
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeAsyncClient:
    """Context-managed async client recording every POST."""
    instances: list["FakeAsyncClient"] = []

    def __init__(self, *args, **kwargs):
        self.calls: list[dict] = []
        self.timeout = kwargs.get("timeout")
        FakeAsyncClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url: str, *, headers=None, json=None, **kw):
        call = {"url": url, "headers": headers, "json": json}
        self.calls.append(call)
        return self._handler(call)

    # The test sets this before triggering the code-under-test.
    _handler = staticmethod(lambda call: FakeResponse(500, {}))


def _reset_client_mock():
    FakeAsyncClient.instances = []


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    """Provide an API key so embedder doesn't early-return."""
    fake_settings = MagicMock()
    fake_settings.OPENROUTER_API_KEY = "test-key"
    # The embedder imports inside the function: `from app.core.config import settings`.
    # Patch the attribute on the already-imported module if present, else
    # install a stub module. Tests that hit embedder internals will then
    # pick up our fake.
    try:
        import app.core.config as cfg
        monkeypatch.setattr(cfg, "settings", fake_settings)
    except ImportError:
        import sys
        import types
        pkg = types.ModuleType("app")
        core = types.ModuleType("app.core")
        conf = types.ModuleType("app.core.config")
        conf.settings = fake_settings
        sys.modules.setdefault("app", pkg)
        sys.modules.setdefault("app.core", core)
        sys.modules["app.core.config"] = conf


@pytest.fixture
def fake_httpx(monkeypatch):
    import httpx
    _reset_client_mock()
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


# ── Helpers to build segments / API responses ──────────────────────────


def _make_segment(i: int, content: str = None, mode: str = None) -> dict:
    return {
        "segment_id": f"seg-{i}",
        "parent_chunk_id": f"par-{i // 5}",
        "collection_id": "c1",
        "resource_id": "r1",
        "user_id": "u1",
        "index": i,
        "content": content if content is not None else f"seg content {i}",
        "tokens": 10,
        "questions": [],
        "anchor": {},
        "modality": "text",
        "retrieval_mode": mode or RetrievalMode.SEMANTIC.value,
        "topics": [],
        "embedding": None,
    }


def _embed_payload(n: int, dim: int = 1536) -> dict:
    return {
        "data": [
            {"index": i, "embedding": [0.0] * dim}
            for i in range(n)
        ]
    }


def _question_response(batches: list[list[list[str]]]) -> list[FakeResponse]:
    """Build responses for each question batch."""
    out = []
    for questions in batches:
        out.append(FakeResponse(200, {
            "choices": [{"message": {"content": json.dumps(questions)}}]
        }))
    return out


# ── Tests: helpers ────────────────────────────────────────────────────

class TestHelpers:
    def test_needs_questions_for_semantic(self):
        assert _needs_questions({"retrieval_mode": RetrievalMode.SEMANTIC.value})

    def test_needs_questions_for_exact_plus_semantic(self):
        assert _needs_questions(
            {"retrieval_mode": RetrievalMode.EXACT_PLUS_SEMANTIC.value}
        )

    def test_skip_questions_for_visual_description(self):
        assert not _needs_questions(
            {"retrieval_mode": RetrievalMode.VISUAL_DESCRIPTION.value}
        )

    def test_embed_text_caps_at_max(self):
        seg = {"content": "x" * (MAX_EMBED_CHARS + 500), "questions": []}
        out = _embed_text(seg)
        assert len(out) == MAX_EMBED_CHARS

    def test_embed_text_includes_questions(self):
        seg = {"content": "hello", "questions": ["Q1?", "Q2?"]}
        out = _embed_text(seg)
        assert out == "hello\nQ1?\nQ2?"

    def test_embed_text_no_questions_is_content_only(self):
        seg = {"content": "hello", "questions": []}
        assert _embed_text(seg) == "hello"


# ── Tests: embed_segments_batch ───────────────────────────────────────


class TestEmbedSegmentsBatch:

    async def test_empty_is_noop(self, fake_httpx):
        await embed_segments_batch([])
        assert fake_httpx.instances == []

    async def test_embeds_every_segment(self, fake_httpx):
        # Use VISUAL_DESCRIPTION to skip question calls → only embed calls.
        segs = [
            _make_segment(i, mode=RetrievalMode.VISUAL_DESCRIPTION.value)
            for i in range(3)
        ]
        FakeAsyncClient._handler = staticmethod(
            lambda call: FakeResponse(200, _embed_payload(3))
        )

        await embed_segments_batch(segs)

        assert all(s["embedding"] is not None for s in segs)
        assert all(len(s["embedding"]) == 1536 for s in segs)

    async def test_visual_description_skips_haiku(self, fake_httpx):
        segs = [
            _make_segment(i, mode=RetrievalMode.VISUAL_DESCRIPTION.value)
            for i in range(4)
        ]

        def _handler(call):
            # Should ONLY be embedding endpoint, never chat/completions.
            assert "embeddings" in call["url"], (
                f"unexpected URL: {call['url']}"
            )
            return FakeResponse(200, _embed_payload(len(call["json"]["input"])))

        FakeAsyncClient._handler = staticmethod(_handler)
        await embed_segments_batch(segs)

        # Confirm no chat/completions request was ever made.
        all_calls = [c for inst in fake_httpx.instances for c in inst.calls]
        assert all("embeddings" in c["url"] for c in all_calls)
        assert all(s["questions"] == [] for s in segs)

    async def test_question_generation_for_semantic(self, fake_httpx):
        segs = [
            _make_segment(i, mode=RetrievalMode.SEMANTIC.value) for i in range(2)
        ]

        def _handler(call):
            if "chat/completions" in call["url"]:
                questions = [["What is 0?"], ["What is 1?"]]
                return FakeResponse(200, {
                    "choices": [{"message": {"content": json.dumps(questions)}}]
                })
            # embeddings
            return FakeResponse(200, _embed_payload(len(call["json"]["input"])))

        FakeAsyncClient._handler = staticmethod(_handler)
        await embed_segments_batch(segs)

        assert segs[0]["questions"] == ["What is 0?"]
        assert segs[1]["questions"] == ["What is 1?"]
        # All embedded
        assert all(s["embedding"] for s in segs)

    async def test_embed_text_includes_questions_post_generation(self, fake_httpx):
        """The text sent to the embedding endpoint should contain the
        generated questions (not just content)."""
        seg = _make_segment(0, content="photosynthesis converts light to energy",
                            mode=RetrievalMode.SEMANTIC.value)

        captured_inputs: list[str] = []

        def _handler(call):
            if "chat/completions" in call["url"]:
                return FakeResponse(200, {
                    "choices": [{"message": {"content": json.dumps(
                        [["How does photosynthesis work?"]]
                    )}}]
                })
            # embeddings — capture the input text
            captured_inputs.extend(call["json"]["input"])
            return FakeResponse(200, _embed_payload(len(call["json"]["input"])))

        FakeAsyncClient._handler = staticmethod(_handler)
        await embed_segments_batch([seg])

        assert len(captured_inputs) == 1
        assert "photosynthesis" in captured_inputs[0]
        assert "How does photosynthesis work?" in captured_inputs[0]

    async def test_batch_size_splitting(self, fake_httpx):
        # Create more than one embed batch.
        n = EMBED_BATCH_SIZE + 7
        segs = [
            _make_segment(i, mode=RetrievalMode.VISUAL_DESCRIPTION.value)
            for i in range(n)
        ]

        def _handler(call):
            return FakeResponse(200, _embed_payload(len(call["json"]["input"])))

        FakeAsyncClient._handler = staticmethod(_handler)
        await embed_segments_batch(segs)

        # Collect embed calls across all client instances.
        embed_calls = [
            c for inst in fake_httpx.instances for c in inst.calls
            if "embeddings" in c["url"]
        ]
        assert len(embed_calls) == 2  # 50 + 7
        assert len(embed_calls[0]["json"]["input"]) == EMBED_BATCH_SIZE
        assert len(embed_calls[1]["json"]["input"]) == 7
        # All segments embedded.
        assert all(s["embedding"] is not None for s in segs)

    async def test_question_batch_size_splitting(self, fake_httpx):
        n = QUESTION_BATCH_SIZE + 5
        segs = [
            _make_segment(i, mode=RetrievalMode.SEMANTIC.value) for i in range(n)
        ]

        def _handler(call):
            if "chat/completions" in call["url"]:
                count = call["json"]["messages"][0]["content"].count("\n\n") or 1
                # Return n question-lists of 1 question each; alignment
                # happens per-batch inside embedder so just return enough.
                questions = [["q?"]] * n
                return FakeResponse(200, {
                    "choices": [{"message": {"content": json.dumps(questions)}}]
                })
            return FakeResponse(200, _embed_payload(len(call["json"]["input"])))

        FakeAsyncClient._handler = staticmethod(_handler)
        await embed_segments_batch(segs)

        chat_calls = [
            c for inst in fake_httpx.instances for c in inst.calls
            if "chat/completions" in c["url"]
        ]
        assert len(chat_calls) == 2  # 20 + 5

    async def test_graceful_500_embedding(self, fake_httpx):
        segs = [
            _make_segment(i, mode=RetrievalMode.VISUAL_DESCRIPTION.value)
            for i in range(3)
        ]

        def _handler(call):
            return FakeResponse(500, {"error": "boom"})

        FakeAsyncClient._handler = staticmethod(_handler)
        # Must not raise.
        await embed_segments_batch(segs)

        # Empty embeddings for each segment.
        for s in segs:
            assert s["embedding"] == []

    async def test_graceful_question_500_still_embeds(self, fake_httpx):
        segs = [
            _make_segment(i, mode=RetrievalMode.SEMANTIC.value) for i in range(2)
        ]

        def _handler(call):
            if "chat/completions" in call["url"]:
                return FakeResponse(500, {})
            return FakeResponse(200, _embed_payload(len(call["json"]["input"])))

        FakeAsyncClient._handler = staticmethod(_handler)
        await embed_segments_batch(segs)

        # Questions failed → stay empty. But embeddings should still succeed.
        assert all(s["questions"] == [] for s in segs)
        assert all(s["embedding"] and len(s["embedding"]) == 1536 for s in segs)

    async def test_long_content_capped_before_embed(self, fake_httpx):
        long = "abc " * 2000  # ~8000 chars
        segs = [_make_segment(0, content=long,
                              mode=RetrievalMode.VISUAL_DESCRIPTION.value)]

        captured: list[str] = []

        def _handler(call):
            captured.extend(call["json"]["input"])
            return FakeResponse(200, _embed_payload(len(call["json"]["input"])))

        FakeAsyncClient._handler = staticmethod(_handler)
        await embed_segments_batch(segs)

        assert len(captured) == 1
        assert len(captured[0]) == MAX_EMBED_CHARS

    async def test_question_response_with_markdown_fence_parsed(self, fake_httpx):
        """Haiku sometimes wraps JSON in ```...``` — embedder must strip."""
        segs = [_make_segment(0, mode=RetrievalMode.SEMANTIC.value)]

        wrapped = "```json\n" + json.dumps([["wrapped q?"]]) + "\n```"

        def _handler(call):
            if "chat/completions" in call["url"]:
                return FakeResponse(200, {
                    "choices": [{"message": {"content": wrapped}}]
                })
            return FakeResponse(200, _embed_payload(len(call["json"]["input"])))

        FakeAsyncClient._handler = staticmethod(_handler)
        await embed_segments_batch(segs)

        assert segs[0]["questions"] == ["wrapped q?"]

    async def test_question_capped_at_three(self, fake_httpx):
        segs = [_make_segment(0, mode=RetrievalMode.SEMANTIC.value)]

        def _handler(call):
            if "chat/completions" in call["url"]:
                return FakeResponse(200, {
                    "choices": [{"message": {"content": json.dumps(
                        [["q1", "q2", "q3", "q4", "q5"]]
                    )}}]
                })
            return FakeResponse(200, _embed_payload(len(call["json"]["input"])))

        FakeAsyncClient._handler = staticmethod(_handler)
        await embed_segments_batch(segs)

        assert segs[0]["questions"] == ["q1", "q2", "q3"]

    async def test_no_api_key_empty_embeddings(self, fake_httpx, monkeypatch):
        import app.core.config as cfg
        fake = MagicMock()
        fake.OPENROUTER_API_KEY = ""
        monkeypatch.setattr(cfg, "settings", fake)

        segs = [
            _make_segment(i, mode=RetrievalMode.VISUAL_DESCRIPTION.value)
            for i in range(2)
        ]
        await embed_segments_batch(segs)
        # Empty list indicates graceful fallback.
        assert all(s["embedding"] == [] for s in segs)
