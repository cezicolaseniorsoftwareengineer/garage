"""Authentication API routes -- register, login, refresh, profile."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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

    access_token = create_access_token(user.id, user.username)
    refresh_token = create_refresh_token(user.id)

    if _events:
        _events.log("user_registered", user_id=user.id)

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
    user = _user_repo.find_by_username(req.username)
    if not user:
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
        raise HTTPException(status_code=401, detail="Usuario ou senha incorretos.")

    access_token = create_access_token(user_data["id"], user_data["username"])
    refresh_token = create_refresh_token(user_data["id"])

    # Update last login timestamp
    try:
        _user_repo.update_last_login(user_data["id"])
    except (AttributeError, Exception):
        pass

    if _events:
        _events.log("user_logged_in", user_id=user_data["id"])

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

    access_token = create_access_token(user_id, username)
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
