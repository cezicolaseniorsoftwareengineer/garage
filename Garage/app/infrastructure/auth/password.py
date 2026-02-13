"""Password hashing -- bcrypt (primary) with legacy SHA-256 support."""
import hashlib
import secrets

import bcrypt


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return bcrypt.hashpw(
        plain.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_legacy_sha256(plain: str, salt: str, stored_hash: str) -> bool:
    """Verify against the legacy SHA-256 + salt scheme."""
    candidate = hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
    return secrets.compare_digest(candidate, stored_hash)


def is_bcrypt_hash(hashed: str) -> bool:
    """Return True if the hash string looks like a bcrypt hash."""
    return hashed.startswith("$2b$") or hashed.startswith("$2a$")
