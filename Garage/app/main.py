"""Entry point. Wires repos into routes and serves the frontend.

Persistence strategy:
  - If DATABASE_URL is set  -> PostgreSQL (Neon) with full auth/metrics/events.
  - Otherwise               -> JSON file fallback (development only).
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(PROJECT_DIR, ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from app.api.routes.game_routes import router as game_router, init_routes
from app.api.routes.auth_routes import router as auth_router, init_auth_routes
from app.api.routes.admin_routes import router as admin_router, init_admin_routes
from app.api.routes.study_routes import router as study_router, init_study_routes
from app.api.routes.code_runner_routes import router as code_runner_router
from app.api.routes.ai_validator_routes import router as ai_validator_router
from app.api.routes.payment_routes import router as payment_router, init_payment_routes
from app.api.routes.analytics_routes import router as analytics_router, init_analytics_routes
from app.api.routes.account_routes import router as account_router, init_account_routes
from app.api.routes.diagnostic_routes import router as diagnostic_router
from app.infrastructure.middleware.idempotency import IdempotencyMiddleware

DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
LANDING_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "landing")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

app = FastAPI(
    title="GARAGE - Toda Big Tech tem um inicio",
    description="Backend-first engineering education game.",
    version="3.0.0",
)

# ---------------------------------------------------------------------------
# GZip compression — reduces JS/CSS/HTML/JSON by ~70%
# ---------------------------------------------------------------------------
app.add_middleware(GZipMiddleware, minimum_size=1024)

# ---------------------------------------------------------------------------
# Cache-Control middleware for static assets
# Saves bandwidth: browser caches assets instead of re-downloading every visit.
# ---------------------------------------------------------------------------
_LONG_CACHE   = "public, max-age=2592000, immutable"   # 30 days  — MP3, PNG, images
_REVALIDATE   = "no-store, no-cache, must-revalidate"  # never cache — JS, CSS (version-busted via ?v=)
_NO_CACHE     = "no-store, no-cache, must-revalidate"  # HTML, API responses

_CACHE_BY_EXT = {
    ".mp3": _LONG_CACHE,  ".ogg": _LONG_CACHE, ".wav": _LONG_CACHE,
    ".png": _LONG_CACHE,  ".jpg": _LONG_CACHE,  ".jpeg": _LONG_CACHE,
    ".gif": _LONG_CACHE,  ".webp": _LONG_CACHE, ".ico":  _LONG_CACHE,
    ".svg": _LONG_CACHE,  ".woff": _LONG_CACHE, ".woff2": _LONG_CACHE,
    ".ttf": _LONG_CACHE,
    ".js":  _REVALIDATE,  ".css": _REVALIDATE,
}


class StaticCacheMiddleware(BaseHTTPMiddleware):
    """Inject Cache-Control headers on /static/* responses."""

    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/"):
            ext = os.path.splitext(path)[1].lower()
            header = _CACHE_BY_EXT.get(ext, _NO_CACHE)
            response.headers["Cache-Control"] = header
            # Allow CDN / Cloudflare to cache the same rules
            response.headers["Vary"] = "Accept-Encoding"
        return response


app.add_middleware(StaticCacheMiddleware)

# Server-side idempotency middleware — deduplicate mutating requests with
# `Idempotency-Key` header when provided by the client.
app.add_middleware(IdempotencyMiddleware)

# CORS (required for browser frontend)
# CORS configuration: read allowed origins from env (comma-separated).
# IMPORTANT: allow_credentials=True is INVALID with allow_origins=["*"] per the
# CORS spec — browsers reject the preflight with 400. Only enable credentials
# when specific origins are declared (production).
_allowed = os.environ.get("ALLOWED_ORIGINS", "").strip()
if _allowed:
    allow_origins = [o.strip() for o in _allowed.split(",") if o.strip()]
    allow_credentials = True
else:
    # Wildcard for local development — credentials MUST be False with "*"
    allow_origins = ["*"]
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (frontend visualisation layer)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Landing page static assets  (CSS, JS, screenshots)
if os.path.exists(LANDING_DIR):
    app.mount("/landing", StaticFiles(directory=LANDING_DIR), name="landing")

# ---------------------------------------------------------------------------
# Persistence wiring
# ---------------------------------------------------------------------------

metrics_service = None
event_service = None
verification_repo = None  # set only when PostgreSQL is available
pending_repo = None       # PgPendingRepository -- pre-verification staging table

if DATABASE_URL:
    # -- PostgreSQL (Neon primary + Supabase fallback) ----------------------
    from app.infrastructure.database.connection import (
        init_engine, create_tables, dynamic_session_factory, check_health, get_db_status,
    )
    from app.infrastructure.repositories.pg_user_repository import PgUserRepository
    from app.infrastructure.repositories.pg_player_repository import PgPlayerRepository
    from app.infrastructure.repositories.pg_leaderboard_repository import PgLeaderboardRepository
    from app.infrastructure.repositories.pg_challenge_repository import PgChallengeRepository
    from app.infrastructure.repositories.pg_verification_repository import PgVerificationRepository
    from app.infrastructure.repositories.pg_pending_repository import PgPendingRepository
    from app.infrastructure.repositories.pg_landing_analytics_repository import PgLandingAnalyticsRepository
    from app.infrastructure.database.seed import seed_challenges
    from app.application.metrics_service import MetricsService
    from app.application.event_service import EventService

    init_engine()
    create_tables()
    _sf = dynamic_session_factory   # proxy — always routes to active engine

    challenge_repo = PgChallengeRepository(_sf)
    player_repo = PgPlayerRepository(_sf)
    leaderboard_repo = PgLeaderboardRepository(_sf)
    user_repo = PgUserRepository(_sf)
    verification_repo = PgVerificationRepository(_sf)
    pending_repo = PgPendingRepository(_sf)
    landing_analytics_repo = PgLandingAnalyticsRepository(_sf)
    metrics_service = MetricsService(_sf)
    event_service = EventService(_sf)

    # Seed challenges from JSON into DB (idempotent — non-fatal if DB is down)
    try:
        seeded = seed_challenges(_sf, os.path.join(DATA_DIR, "challenges.json"))
        if seeded:
            print(f"[GARAGE] Seeded {seeded} challenges into PostgreSQL.")
    except Exception as _seed_exc:
        print(f"[GARAGE][WARN] Seed skipped (DB unavailable): {type(_seed_exc).__name__}: {_seed_exc}")

    # -- Validate challenges are accessible and enum-compatible via PostgreSQL ---
    try:
        _challenges_sample = challenge_repo.get_all()
        _challenge_count = len(_challenges_sample)
        print(f"[GARAGE] PostgreSQL challenges available and parsed: {_challenge_count}")
        if _challenge_count == 0:
            raise RuntimeError("challenges table is empty after seed")
    except Exception as _pg_exc:
        import logging as _logging
        _logging.getLogger("garage.startup").error(
            "PostgreSQL challenge repo failed: %s: %s", type(_pg_exc).__name__, _pg_exc
        )
        print(f"[GARAGE][ERROR] PostgreSQL challenge repo failed ({type(_pg_exc).__name__}: {_pg_exc}).")
        # Fall back to JSON challenges when DB is unavailable (production or dev).
        # This keeps the app serving players even during DB quota/outage events.
        # On recovery, the circuit-breaker reopens and future requests use the DB.
        print("[GARAGE][WARN] Falling back to JSON challenges (DB unavailable).")
        from app.infrastructure.repositories.challenge_repository import ChallengeRepository as _JsonChallengeRepo
        challenge_repo = _JsonChallengeRepo(
            data_path=os.path.join(DATA_DIR, "challenges.json")
        )

    _persistence = "postgresql"
else:
    # -- JSON file fallback (dev) -------------------------------------------
    from app.infrastructure.repositories.challenge_repository import ChallengeRepository
    from app.infrastructure.repositories.player_repository import PlayerRepository
    from app.infrastructure.repositories.leaderboard_repository import LeaderboardRepository
    from app.infrastructure.repositories.user_repository import UserRepository

    challenge_repo = ChallengeRepository(
        data_path=os.path.join(DATA_DIR, "challenges.json")
    )
    player_repo = PlayerRepository(
        data_path=os.path.join(DATA_DIR, "sessions.json")
    )
    leaderboard_repo = LeaderboardRepository(
        data_path=os.path.join(DATA_DIR, "leaderboard.json")
    )
    user_repo = UserRepository(
        data_path=os.path.join(DATA_DIR, "users.json")
    )
    landing_analytics_repo = None  # analytics require PostgreSQL
    _persistence = "json"

# Wire repos + services into route modules
init_routes(player_repo, challenge_repo, leaderboard_repo,
            metrics_service=metrics_service, event_service=event_service,
            user_repo=user_repo)
init_auth_routes(
    user_repo,
    event_service=event_service,
    verification_repo=verification_repo if DATABASE_URL else None,
    pending_repo=pending_repo if DATABASE_URL else None,
)
init_admin_routes(user_repo, player_repo, leaderboard_repo, challenge_repo,
                  pending_repo=pending_repo if DATABASE_URL else None)
init_study_routes(player_repo, challenge_repo)
init_payment_routes(user_repo)
init_analytics_routes(landing_analytics_repo if DATABASE_URL else None)
init_account_routes(
    user_repo,
    session_factory=dynamic_session_factory if DATABASE_URL else None,
)

# Register API routes
app.include_router(auth_router)
app.include_router(game_router)
app.include_router(admin_router)
app.include_router(study_router)
app.include_router(code_runner_router)
app.include_router(ai_validator_router)
app.include_router(payment_router)
app.include_router(analytics_router)
app.include_router(account_router)
app.include_router(diagnostic_router)


@app.get("/")
def serve_landing():
    """Serve landing page (entry point / marketing page)."""
    landing_path = os.path.join(LANDING_DIR, "index.html")
    if os.path.exists(landing_path):
        return FileResponse(landing_path, headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        })
    # Fallback: serve the game directly if no landing page
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "GARAGE API is running."}


@app.get("/jogo")
def serve_game():
    """Serve the game frontend."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        })
    return {"message": "Game not found."}


@app.get("/account")
def serve_account():
    """Serve the user account area (subscription + usage stats)."""
    account_path = os.path.join(STATIC_DIR, "account.html")
    if os.path.exists(account_path):
        return FileResponse(account_path, headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        })
    return {"message": "Account page not found."}


@app.get("/admin")
def serve_admin():
    """Serve the admin dashboard (authentication enforced client-side + API)."""
    admin_path = os.path.join(STATIC_DIR, "admin.html")
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    return {"message": "Admin page not found."}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Favicon or 204."""
    favicon_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get("/health")
def health():
    result = {
        "status": "online",
        "system": "GARAGE Backend v3.0.0",
        "persistence": _persistence,
    }
    try:
        result["challenges_loaded"] = len(challenge_repo.get_all())
    except Exception as exc:
        result["challenges_loaded"] = f"ERROR: {type(exc).__name__}"
    if DATABASE_URL:
        # Use in-memory circuit-breaker state — avoids a live TCP probe that
        # would block for up to connect_timeout seconds when Neon is hibernating,
        # which would cause Render's health check to time out and restart the
        # service in a loop.  For live DB probes use GET /api/diagnostic/db.
        from app.infrastructure.database.connection import get_db_circuit_state
        try:
            result["db_circuit"] = get_db_circuit_state()
        except Exception as exc:
            result["db_circuit"] = f"ERROR: {type(exc).__name__}"
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_includes=["*.py", "*.html", "*.css", "*.js"],
        reload_excludes=["*.json", "__pycache__/*", "data/*"],
    )
