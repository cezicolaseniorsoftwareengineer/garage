"""Entry point. Wires repos into routes and serves the frontend.

Persistence strategy:
  - If DATABASE_URL is set  -> PostgreSQL (Neon) with full auth/metrics/events.
  - Otherwise               -> JSON file fallback (development only).
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes.game_routes import router as game_router, init_routes
from app.api.routes.auth_routes import router as auth_router, init_auth_routes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

app = FastAPI(
    title="GARAGE - Toda Big Tech tem um inicio",
    description="Backend-first engineering education game.",
    version="3.0.0",
)

# CORS (required for browser frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (frontend visualisation layer)
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---------------------------------------------------------------------------
# Persistence wiring
# ---------------------------------------------------------------------------

metrics_service = None
event_service = None

if DATABASE_URL:
    # -- PostgreSQL (Neon) --------------------------------------------------
    from app.infrastructure.database.connection import (
        init_engine, create_tables, get_session_factory, check_health,
    )
    from app.infrastructure.repositories.pg_user_repository import PgUserRepository
    from app.infrastructure.repositories.pg_player_repository import PgPlayerRepository
    from app.infrastructure.repositories.pg_leaderboard_repository import PgLeaderboardRepository
    from app.infrastructure.repositories.pg_challenge_repository import PgChallengeRepository
    from app.infrastructure.database.seed import seed_challenges
    from app.application.metrics_service import MetricsService
    from app.application.event_service import EventService

    init_engine()
    create_tables()
    _sf = get_session_factory()

    challenge_repo = PgChallengeRepository(_sf)
    player_repo = PgPlayerRepository(_sf)
    leaderboard_repo = PgLeaderboardRepository(_sf)
    user_repo = PgUserRepository(_sf)
    metrics_service = MetricsService(_sf)
    event_service = EventService(_sf)

    # Seed challenges from JSON into DB (idempotent)
    seeded = seed_challenges(_sf, os.path.join(DATA_DIR, "challenges.json"))
    if seeded:
        print(f"[GARAGE] Seeded {seeded} challenges into PostgreSQL.")

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
    _persistence = "json"

# Wire repos + services into route modules
init_routes(player_repo, challenge_repo, leaderboard_repo,
            metrics_service=metrics_service, event_service=event_service)
init_auth_routes(user_repo, event_service=event_service)

# Register API routes
app.include_router(auth_router)
app.include_router(game_router)


@app.get("/")
def serve_frontend():
    """Serve index.html."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "GARAGE API is running. No frontend found at /static/index.html."}


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
        "challenges_loaded": len(challenge_repo.get_all()),
    }
    if DATABASE_URL:
        from app.infrastructure.database.connection import check_health
        result["database"] = "connected" if check_health() else "disconnected"
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
