"""FastAPI authentication dependencies (Bearer JWT)."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.infrastructure.auth.jwt_handler import verify_token

_security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """Extract and validate the JWT from the Authorization header.

    Returns the decoded payload dict with at least ``sub`` (user id)
    and ``username``.  Raises 401 on missing / invalid / expired tokens.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Access token required.",
        )

    return payload


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict | None:
    """Same as get_current_user but returns None instead of raising."""
    if not credentials:
        return None
    payload = verify_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        return None
    return payload
