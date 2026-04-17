"""Unit tests for byo.processing.orchestrator job state machine.

Mocks every heavy dependency (processors, chunker, classifier, embedder,
indexer) so we only exercise submit/claim/process flow, retry bookkeeping,
and state transitions. Real MongoDB, LLM, and filesystem are never touched.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

import byo.processing.orchestrator as orch
from byo.processing.orchestrator import (
    JobState,
    PIPELINE_STEPS,
    _claim_job,
    _process_job,
    get_job_status,
    submit_processing_job,
)


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def wired_mocks(fake_mongo, monkeypatch):
    """Stub out every heavy step function on the orchestrator module.

    Returns a MagicMock namespace so tests can inspect call counts.
    """
    calls = MagicMock()

    async def _fake_extract(job):
        calls.extract(job)
        return {"markdown": "# hi\n\nsome content",
                "meta": {}, "images": []}

    async def _fake_chunk(job, extraction):
        calls.chunk(job, extraction)
        parents = [{
            "chunk_id": "p0", "collection_id": job["collection_id"],
            "resource_id": job["resource_id"], "user_id": job.get("user_id", ""),
            "index": 0, "level": "parent", "content": "hi",
            "tokens": 5, "anchor": {}, "modality": "text",
            "retrieval_mode": "semantic", "labels": [], "topics": [],
            "attachments": [],
        }]
        segments = [{
            "segment_id": "s0", "parent_chunk_id": "p0",
            "collection_id": job["collection_id"],
            "resource_id": job["resource_id"], "user_id": job.get("user_id", ""),
            "index": 0, "content": "hi", "tokens": 5, "questions": [],
            "anchor": {}, "modality": "text", "retrieval_mode": "semantic",
            "topics": [], "embedding": None,
        }]
        return parents, segments

    async def _fake_classify(parents):
        calls.classify(parents)
        out = []
        for p in parents:
            p["topics"] = ["mocked-topic"]
            p["labels"] = ["concept"]
            out.append({"topics": p["topics"], "labels": p["labels"]})
        return out

    async def _fake_embed(segments):
        calls.embed(segments)
        for s in segments:
            s["embedding"] = [0.0] * 1536
        return True

    async def _fake_store(job, result):
        calls.store(job, result)
        # Also write a cheap parent doc so downstream code sees it.
        parents = result.get("chunks", [])
        if parents:
            await fake_mongo.byo_chunks.insert_many(
                [dict(p, resource_id=job["resource_id"],
                      collection_id=job["collection_id"]) for p in parents]
            )

    monkeypatch.setattr(orch, "_step_extract", _fake_extract)
    monkeypatch.setattr(orch, "_step_chunk", _fake_chunk)
    monkeypatch.setattr(orch, "_step_classify", _fake_classify)
    monkeypatch.setattr(orch, "_step_embed", _fake_embed)
    monkeypatch.setattr(orch, "_step_store", _fake_store)

    return calls


# ── submit_processing_job ─────────────────────────────────────────────


class TestSubmitJob:

    async def test_creates_queued_job(self, fake_mongo):
        # Seed resource so the status update finds something.
        await fake_mongo.byo_resources.insert_one(
            {"resource_id": "R1", "status": "queued"}
        )
        job_id = await submit_processing_job("R1", "C1", "U1", meta={"mime_type": "text/plain"})
        assert isinstance(job_id, str) and len(job_id) > 10
        job = await fake_mongo.byo_jobs.find_one({"job_id": job_id})
        assert job is not None
        assert job["state"] == JobState.QUEUED
        assert job["step_index"] == 0
        assert job["retries"] == 0
        assert job["resource_id"] == "R1"
        assert job["collection_id"] == "C1"
        assert job["user_id"] == "U1"

    async def test_sets_resource_to_processing(self, fake_mongo):
        await fake_mongo.byo_resources.insert_one(
            {"resource_id": "R2", "status": "queued"}
        )
        await submit_processing_job("R2", "C1", "U1")
        res = await fake_mongo.byo_resources.find_one({"resource_id": "R2"})
        assert res["status"] == "processing"

    async def test_job_id_is_unique(self, fake_mongo):
        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        ids = set()
        for _ in range(5):
            ids.add(await submit_processing_job("R1", "C1", "U1"))
        assert len(ids) == 5


# ── get_job_status ────────────────────────────────────────────────────


class TestGetJobStatus:
    async def test_returns_status_dict(self, fake_mongo):
        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        job_id = await submit_processing_job("R1", "C1", "U1")
        status = await get_job_status(job_id)
        assert status is not None
        assert status["state"] == JobState.QUEUED

    async def test_none_when_unknown(self, fake_mongo):
        assert await get_job_status("no-such-job") is None


# ── _claim_job ────────────────────────────────────────────────────────


class TestClaimJob:

    async def test_claims_queued_job(self, fake_mongo):
        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        await submit_processing_job("R1", "C1", "U1")
        db = fake_mongo
        job = await _claim_job(db)
        assert job is not None
        assert job["resource_id"] == "R1"

    async def test_sets_lock_fields(self, fake_mongo):
        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        jid = await submit_processing_job("R1", "C1", "U1")
        await _claim_job(fake_mongo)
        job = await fake_mongo.byo_jobs.find_one({"job_id": jid})
        assert job["locked_by"] is not None
        assert job["lock_expires"] is not None

    async def test_second_claim_skips_locked(self, fake_mongo):
        """A job locked by an unexpired lock should not be re-claimed."""
        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        await submit_processing_job("R1", "C1", "U1")
        first = await _claim_job(fake_mongo)
        assert first is not None
        # Refresh the first job's lock so it hasn't expired.
        second = await _claim_job(fake_mongo)
        # Same job won't come back because it now has locked_by=WORKER_ID
        # and its lock_expires is in the future.
        if second is not None:
            assert second["job_id"] != first["job_id"]
        else:
            assert second is None

    async def test_expired_lock_reclaimable(self, fake_mongo):
        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        jid = await submit_processing_job("R1", "C1", "U1")
        # Manually set an expired lock.
        past = datetime.utcnow() - timedelta(seconds=1)
        await fake_mongo.byo_jobs.update_one(
            {"job_id": jid},
            {"$set": {"locked_by": "ghost", "lock_expires": past}},
        )
        job = await _claim_job(fake_mongo)
        assert job is not None
        assert job["job_id"] == jid

    async def test_no_job_available(self, fake_mongo):
        job = await _claim_job(fake_mongo)
        assert job is None


# ── _process_job: happy path state transitions ────────────────────────


class TestProcessJobStates:

    async def test_full_pipeline_completes(self, fake_mongo, wired_mocks):
        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        await fake_mongo.collections.insert_one({"collection_id": "C1"})
        jid = await submit_processing_job(
            "R1", "C1", "U1", meta={"mime_type": "text/plain"}
        )
        job = await _claim_job(fake_mongo)

        await _process_job(job)

        final = await fake_mongo.byo_jobs.find_one({"job_id": jid})
        assert final["state"] == JobState.COMPLETE
        assert final["progress"] == 1.0
        assert final["completed_at"] is not None
        # Resource advanced to ready.
        res = await fake_mongo.byo_resources.find_one({"resource_id": "R1"})
        assert res["status"] == "ready"

    async def test_each_step_invoked_once(self, fake_mongo, wired_mocks):
        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        await fake_mongo.collections.insert_one({"collection_id": "C1"})
        await submit_processing_job("R1", "C1", "U1", meta={"mime_type": "text/plain"})
        job = await _claim_job(fake_mongo)
        await _process_job(job)

        assert wired_mocks.extract.call_count == 1
        assert wired_mocks.chunk.call_count == 1
        assert wired_mocks.classify.call_count == 1
        assert wired_mocks.embed.call_count == 1
        assert wired_mocks.store.call_count == 1

    async def test_pipeline_steps_order(self):
        """Sanity: PIPELINE_STEPS matches the expected state machine."""
        assert PIPELINE_STEPS == [
            JobState.EXTRACTING,
            JobState.CHUNKING,
            JobState.CLASSIFYING,
            JobState.EMBEDDING,
            JobState.STORING,
        ]


# ── _process_job: failure handling ────────────────────────────────────


class TestProcessJobRetries:

    async def test_failure_increments_retries(self, fake_mongo, wired_mocks, monkeypatch):
        # Make chunk raise on first call.
        async def _boom(job, extraction):
            raise RuntimeError("chunk failed")
        monkeypatch.setattr(orch, "_step_chunk", _boom)

        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        await fake_mongo.collections.insert_one({"collection_id": "C1"})
        jid = await submit_processing_job("R1", "C1", "U1", meta={"mime_type": "text/plain"})
        job = await _claim_job(fake_mongo)
        await _process_job(job)

        final = await fake_mongo.byo_jobs.find_one({"job_id": jid})
        # After the first failure, retries incremented, state is still
        # the in-flight step ("chunking") and locked_by is cleared.
        assert final["retries"] == 1
        assert final["state"] != JobState.FAILED
        assert final["state"] != JobState.COMPLETE
        assert final["locked_by"] is None
        assert "chunk failed" in (final.get("error") or "")

    async def test_exhausted_retries_moves_to_failed(self, fake_mongo, wired_mocks, monkeypatch):
        async def _boom(job, extraction):
            raise RuntimeError("always fails")
        monkeypatch.setattr(orch, "_step_chunk", _boom)

        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        await fake_mongo.collections.insert_one({"collection_id": "C1"})
        jid = await submit_processing_job("R1", "C1", "U1", meta={"mime_type": "text/plain"})
        # Force retries to max so one more failure trips FAILED.
        await fake_mongo.byo_jobs.update_one(
            {"job_id": jid}, {"$set": {"retries": 3}}
        )
        job = await _claim_job(fake_mongo)
        await _process_job(job)

        final = await fake_mongo.byo_jobs.find_one({"job_id": jid})
        assert final["state"] == JobState.FAILED
        assert "always fails" in final["error"]
        res = await fake_mongo.byo_resources.find_one({"resource_id": "R1"})
        assert res["status"] == "error"

    async def test_resume_skips_completed_steps(self, fake_mongo, wired_mocks, monkeypatch):
        """step_index lets _process_job resume past finished steps."""
        await fake_mongo.byo_resources.insert_one({"resource_id": "R1"})
        await fake_mongo.collections.insert_one({"collection_id": "C1"})
        jid = await submit_processing_job("R1", "C1", "U1", meta={"mime_type": "text/plain"})

        # Pretend extract + chunk already ran: step_index=2 means we start
        # at CLASSIFYING.
        await fake_mongo.byo_jobs.update_one(
            {"job_id": jid},
            {"$set": {
                "step_index": 2,
                "result": {
                    "extraction": {"markdown": "hi", "meta": {}, "images": []},
                    "chunks": [{
                        "chunk_id": "p0", "collection_id": "C1",
                        "resource_id": "R1", "user_id": "U1",
                        "index": 0, "level": "parent", "content": "hi",
                        "tokens": 5, "anchor": {}, "modality": "text",
                        "retrieval_mode": "semantic", "labels": [],
                        "topics": [], "attachments": [],
                    }],
                    "segments": [{
                        "segment_id": "s0", "parent_chunk_id": "p0",
                        "collection_id": "C1", "resource_id": "R1",
                        "user_id": "U1", "index": 0, "content": "hi",
                        "tokens": 5, "questions": [], "anchor": {},
                        "modality": "text", "retrieval_mode": "semantic",
                        "topics": [], "embedding": None,
                    }],
                },
            }},
        )
        job = await _claim_job(fake_mongo)
        await _process_job(job)

        # Extract + chunk MUST NOT have run again; classify/embed/store did.
        assert wired_mocks.extract.call_count == 0
        assert wired_mocks.chunk.call_count == 0
        assert wired_mocks.classify.call_count == 1
        assert wired_mocks.embed.call_count == 1
        assert wired_mocks.store.call_count == 1
        final = await fake_mongo.byo_jobs.find_one({"job_id": jid})
        assert final["state"] == JobState.COMPLETE
