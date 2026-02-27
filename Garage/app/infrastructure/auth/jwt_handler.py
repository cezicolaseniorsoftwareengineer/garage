"""JWT token creation and verification (HS256)."""
import os
import secrets as _secrets
import logging
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

SECRET_KEY = os.environ.get("JWT_SECRET_KEY")

# Fail-fast: a missing secret key is a critical misconfiguration in any environment.
# A None key makes python-jose sign tokens with the string "None" — all tokens
# become universally forgeable. There is no safe dev/prod distinction here.
if not SECRET_KEY:  # pragma: no cover
    raise RuntimeError(
        "Missing JWT_SECRET_KEY environment variable. "
        "Add JWT_SECRET_KEY=<strong-random-value> to your .env file before starting."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(user_id: str, username: str, role: str | None = None) -> str:
    """Create a short-lived access token (1 h default)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "username": username,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if role:
        payload["role"] = role
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token (7 d default)."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Decode and validate a JWT. Returns the payload dict or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") is None:
            return None
        # Check revocation for refresh tokens
        if payload.get("type") == "refresh" and is_refresh_revoked(token):
            return None
        return payload
    except JWTError:
        return None


# Simple in-memory refresh token revocation set (process-lifetime)
_revoked_refresh_tokens: set = set()


def revoke_refresh_token(token: str) -> None:
    """Mark a refresh token as revoked for the local process lifetime."""
    try:
        _revoked_refresh_tokens.add(token)
    except Exception:  # pragma: no cover
        pass


def is_refresh_revoked(token: str) -> bool:
    return token in _revoked_refresh_tokens


# Legacy env-specific guard removed: fail-fast is now unconditional (see above).

# Development fallback: generate a random secret so the app can run locally.
if not SECRET_KEY:  # pragma: no cover
    SECRET_KEY = _secrets.token_urlsafe(32)
    logging.warning(
        "JWT_SECRET_KEY not set — using a generated development secret. "
        "Set JWT_SECRET_KEY or set ENV=production to require it."
    )
