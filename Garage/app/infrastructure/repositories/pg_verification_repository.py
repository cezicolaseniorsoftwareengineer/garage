"""PostgreSQL-backed email verification token repository."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.infrastructure.database.models import EmailVerificationModel, UserModel


_CODE_BYTES = 3          # 6 hex digits → 6-digit decimal code
_CODE_TTL_MINUTES = 30


def _new_code() -> str:
    """Generate a cryptographically secure 6-digit decimal OTP."""
    return str(secrets.randbelow(900_000) + 100_000)  # always 6 digits


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class PgVerificationRepository:
    """Create, validate, and consume email OTP tokens stored on PostgreSQL."""

    def __init__(self, session_factory):
        self._sf = session_factory

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create_code(self, user_id: str) -> str:
        """Invalidate old tokens, generate a new 6-digit code, persist hash.

        Returns the *plaintext* code to be sent via email (never stored).
        """
        code = _new_code()
        token_hash = _hash_code(code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_CODE_TTL_MINUTES)

        with self._sf() as session:
            # Invalidate every previous unused token for this user
            old = (
                session.query(EmailVerificationModel)
                .filter(
                    EmailVerificationModel.user_id == user_id,
                    EmailVerificationModel.used_at.is_(None),
                )
                .all()
            )
            for row in old:
                row.used_at = datetime.now(timezone.utc)  # mark consumed/invalidated

            session.add(
                EmailVerificationModel(
                    user_id=user_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                )
            )
            session.commit()

        return code

    def mark_verified(self, user_id: str, code: str) -> bool:
        """Check *code* against the latest valid token for *user_id*.

        If valid: marks the token as used, sets user.email_verified = True.
        Returns True on success, False if code is wrong/expired/already used.
        """
        token_hash = _hash_code(code)
        now = datetime.now(timezone.utc)

        with self._sf() as session:
            token = (
                session.query(EmailVerificationModel)
                .filter(
                    EmailVerificationModel.user_id == user_id,
                    EmailVerificationModel.token_hash == token_hash,
                    EmailVerificationModel.used_at.is_(None),
                    EmailVerificationModel.expires_at > now,
                )
                .order_by(EmailVerificationModel.created_at.desc())
                .first()
            )
            if not token:
                return False

            token.used_at = now
            # Mark user as verified
            user_row = session.get(UserModel, user_id)
            if user_row:
                user_row.email_verified = True
            session.commit()

        return True

    def has_pending(self, user_id: str) -> bool:
        """Return True if user has at least one unexpired, unused code."""
        now = datetime.now(timezone.utc)
        with self._sf() as session:
            return bool(
                session.query(EmailVerificationModel)
                .filter(
                    EmailVerificationModel.user_id == user_id,
                    EmailVerificationModel.used_at.is_(None),
                    EmailVerificationModel.expires_at > now,
                )
                .first()
            )

    def get_user_id_by_email(self, email: str) -> Optional[str]:
        """Helper: look up user_id from email for the resend flow."""
        target = email.lower().strip()
        with self._sf() as session:
            row = session.query(UserModel).filter(UserModel.email == target).first()
            return row.id if row else None

    def is_already_verified(self, email: str) -> bool:
        """Return True if the user with *email* already has email_verified=True."""
        target = email.lower().strip()
        with self._sf() as session:
            row = session.query(UserModel).filter(UserModel.email == target).first()
            return bool(row and row.email_verified)
