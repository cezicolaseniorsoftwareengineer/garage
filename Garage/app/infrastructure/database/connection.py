"""Database connection pool and session factory for PostgreSQL (Neon)."""
import os
import re

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None

# Matches a postgres(ql):// URL anywhere inside a string.
_PG_URL_RE = re.compile(r"(postgres(?:ql)?://\S+)")


def _resolve_database_url() -> str:
    """Read DATABASE_URL from environment and extract a clean SQLAlchemy URL.

    Handles robustly:
    - Leading/trailing whitespace or newlines from copy-paste.
    - Literal surrounding quotes pasted in dashboards.
    - Full ``psql`` command pasted instead of just the URL
      (e.g. ``psql 'postgresql://user:pass@host/db'``).
    - ``postgres://`` scheme that SQLAlchemy rejects (needs ``postgresql://``).
    """
    raw = os.environ.get("DATABASE_URL", "").strip()

    # Remove accidental surrounding quotes (single or double)
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        raw = raw[1:-1].strip()

    # Extract the actual URL if the value contains a command prefix (e.g. psql ...)
    match = _PG_URL_RE.search(raw)
    if match:
        url = match.group(1)
    else:
        url = raw

    # Strip trailing quote that may remain from psql 'url'
    url = url.rstrip("'\"").strip()

    # Render / Heroku / Neon sometimes expose postgres:// instead of postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


def init_engine() -> None:
    """Initialize the SQLAlchemy engine and session factory.

    Must be called once during application startup before any
    repository or service attempts to acquire a database session.
    """
    global _engine, _SessionLocal
    url = _resolve_database_url()
    if not url:
        print("[GARAGE] DATABASE_URL is empty -- skipping PostgreSQL init.")
        return

    # Masked log for deploy debugging (show scheme + host only)
    try:
        _masked = url.split("@")[-1].split("?")[0] if "@" in url else "<no-host>"
    except Exception:
        _masked = "<parse-error>"
    print(f"[GARAGE] Initialising PostgreSQL engine -> {_masked}")

    try:
        _engine = create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            echo=False,
        )
    except Exception as exc:
        print(f"[GARAGE] FATAL: Failed to create engine: {exc}")
        print(f"[GARAGE] URL scheme: {url[:url.index('://') + 3] if '://' in url else 'MISSING'}")
        print(f"[GARAGE] URL length: {len(url)}, first 30 chars: {repr(url[:30])}")
        raise
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def get_engine():
    """Return the current SQLAlchemy engine (may be None)."""
    return _engine


def get_session_factory():
    """Return the sessionmaker bound to the engine.

    Raises RuntimeError if the engine has not been initialised.
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised. Call init_engine() first.")
    return _SessionLocal


def create_tables() -> None:
    """Create all tables declared in models.Base.metadata.

    Safe to call multiple times -- CREATE IF NOT EXISTS semantics.
    """
    if _engine is None:
        return
    from app.infrastructure.database.models import Base
    Base.metadata.create_all(bind=_engine)


def check_health() -> bool:
    """Verify database connectivity with a lightweight probe."""
    if _engine is None:
        return False
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
