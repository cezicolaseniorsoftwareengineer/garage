"""Database connection pool and session factory — primary (Neon) + fallback (Supabase).

Circuit-breaker strategy:
  - Primary engine used by default.
  - After PRIMARY_FAILURE_THRESHOLD consecutive failures it is marked DOWN and
    the fallback engine (FALLBACK_DATABASE_URL) takes over transparently.
  - Every PRIMARY_RETRY_INTERVAL seconds the primary is probed; if healthy it is
    restored automatically.
  - All repository code is unaffected: call get_session_factory() as before.
"""
import os
import re
import threading
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ── circuit-breaker tunables ────────────────────────────────────────────────
PRIMARY_FAILURE_THRESHOLD = 3     # consecutive errors before opening circuit
PRIMARY_RETRY_INTERVAL    = 120   # seconds between primary health checks
# ────────────────────────────────────────────────────────────────────────────

_primary_engine   = None
_fallback_engine  = None
_primary_sf       = None   # sessionmaker for primary
_fallback_sf      = None   # sessionmaker for fallback

_circuit_open         = False   # True  => routing to fallback
_consecutive_failures = 0
_last_primary_check   = 0.0
_cb_lock              = threading.Lock()

# ── legacy single-engine aliases (unchanged public API) ────────────────────
_engine       = None   # always points to the currently active engine
_SessionLocal = None   # always points to the currently active sessionmaker

# Matches a postgres(ql):// URL anywhere inside a string.
_PG_URL_RE = re.compile(r"(postgres(?:ql)?://\S+)")


def _resolve_database_url(env_var: str = "DATABASE_URL") -> str:
    """Read a database URL from environment and return a clean SQLAlchemy URL.

    Handles robustly:
    - Leading/trailing whitespace or newlines from copy-paste.
    - Literal surrounding quotes pasted in dashboards.
    - Full ``psql`` command pasted instead of just the URL.
    - ``postgres://`` scheme that SQLAlchemy rejects (needs ``postgresql://``).
    """
    raw = os.environ.get(env_var, "").strip()

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


def _build_engine(url: str, label: str):
    """Create a SQLAlchemy engine for the given URL, logging masked host."""
    try:
        masked = url.split("@")[-1].split("?")[0] if "@" in url else "<no-host>"
    except Exception:
        masked = "<parse-error>"
    print(f"[GARAGE] Initialising {label} engine -> {masked}")
    return create_engine(
        url,
        pool_size=3,
        max_overflow=5,
        pool_timeout=15,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=False,
    )


def init_engine() -> None:
    """Initialize primary (Neon) and optional fallback (Supabase) engines.

    Environment variables:
      DATABASE_URL          — required, Neon connection string
      FALLBACK_DATABASE_URL — optional, Supabase (or any PostgreSQL) fallback
    """
    global _primary_engine, _fallback_engine, _primary_sf, _fallback_sf
    global _engine, _SessionLocal

    primary_url  = _resolve_database_url("DATABASE_URL")
    fallback_url = _resolve_database_url("FALLBACK_DATABASE_URL")

    if not primary_url:
        print("[GARAGE] DATABASE_URL is empty -- skipping PostgreSQL init.")
        return

    try:
        _primary_engine = _build_engine(primary_url, "PRIMARY")
        _primary_sf     = sessionmaker(bind=_primary_engine, expire_on_commit=False)
    except Exception as exc:
        print(f"[GARAGE] FATAL: Failed to create primary engine: {exc}")
        raise

    if fallback_url:
        try:
            _fallback_engine = _build_engine(fallback_url, "FALLBACK")
            _fallback_sf     = sessionmaker(bind=_fallback_engine, expire_on_commit=False)
            print("[GARAGE] Fallback DB registered (circuit-breaker active).")
        except Exception as exc:
            print(f"[GARAGE] WARNING: Could not create fallback engine: {exc}")
            _fallback_engine = None
            _fallback_sf     = None
    else:
        print("[GARAGE] FALLBACK_DATABASE_URL not set -- single-engine mode.")

    # Legacy aliases point to primary initially
    _engine       = _primary_engine
    _SessionLocal = _primary_sf


    # Legacy aliases point to primary initially
    _engine       = _primary_engine
    _SessionLocal = _primary_sf


# ── circuit-breaker helpers ────────────────────────────────────────────────

def _get_active_sf():
    """Return the sessionmaker for the currently active engine.

    Implements the circuit-breaker: if the primary has failed
    PRIMARY_FAILURE_THRESHOLD times in a row it is bypassed until
    PRIMARY_RETRY_INTERVAL seconds have elapsed and a health probe succeeds.
    """
    global _circuit_open, _consecutive_failures, _last_primary_check
    global _engine, _SessionLocal

    if _primary_sf is None:
        raise RuntimeError("Database not initialised. Call init_engine() first.")

    with _cb_lock:
        # Primary is marked DOWN → try to heal
        if _circuit_open and _fallback_sf is not None:
            now = time.monotonic()
            if now - _last_primary_check >= PRIMARY_RETRY_INTERVAL:
                _last_primary_check = now
                if _check_engine_health(_primary_engine):
                    _circuit_open         = False
                    _consecutive_failures = 0
                    _engine               = _primary_engine
                    _SessionLocal         = _primary_sf
                    print("[GARAGE] Primary DB recovered — circuit CLOSED.")
            return _fallback_sf

        return _primary_sf


def _record_db_failure(exc: Exception) -> None:
    """Record a DB failure; open circuit if threshold reached."""
    global _circuit_open, _consecutive_failures, _last_primary_check
    global _engine, _SessionLocal

    if _fallback_sf is None:
        return  # no fallback configured — nothing to switch to

    with _cb_lock:
        if _circuit_open:
            return  # already open
        _consecutive_failures += 1
        if _consecutive_failures >= PRIMARY_FAILURE_THRESHOLD:
            _circuit_open         = True
            _last_primary_check   = time.monotonic()
            _engine               = _fallback_engine
            _SessionLocal         = _fallback_sf
            print(
                f"[GARAGE] Primary DB failed {_consecutive_failures}x — "
                "circuit OPEN, routing to FALLBACK."
            )


def _record_db_success() -> None:
    """Reset failure counter on a successful primary operation."""
    global _consecutive_failures
    with _cb_lock:
        _consecutive_failures = 0


def _check_engine_health(engine) -> bool:
    """Lightweight connectivity probe for an engine."""
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ── public API ──────────────────────────────────────────────────────────────


def get_engine():
    """Return the currently active SQLAlchemy engine (may be None)."""
    return _engine


def get_session_factory():
    """Return a sessionmaker for the currently active database.

    Raises RuntimeError if no engine has been initialised.
    Transparently routes to the fallback engine while the circuit is open.
    """
    return _get_active_sf()


def create_tables() -> None:
    """Create all tables on ALL initialised engines (idempotent).

    Ensures the fallback database is schema-ready before it is needed.
    """
    from app.infrastructure.database.models import Base

    for label, engine in [("PRIMARY", _primary_engine), ("FALLBACK", _fallback_engine)]:
        if engine is None:
            continue
        try:
            Base.metadata.create_all(bind=engine)
            _ensure_indexes(engine)
            print(f"[GARAGE] Tables verified on {label} DB.")
        except Exception as exc:
            print(f"[GARAGE] WARNING: Could not create tables on {label} DB: {exc}")


def _ensure_indexes(engine) -> None:
    """Apply performance indexes that cannot be expressed via create_all."""
    ddl_statements = [
        """
        CREATE INDEX IF NOT EXISTS idx_game_sessions_active
        ON game_sessions (updated_at DESC)
        WHERE status = 'in_progress'
        """,
    ]
    try:
        with engine.begin() as conn:
            for ddl in ddl_statements:
                conn.execute(text(ddl))
    except Exception as exc:
        print(f"[GARAGE] WARNING: Could not ensure indexes: {exc}")


def check_health() -> bool:
    """Verify connectivity on the currently active database."""
    return _check_engine_health(_engine)


def get_db_status() -> dict:
    """Return a status dict useful for admin/health endpoints."""
    return {
        "primary_healthy":  _check_engine_health(_primary_engine),
        "fallback_healthy": _check_engine_health(_fallback_engine),
        "circuit_open":     _circuit_open,
        "active":           "fallback" if _circuit_open else "primary",
        "consecutive_failures": _consecutive_failures,
    }


# ── dynamic session factory proxy ──────────────────────────────────────────

from contextlib import contextmanager
from sqlalchemy.exc import OperationalError


class DynamicSessionFactory:
    """Callable proxy passed to repositories.

    Behaves exactly like a sessionmaker but always resolves to the *currently
    active* engine.  When a database OperationalError occurs it feeds the
    circuit-breaker so the next call is automatically routed to the fallback.

    Usage (identical to bare sessionmaker):
        with dynamic_sf() as session:
            ...
    """

    def __call__(self):
        return self._managed_session()

    @contextmanager
    def _managed_session(self):
        sf = _get_active_sf()
        session = sf()
        try:
            yield session
            _record_db_success()
        except OperationalError as exc:
            session.rollback()
            _record_db_failure(exc)
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Singleton — import and pass to all PG repositories.
dynamic_session_factory = DynamicSessionFactory()
