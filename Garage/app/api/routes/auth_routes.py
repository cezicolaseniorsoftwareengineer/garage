"""Authentication API routes -- register, login, refresh, profile."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import os

from app.domain.user import User
from app.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.infrastructure.auth.password import (
    hash_password,
    verify_password,
    verify_legacy_sha256,
    is_bcrypt_hash,
)
from app.infrastructure.auth.bruteforce import record_failed, is_blocked, clear_failed
from app.infrastructure.audit import log_event as audit_log
from app.infrastructure.auth.dependencies import get_current_user


router = APIRouter(prefix="/api/auth", tags=["auth"])

_user_repo = None
_events = None


def init_auth_routes(user_repo, event_service=None):
    global _user_repo, _events
    _user_repo = user_repo
    _events = event_service


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=100)
    username: str = Field(..., min_length=3, max_length=30)
    email: str = Field(..., min_length=5, max_length=120)
    whatsapp: str = Field(..., min_length=10, max_length=20)
    profession: str = Field(..., pattern="^(autonomo|estudante|empresario)$")
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register")
def api_register(req: RegisterRequest):
    """Register a new user account. Returns JWT tokens."""
    if _user_repo.exists_username(req.username):
        raise HTTPException(status_code=409, detail="Nome de usuario ja existe.")

    if _user_repo.exists_email(req.email):
        raise HTTPException(status_code=409, detail="Email ja cadastrado.")

    if hasattr(_user_repo, "exists_full_name") and _user_repo.exists_full_name(req.full_name):
        raise HTTPException(status_code=409, detail="Este nome ja esta em uso por outro usuario.")

    pwd_hash = hash_password(req.password)

    user = User(
        full_name=req.full_name,
        username=req.username,
        email=req.email,
        whatsapp=req.whatsapp,
        profession=req.profession,
        password_hash=pwd_hash,
        salt="bcrypt",
    )

    _user_repo.save(user)

    # Assign role claim for admin users if configured
    admin_email = os.environ.get("ADMIN_EMAIL", "cezicolatecnologia@gmail.com")
    role = "admin" if user.email == admin_email else None
    access_token = create_access_token(user.id, user.username, role=role)
    refresh_token = create_refresh_token(user.id)

    if _events:
        _events.log("user_registered", user_id=user.id)
    try:
        audit_log("user_registered", user.id, {"username": user.username, "email": user.email})
    except Exception:
        pass

    return {
        "success": True,
        "message": "Cadastro realizado com sucesso.",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user.to_public_dict(),
    }


@router.post("/login")
def api_login(req: LoginRequest):
    """Authenticate user. Returns JWT tokens. Upgrades legacy hashes."""
    # Simple brute-force protection by username
    if is_blocked(req.username):
        raise HTTPException(status_code=429, detail="Too many failed login attempts. Try later.")

    user = _user_repo.find_by_username(req.username)
    if not user:
        record_failed(req.username)
        raise HTTPException(status_code=401, detail="Usuario ou senha incorretos.")

    user_data = user.to_dict()
    stored_hash = user_data["password_hash"]

    # Verify with bcrypt or legacy SHA-256
    if is_bcrypt_hash(stored_hash):
        valid = verify_password(req.password, stored_hash)
    else:
        valid = verify_legacy_sha256(req.password, user_data["salt"], stored_hash)
        # Transparent upgrade to bcrypt on successful legacy auth
        if valid:
            new_hash = hash_password(req.password)
            try:
                _user_repo.update_password(user_data["id"], new_hash, "bcrypt")
            except (AttributeError, Exception):
                pass

    if not valid:
        record_failed(req.username)
        raise HTTPException(status_code=401, detail="Usuario ou senha incorretos.")

    # Attach role claim if the user is configured as admin
    admin_email = os.environ.get("ADMIN_EMAIL", "cezicolatecnologia@gmail.com")
    user_obj = _user_repo.find_by_id(user_data["id"]) if hasattr(_user_repo, "find_by_id") else None
    role = "admin" if (user_obj and getattr(user_obj, "email", None) == admin_email) else None
    access_token = create_access_token(user_data["id"], user_data["username"], role=role)
    refresh_token = create_refresh_token(user_data["id"])

    # Update last login timestamp
    try:
        _user_repo.update_last_login(user_data["id"])
    except (AttributeError, Exception):
        pass

    # successful login: clear brute-force counters
    try:
        clear_failed(req.username)
    except Exception:
        pass

    if _events:
        _events.log("user_logged_in", user_id=user_data["id"])
    try:
        audit_log("user_logged_in", user_data["id"], {"username": user_data.get("username")})
    except Exception:
        pass

    return {
        "success": True,
        "message": "Login realizado com sucesso.",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user.to_public_dict(),
    }


@router.post("/refresh")
def api_refresh(req: RefreshRequest):
    """Exchange a valid refresh token for a new access token."""
    payload = verify_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token invalido ou expirado.")

    user_id = payload["sub"]
    user = _user_repo.find_by_id(user_id) if hasattr(_user_repo, "find_by_id") else None
    username = user.username if user else payload.get("username", "")

    admin_email = os.environ.get("ADMIN_EMAIL", "cezicolatecnologia@gmail.com")
    role = "admin" if (user and getattr(user, "email", None) == admin_email) else None
    access_token = create_access_token(user_id, username, role=role)
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.get("/me")
def api_me(current_user: dict = Depends(get_current_user)):
    """Return authenticated user profile."""
    user = None
    if hasattr(_user_repo, "find_by_id"):
        user = _user_repo.find_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    return user.to_public_dict()
