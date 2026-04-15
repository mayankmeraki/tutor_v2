"""Auth routes — MongoDB login/signup + Google OAuth, issue mockup JWT."""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt, JWTError

from app.core.config import settings
from app.core.rate_limit import check_rate_limit_auth as check_rate_limit
from app.services.session.user_service import (
    create_user, create_user_oauth, get_user_by_email, verify_password,
)

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
    """Email/password signup is disabled — new accounts must use Google OAuth."""
    raise HTTPException(
        status_code=410,
        detail="Email/password signup is no longer available. Please sign up with Google.",
    )


@router.post("/google")
async def google_auth(request: Request, _=Depends(check_rate_limit)):
    """Verify a Google ID token and either log in (if user exists) or sign up.

    Frontend uses Google Identity Services (GSI) to obtain an ID token (JWT
    signed by Google). We verify that token server-side against Google's
    public keys, then issue our own mockup JWT.

    REQUIRES email_verified=true — this is the whole point of using Google:
    we know the email belongs to the human signing up.
    """
    if not settings.GOOGLE_CLIENT_ID_MYPROFESSOR:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")

    body = await request.json()
    credential = body.get("credential", "") or body.get("id_token", "")
    if not credential:
        raise HTTPException(status_code=400, detail="Missing Google credential")

    # Verify the ID token signature, expiry, audience, issuer
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        idinfo = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID_MYPROFESSOR,
            clock_skew_in_seconds=10,
        )
    except ValueError as e:
        log.warning("Google token verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Google credential")

    # Extra safety: enforce issuer (verify_oauth2_token already does, but be explicit)
    if idinfo.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=401, detail="Invalid token issuer")

    # REQUIRE verified email — this is why we use Google
    if not idinfo.get("email_verified"):
        raise HTTPException(
            status_code=403,
            detail="Your Google email is not verified. Please verify it with Google and try again.",
        )

    email = (idinfo.get("email") or "").strip().lower()
    name = (idinfo.get("name") or "").strip()
    picture = idinfo.get("picture", "")

    if not email:
        raise HTTPException(status_code=400, detail="Google did not return an email")

    # Find or create
    user = await get_user_by_email(email)
    if not user:
        user = await create_user_oauth(name=name, email=email, provider="google", picture=picture)
        log.info("Google signup: %s (%s)", email, name)
    else:
        log.info("Google login: %s (%s)", email, name)

    token = create_mockup_token(user["email"], user["name"], user.get("role", "student"))
    return {
        "token": token,
        "user": {
            "email": user["email"],
            "name": user["name"],
            "role": user.get("role", "student"),
            "picture": user.get("picture", picture),
        },
        "isNewUser": user.get("authProvider") == "google" and "hashed_password" not in user,
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return the current user profile from the mockup JWT."""
    return user


@router.post("/logout")
async def logout():
    """Logout is a client-side operation (clear localStorage). This is a no-op."""
    return {"ok": True}
