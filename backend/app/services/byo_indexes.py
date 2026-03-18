"""MongoDB index creation for BYO Material collections.

All BYO collections live in the 'capacity' database alongside existing
course content. Student progress lives in 'tutor_v2'.
"""

from __future__ import annotations

import logging

from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core.mongodb import get_mongo_db, get_tutor_db

log = logging.getLogger(__name__)


async def ensure_byo_indexes() -> None:
    """Create indexes for all BYO Material collections. Idempotent."""
    db = get_mongo_db()
    tutor_db = get_tutor_db()

    # ── content_collections ──────────────────────────────────────────
    await db.content_collections.create_indexes([
        IndexModel([("userId", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
    ])

    # ── materials ────────────────────────────────────────────────────
    await db.materials.create_indexes([
        IndexModel([("collectionId", ASCENDING)]),
        IndexModel([("collectionId", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("source._originalUrl", ASCENDING)], sparse=True),
    ])

    # ── chunks ───────────────────────────────────────────────────────
    await db.chunks.create_indexes([
        IndexModel([("collectionId", ASCENDING)]),
        IndexModel([("materialId", ASCENDING)]),
        IndexModel([("collectionId", ASCENDING), ("materialId", ASCENDING), ("index", ASCENDING)]),
    ])

    # ── transcripts ──────────────────────────────────────────────────
    await db.transcripts.create_indexes([
        IndexModel([("materialId", ASCENDING)], unique=True),
        IndexModel([("collectionId", ASCENDING)]),
    ])

    # ── extracted_frames ─────────────────────────────────────────────
    await db.extracted_frames.create_indexes([
        IndexModel([("materialId", ASCENDING)]),
        IndexModel([("collectionId", ASCENDING)]),
        IndexModel([("materialId", ASCENDING), ("timestamp", ASCENDING)]),
        IndexModel([("classification", ASCENDING)]),
    ])

    # ── topic_index ──────────────────────────────────────────────────
    await db.topic_index.create_indexes([
        IndexModel([("collectionId", ASCENDING)]),
        IndexModel([("collectionId", ASCENDING), ("order", ASCENDING)]),
    ])

    # ── concept_graph ────────────────────────────────────────────────
    await db.concept_graph.create_indexes([
        IndexModel([("collectionId", ASCENDING)]),
        IndexModel([("normalizedName", ASCENDING), ("collectionId", ASCENDING)]),
        IndexModel([("aliases", ASCENDING)]),
    ])

    # ── exercise_index ───────────────────────────────────────────────
    await db.exercise_index.create_indexes([
        IndexModel([("collectionId", ASCENDING)]),
        IndexModel([("collectionId", ASCENDING), ("difficulty", ASCENDING)]),
        IndexModel([("topicId", ASCENDING)]),
        IndexModel([("concepts", ASCENDING)]),
    ])

    # ── difficulty_map ───────────────────────────────────────────────
    await db.difficulty_map.create_indexes([
        IndexModel([("collectionId", ASCENDING)], unique=True),
    ])

    # ── asset_index ──────────────────────────────────────────────────
    await db.asset_index.create_indexes([
        IndexModel([("collectionId", ASCENDING)]),
        IndexModel([("topicId", ASCENDING)]),
        IndexModel([("type", ASCENDING)]),
    ])

    # ── flow_map ─────────────────────────────────────────────────────
    await db.flow_map.create_indexes([
        IndexModel([("collectionId", ASCENDING)], unique=True),
    ])

    # ── student_progress (in tutor_v2 database) ──────────────────────
    await tutor_db.student_progress.create_indexes([
        IndexModel([("collectionId", ASCENDING), ("userEmail", ASCENDING)], unique=True),
        IndexModel([("userEmail", ASCENDING)]),
    ])

    log.info("BYO Material indexes ensured")
