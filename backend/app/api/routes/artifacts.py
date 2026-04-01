"""Learning aids / artifacts API.

Artifacts are created by Euler (flashcards, study plans, revision notes, etc.)
and stored in MongoDB. This API lets students list, view, update, and track
spaced repetition progress on their artifacts.
"""

from fastapi import APIRouter, HTTPException, Request
from app.api.routes.auth import get_optional_user
from app.core.mongodb import get_mongo_db

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


@router.get("")
async def list_artifacts(request: Request, user: dict = None):
    """List all artifacts for the current user."""
    user = await get_optional_user(request)
    db = get_mongo_db()
    email = user.get("email", "")

    cursor = db.artifacts.find(
        {"user_id": email},
        {"_id": 0},
    ).sort("created_at", -1).limit(50)

    artifacts = []
    async for doc in cursor:
        # Add preview info
        content = doc.get("content", {})
        preview = {}
        if doc.get("type") == "flashcards" and content.get("cards"):
            preview = {"card_count": len(content["cards"]), "sample": content["cards"][0] if content["cards"] else {}}
        elif content.get("markdown"):
            preview = {"text": content["markdown"][:150]}
        elif content.get("steps"):
            preview = {"step_count": len(content["steps"])}

        artifacts.append({
            "artifact_id": doc.get("artifact_id"),
            "type": doc.get("type"),
            "title": doc.get("title"),
            "preview": preview,
            "created_at": str(doc.get("created_at", "")),
            "sr_stats": doc.get("sr_stats"),  # spaced repetition stats
        })

    return artifacts


@router.get("/{artifact_id}")
async def get_artifact(artifact_id: str, request: Request):
    """Get full artifact content."""
    user = await get_optional_user(request)
    db = get_mongo_db()

    doc = await db.artifacts.find_one(
        {"artifact_id": artifact_id, "user_id": user.get("email", "")},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return doc


@router.patch("/{artifact_id}")
async def update_artifact(artifact_id: str, request: Request):
    """Update artifact content or metadata."""
    user = await get_optional_user(request)
    db = get_mongo_db()
    body = await request.json()

    update = {}
    if "title" in body:
        update["title"] = body["title"]
    if "content" in body:
        update["content"] = body["content"]
    if "tags" in body:
        update["tags"] = body["tags"]

    if not update:
        return {"ok": True}

    result = await db.artifacts.update_one(
        {"artifact_id": artifact_id, "user_id": user.get("email", "")},
        {"$set": update},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"ok": True}


@router.delete("/{artifact_id}")
async def delete_artifact(artifact_id: str, request: Request):
    """Delete an artifact."""
    user = await get_optional_user(request)
    db = get_mongo_db()

    result = await db.artifacts.delete_one(
        {"artifact_id": artifact_id, "user_id": user.get("email", "")}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"ok": True}


@router.post("/{artifact_id}/sr")
async def update_spaced_repetition(artifact_id: str, request: Request):
    """Update spaced repetition state for a flashcard artifact.

    Body: { card_index: int, rating: "again"|"hard"|"good"|"easy" }

    Uses a simplified SM-2 algorithm:
    - again: reset interval to 1 day
    - hard: interval * 1.2
    - good: interval * 2.5
    - easy: interval * 4
    """
    user = await get_optional_user(request)
    db = get_mongo_db()
    body = await request.json()

    card_index = body.get("card_index", 0)
    rating = body.get("rating", "good")

    from datetime import datetime, timedelta

    # Get current SR state
    doc = await db.artifacts.find_one(
        {"artifact_id": artifact_id, "user_id": user.get("email", "")},
        {"sr_state": 1, "content.cards": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Artifact not found")

    sr_state = doc.get("sr_state", {})
    card_key = str(card_index)
    card_sr = sr_state.get(card_key, {"interval": 1, "ease": 2.5, "reviews": 0})

    # Apply SM-2-like algorithm
    interval = card_sr["interval"]
    ease = card_sr["ease"]

    if rating == "again":
        interval = 1
        ease = max(1.3, ease - 0.2)
    elif rating == "hard":
        interval = max(1, int(interval * 1.2))
        ease = max(1.3, ease - 0.1)
    elif rating == "good":
        interval = max(1, int(interval * ease))
    elif rating == "easy":
        interval = max(1, int(interval * ease * 1.5))
        ease = min(3.0, ease + 0.1)

    now = datetime.utcnow()
    card_sr = {
        "interval": interval,
        "ease": round(ease, 2),
        "reviews": card_sr["reviews"] + 1,
        "last_review": now,
        "next_review": now + timedelta(days=interval),
    }
    sr_state[card_key] = card_sr

    # Compute aggregate stats
    total_cards = len(doc.get("content", {}).get("cards", []))
    reviewed = len([k for k, v in sr_state.items() if v.get("reviews", 0) > 0])
    due_now = len([k for k, v in sr_state.items()
                   if v.get("next_review") and v["next_review"] <= now])

    sr_stats = {
        "total_cards": total_cards,
        "reviewed": reviewed,
        "due_now": due_now,
        "mastered": len([k for k, v in sr_state.items() if v.get("interval", 0) >= 7]),
    }

    await db.artifacts.update_one(
        {"artifact_id": artifact_id},
        {"$set": {"sr_state": sr_state, "sr_stats": sr_stats}},
    )

    return {"ok": True, "card_sr": card_sr, "sr_stats": sr_stats}
