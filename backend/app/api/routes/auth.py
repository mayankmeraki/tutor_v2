"""Auth routes — direct DB login, issue mockup JWT."""

import logging
from datetime import datetime, timezone, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import Users

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

ALGORITHM = "HS256"


def _verify_password(plain: str, hashed: str) -> bool:
    pw = plain.encode("utf-8")[:72]
    return bcrypt.checkpw(pw, hashed.encode("utf-8"))


# ─── JWT helpers ──────────────────────────────────────────

def create_mockup_token(email: str, name: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.MOCKUP_JWT_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "name": name,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.MOCKUP_JWT_SECRET, algorithm=ALGORITHM)


def decode_mockup_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.MOCKUP_JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ─── Dependency ───────────────────────────────────────────

async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token")
    token = auth[7:]
    claims = decode_mockup_token(token)
    return {"email": claims["sub"], "name": claims.get("name", ""), "role": claims.get("role", "")}


# ─── Routes ──────────────────────────────────────────────

@router.post("/login")
async def login(request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate against the users table in PostgreSQL, issue a mockup JWT."""
    body = await request.json()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    # Query user from PostgreSQL
    result = await db.execute(select(Users).where(Users.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not _verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Issue mockup JWT
    token = create_mockup_token(user.email, user.name, user.role.value)

    log.info("User logged in: %s (%s)", user.email, user.name)
    return {
        "token": token,
        "user": {"email": user.email, "name": user.name, "role": user.role.value},
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return the current user profile from the mockup JWT."""
    return user


@router.post("/logout")
async def logout():
    """Logout is a client-side operation (clear localStorage). This is a no-op."""
    return {"ok": True}
