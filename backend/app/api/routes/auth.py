"""Auth routes — MongoDB login/signup, issue mockup JWT."""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt, JWTError

from app.core.config import settings
from app.core.rate_limit import check_rate_limit_auth as check_rate_limit
from app.services.session.user_service import create_user, get_user_by_email, verify_password

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

ALGORITHM = "HS256"


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
        # Fall back to ?token= query param (needed for EventSource which can't set headers)
        token = request.query_params.get("token", "")
        if not token:
            raise HTTPException(status_code=401, detail="Missing authorization token")
    else:
        token = auth[7:]
    claims = decode_mockup_token(token)
    return {"email": claims["sub"], "name": claims.get("name", ""), "role": claims.get("role", "")}


async def get_optional_user(request: Request) -> dict:
    """Auth dependency — requires auth in production, soft fallback for local dev only."""
    try:
        return await get_current_user(request)
    except HTTPException:
        # Only allow anonymous in local dev (no CORS_ORIGINS = no production deployment)
        import os
        if not os.environ.get("CORS_ORIGINS"):
            return {"email": "dev@local", "name": "Dev User", "role": "student"}
        raise


# ─── Routes ──────────────────────────────────────────────

@router.post("/login")
async def login(request: Request, _=Depends(check_rate_limit)):
    """Authenticate against MongoDB users collection, issue a mockup JWT."""
    body = await request.json()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user = await get_user_by_email(email)

    if not user or not user.get("hashed_password"):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_mockup_token(user["email"], user["name"], user.get("role", "student"))

    log.info("User logged in: %s (%s)", user["email"], user["name"])
    return {
        "token": token,
        "user": {"email": user["email"], "name": user["name"], "role": user.get("role", "student")},
    }


@router.post("/signup")
async def signup(request: Request, _=Depends(check_rate_limit)):
    """Create a new user account in MongoDB and issue a JWT."""
    body = await request.json()
    name = body.get("name", "").strip()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = await get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = await create_user(name, email, password)

    token = create_mockup_token(user["email"], user["name"], user.get("role", "student"))

    log.info("User signed up: %s (%s)", user["email"], user["name"])
    return {
        "token": token,
        "user": {"email": user["email"], "name": user["name"], "role": user.get("role", "student")},
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return the current user profile from the mockup JWT."""
    return user


@router.post("/logout")
async def logout():
    """Logout is a client-side operation (clear localStorage). This is a no-op."""
    return {"ok": True}
