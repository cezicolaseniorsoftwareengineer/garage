"""User entity -- authentication and profile data."""
import hashlib
import secrets
from datetime import datetime, timezone
from uuid import uuid4


class User:
    """Registered user with hashed credentials."""

    def __init__(
        self,
        full_name: str,
        username: str,
        email: str,
        whatsapp: str,
        profession: str,
        password_hash: str,
        salt: str,
        user_id: str | None = None,
        created_at: str | None = None,
        email_verified: bool = False,
    ):
        self._id = user_id or str(uuid4())
        self._full_name = full_name
        self._username = username.lower().strip()
        self._email = email.lower().strip()
        self._whatsapp = whatsapp.strip()
        self._profession = profession
        self._password_hash = password_hash
        self._salt = salt
        self._created_at = created_at or datetime.now(timezone.utc).isoformat()
        self._email_verified = email_verified

    @property
    def id(self) -> str:
        return self._id

    @property
    def username(self) -> str:
        return self._username

    @property
    def email(self) -> str:
        return self._email

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def email_verified(self) -> bool:
        return self._email_verified

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """SHA-256 hash with salt. Deterministic for verification."""
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    @staticmethod
    def generate_salt() -> str:
        """Cryptographically secure random salt."""
        return secrets.token_hex(16)

    def verify_password(self, password: str) -> bool:
        """Check password against stored hash."""
        candidate = self.hash_password(password, self._salt)
        return secrets.compare_digest(candidate, self._password_hash)

    def to_dict(self) -> dict:
        return {
            "id": self._id,
            "full_name": self._full_name,
            "username": self._username,
            "email": self._email,
            "whatsapp": self._whatsapp,
            "profession": self._profession,
            "password_hash": self._password_hash,
            "salt": self._salt,
            "created_at": self._created_at,
            "email_verified": self._email_verified,
        }

    def to_public_dict(self) -> dict:
        """Safe representation without credentials."""
        return {
            "id": self._id,
            "full_name": self._full_name,
            "username": self._username,
            "email": self._email,
            "profession": self._profession,
            "email_verified": self._email_verified,
        }
