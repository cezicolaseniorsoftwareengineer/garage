"""
Shared pytest fixtures for the GARAGE test suite.

Strategy:
- Domain tests: pure in-memory, zero I/O.
- API/integration tests: FastAPI TestClient with JSON repos in a tmp directory.
  DATABASE_URL is cleared so the app always uses the JSON fallback in tests.
"""
import os
import json
import shutil
import tempfile
import pytest

# ---------------------------------------------------------------------------
# Ensure no real database is touched during the test run
# ---------------------------------------------------------------------------
os.environ.pop("DATABASE_URL", None)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-123456")
os.environ.setdefault("ENV", "test")


# ---------------------------------------------------------------------------
# Domain helpers (reusable across many test modules)
# ---------------------------------------------------------------------------
from app.domain.enums import (
    Gender, Ethnicity, BackendLanguage, CareerStage,
    ChallengeCategory, MapRegion, GameEnding,
)
from app.domain.character import Character
from app.domain.player import Player
from app.domain.challenge import Challenge, ChallengeOption


def make_character(**kwargs) -> Character:
    defaults = {"gender": Gender.MALE, "ethnicity": Ethnicity.WHITE, "avatar_index": 0}
    defaults.update(kwargs)
    return Character(**defaults)


def make_player(name="Dev", stage=CareerStage.INTERN, **kwargs) -> Player:
    return Player(
        name=name,
        character=make_character(),
        language=BackendLanguage.JAVA,
        stage=stage,
        **kwargs,
    )


def make_option(text="opt", is_correct=False, explanation="expl") -> ChallengeOption:
    return ChallengeOption(text=text, is_correct=is_correct, explanation=explanation)


def make_challenge(
    challenge_id="intern_01_test",
    required_stage=CareerStage.INTERN,
    correct_index=0,
    category=ChallengeCategory.LOGIC,
    region=MapRegion.XEROX_PARC,
    n_options=4,
) -> Challenge:
    options = []
    for i in range(n_options):
        options.append(make_option(
            text=f"Option {i}",
            is_correct=(i == correct_index),
            explanation=f"Explanation {i}",
        ))
    return Challenge(
        challenge_id=challenge_id,
        title="Test Challenge",
        description="What is 2+2?",
        context_code=None,
        category=category,
        required_stage=required_stage,
        region=region,
        options=options,
    )


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def character():
    return make_character()


@pytest.fixture
def player():
    return make_player()


@pytest.fixture
def intern_challenge():
    return make_challenge("intern_01_test", required_stage=CareerStage.INTERN, correct_index=0)


@pytest.fixture
def senior_challenge():
    return make_challenge("senior_01_test", required_stage=CareerStage.SENIOR, correct_index=1)


@pytest.fixture
def arch_challenge():
    """Architecture challenge — wrong answer gives -30 points."""
    return make_challenge(
        "intern_02_arch",
        required_stage=CareerStage.INTERN,
        correct_index=0,
        category=ChallengeCategory.ARCHITECTURE,
    )


# ---------------------------------------------------------------------------
# FastAPI TestClient with JSON-file repos in a temp directory
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tmp_data_dir():
    """Temporary data directory shared across the entire session."""
    d = tempfile.mkdtemp(prefix="garage_test_")
    # Seed minimal challenges.json
    challenges = [
        {
            "id": f"intern_0{i+1}_test",
            "title": f"Test Challenge {i+1}",
            "description": "What is correct?",
            "context_code": None,
            "category": "logic",
            "required_stage": "Intern",
            "region": "Xerox PARC",
            "mentor": "The Craftsman",
            "points_on_correct": 100,
            "points_on_wrong": 0,
            "options": [
                {"text": "Correct", "is_correct": True, "explanation": "Yes!"},
                {"text": "Wrong A", "is_correct": False, "explanation": "No"},
                {"text": "Wrong B", "is_correct": False, "explanation": "No"},
                {"text": "Wrong C", "is_correct": False, "explanation": "No"},
            ],
        }
        for i in range(5)
    ]
    with open(os.path.join(d, "challenges.json"), "w") as f:
        json.dump(challenges, f)
    # Empty JSON files for other repos
    for name in ("sessions.json", "users.json", "leaderboard.json"):
        with open(os.path.join(d, name), "w") as f:
            json.dump({} if name in ("sessions.json", "users.json") else [], f)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def test_app(tmp_data_dir):
    """FastAPI app wired with JSON repos in the tmp directory."""
    from app.infrastructure.repositories.challenge_repository import ChallengeRepository
    from app.infrastructure.repositories.player_repository import PlayerRepository
    from app.infrastructure.repositories.leaderboard_repository import LeaderboardRepository
    from app.infrastructure.repositories.user_repository import UserRepository
    from app.api.routes.game_routes import router as game_router, init_routes
    from app.api.routes.auth_routes import router as auth_router, init_auth_routes
    from app.api.routes.admin_routes import router as admin_router, init_admin_routes
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    challenge_repo = ChallengeRepository(os.path.join(tmp_data_dir, "challenges.json"))
    player_repo = PlayerRepository(os.path.join(tmp_data_dir, "sessions.json"))
    leaderboard_repo = LeaderboardRepository(os.path.join(tmp_data_dir, "leaderboard.json"))
    user_repo = UserRepository(os.path.join(tmp_data_dir, "users.json"))

    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    init_routes(player_repo, challenge_repo, leaderboard_repo)
    init_auth_routes(user_repo)
    init_admin_routes(user_repo, player_repo, leaderboard_repo, challenge_repo)

    app.include_router(auth_router)
    app.include_router(game_router)
    app.include_router(admin_router)

    return app


@pytest.fixture(scope="session")
def client(test_app):
    from fastapi.testclient import TestClient
    return TestClient(test_app)


@pytest.fixture(scope="session")
def auth_headers(client):
    """Register + login a test user, return Bearer headers."""
    client.post("/api/auth/register", json={
        "full_name": "Test Player",
        "username": "testplayer",
        "email": "test@garage.test",
        "whatsapp": "11999999999",
        "profession": "estudante",
        "password": "StrongPass123!",
    })
    resp = client.post("/api/auth/login", json={
        "username": "testplayer",
        "password": "StrongPass123!",
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def session_id(client, auth_headers):
    """Create a game session and return its ID."""
    resp = client.post("/api/start", json={
        "player_name": "TestDev",
        "gender": "male",
        "ethnicity": "white",
        "avatar_index": 0,
        "language": "Java",
    }, headers=auth_headers)
    assert resp.status_code == 200, f"Start failed: {resp.text}"
    return resp.json()["session_id"]
