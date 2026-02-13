"""Database connection pool and session factory for PostgreSQL (Neon)."""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None


def _resolve_database_url() -> str:
    """Read DATABASE_URL from environment. Fix common URL scheme issues."""
    url = os.environ.get("DATABASE_URL", "")
    # Render / Heroku sometimes expose postgres:// instead of postgresql://
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
        return

    _engine = create_engine(
        url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=False,
    )
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
