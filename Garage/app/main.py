"""Entry point. Wires repos into routes and serves the frontend."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes.game_routes import router as game_router, init_routes
from app.infrastructure.repositories.challenge_repository import ChallengeRepository
from app.infrastructure.repositories.player_repository import PlayerRepository
from app.infrastructure.repositories.leaderboard_repository import LeaderboardRepository

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

app = FastAPI(
    title="GARAGE - Toda Big Tech tem um inicio",
    description="Backend-first engineering education game.",
    version="2.0.0",
)

# CORS (required for browser frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (frontend visualization layer)
STATIC_DIR = os.path.join(BASE_DIR, "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

challenge_repo = ChallengeRepository(
    data_path=os.path.join(DATA_DIR, "challenges.json")
)
player_repo = PlayerRepository(
    data_path=os.path.join(DATA_DIR, "sessions.json")
)
leaderboard_repo = LeaderboardRepository(
    data_path=os.path.join(DATA_DIR, "leaderboard.json")
)

init_routes(player_repo, challenge_repo, leaderboard_repo)

# Register API routes
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
    return {
        "status": "online",
        "system": "GARAGE Backend v2.0.0",
        "challenges_loaded": len(challenge_repo.get_all()),
    }


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
