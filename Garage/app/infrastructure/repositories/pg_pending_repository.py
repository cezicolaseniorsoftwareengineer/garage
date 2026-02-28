"""PostgreSQL-backed pending registration repository.

Stores registration data temporarily until email OTP is confirmed.
On successful verification, promotes the row to the *users* table and
deletes it from this staging table.

Security rationale:
  - Prevents unverified accounts from appearing in admin panels / leaderboards.
  - Limits ghost accounts (OWASP A07 - Identification and Authentication Failures).
  - OTP hash stored as SHA-256 hexdigest — plaintext never persisted.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_

from app.domain.user import User
from app.infrastructure.database.models import PendingRegistrationModel, UserModel, UserMetricsModel


_CODE_TTL_MINUTES = 30


def _new_code() -> str:
    """Cryptographically secure 6-digit decimal OTP."""
    return str(secrets.randbelow(900_000) + 100_000)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class PgPendingRepository:
    """Manage pre-verification registration records."""

    def __init__(self, session_factory):
        self._sf = session_factory

    # ------------------------------------------------------------------
    # Conflict checks (called during /register to prevent duplicates)
    # ------------------------------------------------------------------

    def exists_username(self, username: str) -> bool:
        """Return True only for non-expired pending records with this username."""
        now = datetime.now(timezone.utc)
        with self._sf() as session:
            return (
                session.query(PendingRegistrationModel)
                .filter(
                    PendingRegistrationModel.username == username,
                    PendingRegistrationModel.expires_at > now,
                )
                .count()
                > 0
            )

    def exists_email(self, email: str) -> bool:
        """Return True only for non-expired pending records with this email."""
        now = datetime.now(timezone.utc)
        with self._sf() as session:
            return (
                session.query(PendingRegistrationModel)
                .filter(
                    PendingRegistrationModel.email == email,
                    PendingRegistrationModel.expires_at > now,
                )
                .count()
                > 0
            )

    # ------------------------------------------------------------------
    # Create / resend
    # ------------------------------------------------------------------

    def create_pending(
        self,
        full_name: str,
        username: str,
        email: str,
        whatsapp: str,
        profession: str,
        password_hash: str,
        salt: str = "bcrypt",
    ) -> str:
        """Insert a pending registration and return the plaintext OTP code."""
        code = _new_code()
        token_hash = _hash_code(code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_CODE_TTL_MINUTES)

        with self._sf() as session:
            # Remove any previous pending for same email OR username (re-registration)
            # Using synchronize_session=False for correct bulk delete behavior
            session.query(PendingRegistrationModel).filter(
                or_(
                    PendingRegistrationModel.email == email,
                    PendingRegistrationModel.username == username,
                )
            ).delete(synchronize_session=False)

            session.add(
                PendingRegistrationModel(
                    id=str(uuid.uuid4()),
                    full_name=full_name,
                    username=username,
                    email=email,
                    whatsapp=whatsapp,
                    profession=profession,
                    password_hash=password_hash,
                    salt=salt,
                    token_hash=token_hash,
                    expires_at=expires_at,
                )
            )
            session.commit()

        return code

    def refresh_code(self, email: str) -> Optional[tuple[str, str]]:
        """Generate and persist a new OTP for an existing pending record.

        Returns (plaintext_code, full_name) on success, None if not found.
        """
        code = _new_code()
        token_hash = _hash_code(code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_CODE_TTL_MINUTES)

        with self._sf() as session:
            row = (
                session.query(PendingRegistrationModel)
                .filter(PendingRegistrationModel.email == email)
                .first()
            )
            if not row:
                return None

            row.token_hash = token_hash
            row.expires_at = expires_at
            full_name = row.full_name
            session.commit()

        return code, full_name

    def find_by_email(self, email: str) -> Optional[PendingRegistrationModel]:
        """Return the pending registration row for the given email, or None."""
        with self._sf() as session:
            row = (
                session.query(PendingRegistrationModel)
                .filter(PendingRegistrationModel.email == email)
                .first()
            )
            if not row:
                return None
            # Detach from session before returning
            session.expunge(row)
            return row

    # ------------------------------------------------------------------
    # Confirm & promote
    # ------------------------------------------------------------------

    def confirm_and_promote(
        self, email: str, code: str, user_repo
    ) -> Optional[User]:
        """Validate OTP, promote pending record to *users* table.

        Returns the newly created User domain object on success,
        or None if the code is invalid / expired / record not found.
        """
        token_hash = _hash_code(code)
        now = datetime.now(timezone.utc)

        with self._sf() as session:
            row = (
                session.query(PendingRegistrationModel)
                .filter(
                    PendingRegistrationModel.email == email,
                    PendingRegistrationModel.token_hash == token_hash,
                    PendingRegistrationModel.expires_at > now,
                )
                .first()
            )
            if not row:
                return None

            # Build User domain object with email_verified=True
            user = User(
                full_name=row.full_name,
                username=row.username,
                email=row.email,
                whatsapp=row.whatsapp,
                profession=row.profession,
                password_hash=row.password_hash,
                salt=row.salt,
                email_verified=True,
            )

            # Promote to users table
            user_data = user.to_dict()
            user_model = UserModel(
                id=user_data["id"],
                full_name=user_data["full_name"],
                username=user_data["username"],
                email=user_data["email"],
                whatsapp=user_data["whatsapp"],
                profession=user_data["profession"],
                password_hash=user_data["password_hash"],
                salt=user_data["salt"],
                hash_algorithm="bcrypt",
                email_verified=True,
                created_at=datetime.now(timezone.utc),
            )
            session.add(user_model)

            # Initialise empty metrics row
            session.add(UserMetricsModel(user_id=user_data["id"]))

            # Remove from staging table
            session.delete(row)
            session.commit()

        return user

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def delete_expired(self) -> int:
        """Remove all pending registrations past their expiry. Returns count."""
        now = datetime.now(timezone.utc)
        with self._sf() as session:
            deleted = (
                session.query(PendingRegistrationModel)
                .filter(PendingRegistrationModel.expires_at <= now)
                .delete()
            )
            session.commit()
        return deleted
