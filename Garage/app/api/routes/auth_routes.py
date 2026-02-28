"""Authentication API routes -- register, login, refresh, profile."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import os

from app.domain.user import User
from app.infrastructure.auth.admin_utils import configured_admin_emails, is_admin_email, is_admin_username
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
from app.infrastructure.auth.email_sender import send_verification_email
from app.infrastructure.audit import log_event as audit_log
from app.infrastructure.auth.dependencies import get_current_user


router = APIRouter(prefix="/api/auth", tags=["auth"])

_user_repo = None
_events = None
_verification_repo = None
_pending_repo = None   # PgPendingRepository — set when PostgreSQL is active


def init_auth_routes(user_repo, event_service=None, verification_repo=None, pending_repo=None):
    global _user_repo, _events, _verification_repo, _pending_repo
    _user_repo = user_repo
    _events = event_service
    _verification_repo = verification_repo
    _pending_repo = pending_repo


# Admin e-mail helpers are now shared via admin_utils to avoid drift.
# configured_admin_emails and is_admin_email imported above.
_configured_admin_emails = configured_admin_emails
_is_admin_email = is_admin_email


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


class VerifyEmailRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendVerificationRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mask_email(email: str) -> str:
    """Return a partially hidden email (e.g. 'jo**@gmail.com') for safe display."""
    try:
        local, domain = email.split("@", 1)
        visible = local[:2] if len(local) >= 2 else local[0]
        return f"{visible}{'*' * max(1, len(local) - 2)}@{domain}"
    except Exception:
        return email


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register")
def api_register(req: RegisterRequest):
    """Register a new user account.

    If verification is enabled (verification_repo wired), returns
    ``requires_verification=True`` and sends a 6-digit OTP to the given email.
    Otherwise (dev/JSON mode) behaves as before and returns JWT tokens directly.
    """
    # Check conflicts in *users* table
    if _user_repo.exists_username(req.username):
        raise HTTPException(status_code=409, detail="Nome de usuario ja existe.")
    if _user_repo.exists_email(req.email):
        raise HTTPException(status_code=409, detail="Email ja cadastrado.")
    if hasattr(_user_repo, "exists_full_name") and _user_repo.exists_full_name(req.full_name):
        raise HTTPException(status_code=409, detail="Este nome ja esta em uso por outro usuario.")

    # Check conflicts in *pending_registrations* (so someone can't grab a taken username/email
    # while the original requester is still in the verification window)
    if _pending_repo is not None:
        if _pending_repo.exists_username(req.username):
            raise HTTPException(status_code=409, detail="Nome de usuario ja existe.")
        if _pending_repo.exists_email(req.email):
            raise HTTPException(
                status_code=409,
                detail="Email ja cadastrado e aguardando verificacao. Verifique sua caixa de entrada.",
            )

    pwd_hash = hash_password(req.password)

    # ---------------------------------------------------------------------------
    # PostgreSQL mode: save to PENDING staging table (NOT users) until OTP confirmed
    # ---------------------------------------------------------------------------
    if _pending_repo is not None:
        try:
            code = _pending_repo.create_pending(
                full_name=req.full_name,
                username=req.username,
                email=req.email,
                whatsapp=req.whatsapp,
                profession=req.profession,
                password_hash=pwd_hash,
            )
            send_verification_email(req.email, code, req.full_name)
        except Exception as exc:
            import logging
            logging.getLogger("garage.auth").error("Failed to create pending/send email: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="Erro ao enviar e-mail de verificacao. Tente novamente.",
            )

        try:
            audit_log("user_register_pending", req.email, {"username": req.username, "email": req.email})
        except Exception:
            pass

        return {
            "success": True,
            "requires_verification": True,
            "email_hint": _mask_email(req.email),
            "message": (
                "Cadastro iniciado! Enviamos um codigo de 6 digitos para o seu e-mail. "
                "Insira o codigo para concluir o cadastro e entrar no jogo."
            ),
        }

    # ---------------------------------------------------------------------------
    # Dev / JSON fallback: create user directly (no email verification)
    # ---------------------------------------------------------------------------
    user = User(
        full_name=req.full_name,
        username=req.username,
        email=req.email,
        whatsapp=req.whatsapp,
        profession=req.profession,
        password_hash=pwd_hash,
        salt="bcrypt",
        email_verified=True,
    )
    _user_repo.save(user)

    role = "admin" if is_admin_username(user.username) else None
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
    else:  # pragma: no cover — legacy SHA-256 upgrade path
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

    # Block unverified accounts (only when verification is active)
    if _verification_repo is not None and not user.email_verified:
        raise HTTPException(
            status_code=403,
            detail=(
                "E-mail nao verificado. Verifique sua caixa de entrada e insira "
                "o codigo de 6 digitos. Use 'Reenviar codigo' se necessario."
            ),
        )

    # Attach role claim if the user is configured as admin (username-based check)
    role = "admin" if is_admin_username(user_data["username"]) else None
    access_token = create_access_token(user_data["id"], user_data["username"], role=role)
    refresh_token = create_refresh_token(user_data["id"])

    # Update last login timestamp
    try:
        _user_repo.update_last_login(user_data["id"])
    except (AttributeError, Exception):  # pragma: no cover
        pass

    # successful login: clear brute-force counters
    try:
        clear_failed(req.username)
    except Exception:  # pragma: no cover
        pass

    if _events:
        _events.log("user_logged_in", user_id=user_data["id"])
    try:
        audit_log("user_logged_in", user_data["id"], {"username": user_data.get("username")})
    except Exception:  # pragma: no cover
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

    role = "admin" if is_admin_username(username) else None
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


# ---------------------------------------------------------------------------
# Email verification endpoints
# ---------------------------------------------------------------------------

@router.post("/verify-email")
def api_verify_email(req: VerifyEmailRequest):
    """Validate the 6-digit OTP sent after registration.

    In PostgreSQL mode uses the pending_registrations staging table:
      - Validates OTP, promotes record to users table, deletes staging row.
    Fallback (no pending_repo): uses legacy email_verifications table.

    On success returns JWT tokens so the frontend can log the user in directly.
    """
    # ---------------------------------------------------------------------------
    # PostgreSQL / pending_registrations flow  (preferred, secure)
    # ---------------------------------------------------------------------------
    if _pending_repo is not None:
        # Check if user already exists and is verified (e.g. re-submitted form)
        existing = _user_repo.find_by_email(req.email)
        if existing and existing.email_verified:
            raise HTTPException(status_code=409, detail="E-mail ja verificado. Faca login normalmente.")

        # Confirm OTP and atomically promote pending → users
        user = _pending_repo.confirm_and_promote(req.email, req.code, _user_repo)
        if user is None:
            raise HTTPException(
                status_code=400,
                detail="Codigo invalido ou expirado. Solicite um novo codigo e tente novamente.",
            )

        role = "admin" if is_admin_username(user.username) else None
        access_token = create_access_token(user.id, user.username, role=role)
        refresh_token = create_refresh_token(user.id)

        if _events:
            _events.log("user_registered", user_id=user.id)
        try:
            audit_log("email_verified", user.id, {"username": user.username, "email": user.email})
        except Exception:
            pass

        return {
            "success": True,
            "message": "E-mail verificado com sucesso! Bem-vindo ao Garage.",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user.to_public_dict(),
        }

    # ---------------------------------------------------------------------------
    # Legacy fallback: email_verifications table (used when pending_repo is None)
    # ---------------------------------------------------------------------------
    if _verification_repo is None:
        raise HTTPException(status_code=404, detail="Verification not enabled.")

    if _verification_repo.is_already_verified(req.email):
        raise HTTPException(status_code=409, detail="E-mail ja verificado. Faca login normalmente.")

    user = _user_repo.find_by_email(req.email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")

    ok = _verification_repo.mark_verified(user.id, req.code)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Codigo invalido ou expirado. Solicite um novo codigo e tente novamente.",
        )

    user = _user_repo.find_by_id(user.id)

    role = "admin" if is_admin_username(user.username) else None
    access_token = create_access_token(user.id, user.username, role=role)
    refresh_token = create_refresh_token(user.id)

    try:
        audit_log("email_verified", user.id, {"email": user.email})
    except Exception:
        pass

    return {
        "success": True,
        "message": "E-mail verificado com sucesso! Bem-vindo ao Garage.",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user.to_public_dict(),
    }


@router.post("/resend-verification")
def api_resend_verification(req: ResendVerificationRequest):
    """Resend a fresh 6-digit OTP to the given email address.

    Checks both the pending_registrations staging table and (legacy) users table.
    """
    import logging
    _log = logging.getLogger("garage.auth")

    # Security: always return success to avoid email enumeration
    _generic_ok = {
        "success": True,
        "message": "Se este e-mail estiver cadastrado e aguardando verificacao, um novo codigo foi enviado.",
    }

    # ---------------------------------------------------------------------------
    # PostgreSQL / pending_registrations flow
    # ---------------------------------------------------------------------------
    if _pending_repo is not None:
        # Check if already verified in users table (no need to resend)
        existing = _user_repo.find_by_email(req.email)
        if existing and existing.email_verified:
            raise HTTPException(status_code=409, detail="E-mail ja verificado. Faca login normalmente.")

        result = _pending_repo.refresh_code(req.email)
        if result is None:
            # Email not in pending (doesn't exist or never registered) — don't reveal
            return _generic_ok

        code, full_name = result
        try:
            send_verification_email(req.email, code, full_name)
        except Exception as exc:
            _log.error("Resend verification failed: %s", exc)

        return {
            "success": True,
            "email_hint": _mask_email(req.email),
            "message": "Novo codigo enviado para o seu e-mail.",
        }

    # ---------------------------------------------------------------------------
    # Legacy fallback: email_verifications table
    # ---------------------------------------------------------------------------
    if _verification_repo is None:
        raise HTTPException(status_code=404, detail="Verification not enabled.")

    if _verification_repo.is_already_verified(req.email):
        raise HTTPException(status_code=409, detail="E-mail ja verificado. Faca login normalmente.")

    user = _user_repo.find_by_email(req.email)
    if not user:
        return _generic_ok

    try:
        code = _verification_repo.create_code(user.id)
        send_verification_email(user.email, code, user.full_name)
    except Exception as exc:
        logging.getLogger("garage.auth").error("Resend verification failed: %s", exc)

    return {
        "success": True,
        "email_hint": _mask_email(user.email),
        "message": "Novo codigo enviado para o seu e-mail.",
    }
