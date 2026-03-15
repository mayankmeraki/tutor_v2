"""User service — MongoDB-based user CRUD for tutor_v2.users."""

import logging
from datetime import datetime, timezone

import bcrypt

from app.core.mongodb import get_tutor_db

log = logging.getLogger(__name__)


# ─── Collection accessor ───────────────────────────────────────────

def _users():
    return get_tutor_db()["users"]


# ─── CRUD ───────────────────────────────────────────────────────────

async def create_user(name: str, email: str, password: str) -> dict:
    """Create a new user with bcrypt-hashed password. Returns the inserted doc."""
    hashed = bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt())
    doc = {
        "name": name.strip(),
        "email": email.strip().lower(),
        "hashed_password": hashed.decode("utf-8"),
        "role": "student",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    result = await _users().insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    log.info("User created: %s (%s)", doc["email"], doc["name"])
    return doc


async def get_user_by_email(email: str) -> dict | None:
    """Find a user by email (case-insensitive, stored lowercase)."""
    doc = await _users().find_one({"email": email.strip().lower()})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))


async def ensure_indexes():
    """Create unique index on email field."""
    await _users().create_index("email", unique=True)
    log.info("User indexes ensured")
