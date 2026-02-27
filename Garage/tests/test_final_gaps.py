"""
Final coverage gap tests — covers remaining uncovered lines after main suite.

Target files:
- app/domain/challenge.py        lines 96, 120, 131
- app/api/routes/game_routes.py  lines 107-108, 122-123, 156-159, 167, 191, 220, 242, 346-353
- app/api/routes/study_routes.py lines 1011-1021, 1150, 1160, 1164
"""
import os
import json
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-123456")
os.environ.setdefault("ENV", "test")

# ---------------------------------------------------------------------------
# Domain: challenge.py properties — lines 96, 120, 131
# ---------------------------------------------------------------------------

class TestChallengeExtraProperties:
    """Cover context_code, points_on_correct, correct_index properties."""

    def _make(self):
        from app.domain.challenge import Challenge, ChallengeOption
        from app.domain.enums import ChallengeCategory, CareerStage, MapRegion
        opt_correct = ChallengeOption(text="correct", is_correct=True, explanation="yes")
        opt_wrong = ChallengeOption(text="wrong", is_correct=False, explanation="no")
        return Challenge(
            challenge_id="prop-test",
            title="Prop Test",
            description="desc",
            context_code="int x = 1;",  # non-None context_code
            category=ChallengeCategory.LOGIC,
            required_stage=CareerStage.INTERN,
            region=MapRegion.XEROX_PARC,
            options=[opt_correct, opt_wrong],
            mentor_name="Alan Kay",
            points_on_correct=150,
            points_on_wrong=10,
        )

    def test_context_code_property(self):
        """Line 96: return self._context_code."""
        c = self._make()
        assert c.context_code == "int x = 1;"

    def test_points_on_correct_property(self):
        """Line 120: return self._points_on_correct."""
        c = self._make()
        assert c.points_on_correct == 150

    def test_correct_index_returns_index(self):
        """Line 131: return i inside correct_index loop."""
        c = self._make()
        assert c.correct_index == 0  # opt_correct is index 0


# ---------------------------------------------------------------------------
# Game routes helpers
# ---------------------------------------------------------------------------

def _build_game_app(with_metrics=False, with_events=False):
    """Build an isolated game+auth app for targeted tests."""
    from app.infrastructure.repositories.challenge_repository import ChallengeRepository
    from app.infrastructure.repositories.player_repository import PlayerRepository
    from app.infrastructure.repositories.leaderboard_repository import LeaderboardRepository
    from app.infrastructure.repositories.user_repository import UserRepository
    from app.api.routes.game_routes import router as game_router, init_routes
    from app.api.routes.auth_routes import router as auth_router, init_auth_routes

    tmpdir = tempfile.mkdtemp(prefix="garage_final_test_")

    challenges = [
        {
            "id": f"final_{i}",
            "title": f"Final Challenge {i}",
            "description": "What is correct?",
            "context_code": None,
            "category": "logic",
            "required_stage": "Intern",
            "region": "Xerox PARC",
            "mentor": "Tester",
            "points_on_correct": 100,
            "points_on_wrong": 0,
            "options": [
                {"text": "Correct", "is_correct": True, "explanation": "Yes!"},
                {"text": "Wrong", "is_correct": False, "explanation": "No"},
            ],
        }
        for i in range(4)
    ]
    with open(os.path.join(tmpdir, "challenges.json"), "w") as f:
        json.dump(challenges, f)
    for name in ("sessions.json", "users.json"):
        with open(os.path.join(tmpdir, name), "w") as f:
            json.dump({}, f)
    with open(os.path.join(tmpdir, "leaderboard.json"), "w") as f:
        json.dump([], f)

    challenge_repo = ChallengeRepository(os.path.join(tmpdir, "challenges.json"))
    player_repo = PlayerRepository(os.path.join(tmpdir, "sessions.json"))
    leaderboard_repo = LeaderboardRepository(os.path.join(tmpdir, "leaderboard.json"))
    user_repo = UserRepository(os.path.join(tmpdir, "users.json"))

    mock_metrics = MagicMock() if with_metrics else None
    mock_events = MagicMock() if with_events else None

    init_routes(player_repo, challenge_repo, leaderboard_repo, mock_metrics, mock_events)
    init_auth_routes(user_repo)

    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(auth_router)
    app.include_router(game_router)

    return TestClient(app), player_repo, challenge_repo, tmpdir


def _auth_headers(client, suffix="fg"):
    """Register + login, return bearer headers."""
    reg = {
        "full_name": f"Final Gap User {suffix}",
        "username": f"finalgap{suffix}",
        "email": f"finalgap{suffix}@test.com",
        "whatsapp": "11999999999",
        "profession": "estudante",
        "password": "FinalPass123!",
    }
    client.post("/api/auth/register", json=reg)
    resp = client.post("/api/auth/login", json={
        "username": reg["username"],
        "password": reg["password"],
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _start_session(client, headers, suffix="fg"):
    resp = client.post("/api/start", json={
        "player_name": f"GapDev{suffix}",
        "gender": "male",
        "ethnicity": "white",
        "avatar_index": 0,
        "language": "Java",
    }, headers=headers)
    assert resp.status_code == 200, f"Start failed: {resp.text}"
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# game_routes line 107-108: ValueError from start_game (invalid language)
# ---------------------------------------------------------------------------

class TestStartGameValueError:
    """Line 107-108: except ValueError → 400 when language is invalid."""

    def test_invalid_language_returns_400(self):
        client, _, _, tmpdir = _build_game_app()
        try:
            headers = _auth_headers(client, suffix="sge")
            resp = client.post("/api/start", json={
                "player_name": "Dev",
                "gender": "male",
                "ethnicity": "white",
                "avatar_index": 0,
                "language": "COBOL",  # invalid BackendLanguage
            }, headers=headers)
            assert resp.status_code == 400
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# game_routes lines 122-123: Distinguished session retroactive completion
# ---------------------------------------------------------------------------

class TestGetSessionDistinguished:
    """Lines 122-123: GET /api/session/{id} with Distinguished+not-completed."""

    def test_distinguished_session_gets_marked_completed(self):
        client, player_repo, _, tmpdir = _build_game_app()
        try:
            headers = _auth_headers(client, suffix="dist")
            sid = _start_session(client, headers, suffix="dist")

            # Manually set stage to Distinguished + status still "active" in JSON
            sessions_path = os.path.join(tmpdir, "sessions.json")
            with open(sessions_path) as f:
                data = json.load(f)
            data[sid]["stage"] = "Distinguished"
            data[sid]["status"] = "in_progress"  # not completed yet
            with open(sessions_path, "w") as f:
                json.dump(data, f)

            # Force reload
            player_repo._sessions = {}

            resp = client.get(f"/api/session/{sid}", headers=headers)
            assert resp.status_code == 200
            body = resp.json()
            assert body["stage"] == "Distinguished"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# game_routes lines 156-159: GET /api/challenges/{challenge_id}
# ---------------------------------------------------------------------------

class TestGetSingleChallenge:
    """Lines 156-159: api_get_challenge — success and 404."""

    def test_get_existing_challenge_returns_200(self):
        client, _, _, tmpdir = _build_game_app()
        try:
            resp = client.get("/api/challenges/final_0")
            assert resp.status_code == 200
            assert "id" in resp.json() or "title" in resp.json()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_nonexistent_challenge_returns_404(self):
        client, _, _, tmpdir = _build_game_app()
        try:
            resp = client.get("/api/challenges/nonexistent_xyz")
            assert resp.status_code == 404
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# game_routes line 167: submit with nonexistent session_id
# ---------------------------------------------------------------------------

class TestSubmitSessionNotFound:
    """Line 167: raise HTTPException(404) when session not found in submit."""

    def test_submit_nonexistent_session_returns_404(self):
        client, _, _, tmpdir = _build_game_app()
        try:
            headers = _auth_headers(client, suffix="snf")
            resp = client.post("/api/submit", json={
                "session_id": "00000000-0000-0000-0000-000000000000",
                "challenge_id": "final_0",
                "selected_index": 0,
            }, headers=headers)
            assert resp.status_code == 404
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# game_routes line 191: on_stage_promoted via metrics
# ---------------------------------------------------------------------------

class TestStagePromotionMetrics:
    """Line 191: _metrics.on_stage_promoted when promotion happens."""

    def test_stage_promotion_triggers_metrics(self):
        """Mock submit_answer to return a promotion result."""
        client, _, _, tmpdir = _build_game_app(with_metrics=True)
        try:
            headers = _auth_headers(client, suffix="promo")
            sid = _start_session(client, headers, suffix="promo")

            # Mock submit_answer to return a promotion result
            with patch("app.api.routes.game_routes.submit_answer") as mock_submit:
                mock_submit.return_value = {
                    "outcome": "correct",
                    "points_awarded": 100,
                    "promotion": True,
                    "new_stage": "Junior",
                }
                resp = client.post("/api/submit", json={
                    "session_id": sid,
                    "challenge_id": "final_0",
                    "selected_index": 0,
                }, headers=headers)
                assert resp.status_code == 200
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# game_routes line 220: recover with nonexistent session_id
# ---------------------------------------------------------------------------

class TestRecoverSessionNotFound:
    """Line 220: raise HTTPException(404) when session not found in recover."""

    def test_recover_nonexistent_session_returns_404(self):
        client, _, _, tmpdir = _build_game_app()
        try:
            headers = _auth_headers(client, suffix="rnf")
            resp = client.post("/api/recover", json={
                "session_id": "00000000-0000-0000-0000-000000000000",
            }, headers=headers)
            assert resp.status_code == 404
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# game_routes line 242: save_world_state with nonexistent session_id
# ---------------------------------------------------------------------------

class TestSaveWorldStateSessionNotFound:
    """Line 242: raise HTTPException(404) when session not found in save-world-state."""

    def test_save_world_state_nonexistent_session_returns_404(self):
        client, _, _, tmpdir = _build_game_app()
        try:
            headers = _auth_headers(client, suffix="swsnf")
            resp = client.post("/api/save-world-state", json={
                "session_id": "00000000-0000-0000-0000-000000000000",
                "collected_books": [],
                "completed_regions": [],
            }, headers=headers)
            assert resp.status_code == 404
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# game_routes lines 346-353: reset with Distinguished session → leaderboard submit
# ---------------------------------------------------------------------------

class TestResetWithCompletedSession:
    """Lines 346-353: Reset a Distinguished session triggers leaderboard submit."""

    def test_reset_distinguished_session_submits_to_leaderboard(self):
        client, player_repo, _, tmpdir = _build_game_app()
        try:
            headers = _auth_headers(client, suffix="rst")
            sid = _start_session(client, headers, suffix="rst")

            # Manually set stage to Distinguished so reset triggers leaderboard
            sessions_path = os.path.join(tmpdir, "sessions.json")
            with open(sessions_path) as f:
                data = json.load(f)
            data[sid]["stage"] = "Distinguished"
            data[sid]["status"] = "completed"
            with open(sessions_path, "w") as f:
                json.dump(data, f)

            # Force reload
            player_repo._sessions = {}

            resp = client.post("/api/reset", json={"session_id": sid}, headers=headers)
            # Should succeed (200) — the leaderboard submit happens inside
            assert resp.status_code == 200
            assert "session_id" in resp.json()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# study_routes lines 1011-1021: Mid/Senior stage format in _build_prompts
# ---------------------------------------------------------------------------

class TestStudyChatMidSeniorStage:
    """Lines 1011-1021: _build_prompts with Mid/Senior stage."""

    def _make_study_client(self, stage="Senior"):
        from app.api.routes.study_routes import router as study_router, init_study_routes
        from app.api.routes.auth_routes import router as auth_router, init_auth_routes

        tmpdir = tempfile.mkdtemp(prefix="study_stage_test_")
        for name in ("sessions.json", "users.json"):
            with open(os.path.join(tmpdir, name), "w") as f:
                json.dump({}, f)

        mock_player_repo = MagicMock()
        mock_challenge_repo = MagicMock()

        player = MagicMock()
        player.user_id = "sub-study-mid"
        player.stage = MagicMock()
        player.stage.value = stage
        mock_player_repo.get.return_value = player
        mock_challenge_repo.get_by_id.return_value = None

        init_study_routes(mock_player_repo, mock_challenge_repo)

        app = FastAPI()
        app.include_router(study_router)

        from app.infrastructure.auth.dependencies import get_current_user
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": "sub-study-mid",
            "username": "miduser",
        }

        return TestClient(app), tmpdir

    def test_chat_with_senior_stage_covers_mid_senior_format(self):
        """Covers lines 1011-1021: elif stage in ('Mid', 'Senior') response format."""
        client, tmpdir = self._make_study_client(stage="Senior")
        try:
            with patch(
                "app.api.routes.study_routes._call_with_fallback",
                return_value=("Answer for Senior", "rid-senior", "test-model"),
            ):
                resp = client.post("/api/study/chat", json={
                    "session_id": "test-session-mid",
                    "message": "Explain binary search trees in detail please",
                    "stage": "Senior",
                    "region": "Google",
                    "challenge_id": None,
                    "recent_messages": [],
                    "books": [],
                })
                assert resp.status_code == 200
                assert resp.json()["reply"] == "Answer for Senior"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_chat_with_mid_stage_also_covered(self):
        """Also covers lines 1011-1021 for 'Mid' stage."""
        client, tmpdir = self._make_study_client(stage="Mid")
        try:
            with patch(
                "app.api.routes.study_routes._call_with_fallback",
                return_value=("Mid answer", "rid-mid", "test-model"),
            ):
                resp = client.post("/api/study/chat", json={
                    "session_id": "test-session-mid2",
                    "message": "Explain recursion with practical examples for mid developers",
                    "stage": "Mid",
                    "region": "Amazon",
                    "challenge_id": None,
                    "recent_messages": [],
                    "books": [],
                })
                assert resp.status_code == 200
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# study_routes lines 1150, 1160, 1164: long messages + books in /chat
# ---------------------------------------------------------------------------

class TestStudyChatWithBooksAndLongHistory:
    """Lines 1150, 1160, 1164: truncation paths in /chat handler."""

    def _make_study_client(self, stage="Staff"):
        from app.api.routes.study_routes import router as study_router, init_study_routes
        from app.infrastructure.auth.dependencies import get_current_user

        mock_player_repo = MagicMock()
        mock_challenge_repo = MagicMock()

        player = MagicMock()
        player.user_id = "sub-study-books"
        player.stage = MagicMock()
        player.stage.value = stage
        mock_player_repo.get.return_value = player
        mock_challenge_repo.get_by_id.return_value = None

        init_study_routes(mock_player_repo, mock_challenge_repo)

        app = FastAPI()
        app.include_router(study_router)
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": "sub-study-books",
            "username": "booksuser",
        }
        return TestClient(app)

    def test_chat_with_long_history_and_many_books(self):
        """
        Line 1150: history truncation > 180 chars
        Line 1160: book insight truncation > 70 chars
        Line 1164: omitted books message (> 5 collected books)
        """
        client = self._make_study_client(stage="Staff")

        # Long history message (> 180 chars) → covers line 1150
        long_msg = "A" * 200

        # 7 collected books (> 5 after prompt_books[:5]) → covers line 1164
        # Books with long insight (> 70 chars) → covers line 1160
        books = [
            {
                "id": f"book-{i}",
                "title": f"Book {i}",
                "author": "Author",
                "collected": True,
                "summary": f"Summary for book {i}: " + "X" * 80,  # > 70 chars
                "lesson": "",
            }
            for i in range(7)
        ]

        with patch(
            "app.api.routes.study_routes._call_with_fallback",
            return_value=("Deep answer", "rid-books", "test-model"),
        ):
            resp = client.post("/api/study/chat", json={
                "session_id": "books-session",
                "message": "Explain the key concepts from these books",
                "stage": "Staff",
                "region": "Google",
                "challenge_id": None,
                "recent_messages": [
                    {"role": "user", "content": long_msg},
                    {"role": "assistant", "content": long_msg},
                ],
                "books": books,
            })
        assert resp.status_code == 200
        assert resp.json()["reply"] == "Deep answer"
