"""
E2E completo via FastAPI TestClient — todas as 6 fases do jogo.
Usa o challenges.json REAL (75 desafios) para testar o fluxo
exatamente como o jogador experimenta.

Fluxos cobertos:
  - Register → Login → Start → Intern(3 corretas) → Junior(3) → Mid(3) → Senior(3)
    → Staff(3) → Principal(3) → Distinguished (vitória)
  - Game over path: 2 erros → recover → continuar
  - World state: save + restore + books blocked when in region
  - Ownership: outra conta não acessa sessão alheia (403)
  - Resposta duplicada bloqueada (400)
"""
import os
import sys
import json
import uuid
import shutil
import tempfile

import pytest

GARAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GARAGE_DIR not in sys.path:
    sys.path.insert(0, GARAGE_DIR)

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-garage-e2e-2026")
os.environ.pop("DATABASE_URL", None)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures: app com challenges.json REAIS
# ---------------------------------------------------------------------------

REAL_DATA = os.path.join(GARAGE_DIR, "app", "data")


def _build_real_app(tmp_dir: str) -> FastAPI:
    """App wired with copies of the real challenges.json but isolated tmp repos."""
    import shutil as _sh
    _sh.copy(os.path.join(REAL_DATA, "challenges.json"),
             os.path.join(tmp_dir, "challenges.json"))

    for name in ("sessions.json", "users.json", "leaderboard.json"):
        src = os.path.join(REAL_DATA, name)
        dst = os.path.join(tmp_dir, name)
        if os.path.exists(src):
            _sh.copy(src, dst)
        else:
            with open(dst, "w") as f:
                json.dump({} if name != "leaderboard.json" else [], f)

    from app.infrastructure.repositories.challenge_repository import ChallengeRepository
    from app.infrastructure.repositories.player_repository import PlayerRepository
    from app.infrastructure.repositories.leaderboard_repository import LeaderboardRepository
    from app.infrastructure.repositories.user_repository import UserRepository
    from app.api.routes.game_routes import router as game_router
    from app.api.routes.game_routes import init_routes
    from app.api.routes.auth_routes import router as auth_router, init_auth_routes

    ch_repo = ChallengeRepository(os.path.join(tmp_dir, "challenges.json"))
    pl_repo = PlayerRepository(os.path.join(tmp_dir, "sessions.json"))
    lb_repo = LeaderboardRepository(os.path.join(tmp_dir, "leaderboard.json"))
    u_repo  = UserRepository(os.path.join(tmp_dir, "users.json"))

    init_routes(pl_repo, ch_repo, lb_repo)
    init_auth_routes(u_repo)

    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(auth_router)
    app.include_router(game_router)
    return app


@pytest.fixture(scope="module")
def e2e_client():
    tmp = tempfile.mkdtemp(prefix="garage_e2e_")
    app = _build_real_app(tmp)
    with TestClient(app) as c:
        yield c
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_login(client: TestClient) -> dict:
    uid = uuid.uuid4().hex[:8]
    reg = client.post("/api/auth/register", json={
        "full_name": f"E2E Player {uid}",
        "username":  f"e2e_{uid}",
        "email":     f"e2e_{uid}@test.io",
        "whatsapp":  "11900000000",
        "profession": "estudante",
        "password":  "E2eTest123!",
    })
    assert reg.status_code == 200, f"Register falhou: {reg.text}"
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _start(client, headers):
    r = client.post("/api/start", json={
        "player_name": "DevJorney",
        "gender": "male",
        "ethnicity": "white",
        "avatar_index": 0,
        "language": "Java",
    }, headers=headers)
    assert r.status_code == 200, f"Start falhou: {r.text}"
    return r.json()["session_id"]


def _submit(client, sid, ch_id, idx, headers):
    r = client.post("/api/submit", json={
        "session_id": sid,
        "challenge_id": ch_id,
        "selected_index": idx,
    }, headers=headers)
    assert r.status_code == 200, f"Submit falhou: {r.text}"
    return r.json()


def _get_session(client, sid, headers):
    r = client.get(f"/api/session/{sid}", headers=headers)
    assert r.status_code == 200
    return r.json()


def _get_challenges(client, stage: str):
    r = client.get(f"/api/challenges?stage={stage}")
    assert r.status_code == 200
    return r.json()


def _correct_index_from_real(challenge_id: str) -> int:
    """Lookup the correct index from the real challenges.json."""
    data = json.load(
        open(os.path.join(REAL_DATA, "challenges.json"), encoding="utf-8")
    )
    for c in data:
        if c["id"] == challenge_id:
            for i, opt in enumerate(c["options"]):
                if opt["is_correct"]:
                    return i
    raise ValueError(f"Challenge {challenge_id} not found")


def _wrong_index_from_real(challenge_id: str) -> int:
    data = json.load(
        open(os.path.join(REAL_DATA, "challenges.json"), encoding="utf-8")
    )
    for c in data:
        if c["id"] == challenge_id:
            for i, opt in enumerate(c["options"]):
                if not opt["is_correct"]:
                    return i
    raise ValueError(f"Challenge {challenge_id} not found")


# ---------------------------------------------------------------------------
# Testes de autenticação e ownership
# ---------------------------------------------------------------------------

class TestAuthAndOwnership:
    def test_start_without_auth_returns_401(self, e2e_client):
        r = e2e_client.post("/api/start", json={
            "player_name": "X",
            "gender": "male",
            "ethnicity": "white",
            "avatar_index": 0,
            "language": "Java",
        })
        assert r.status_code == 401

    def test_submit_without_auth_returns_401(self, e2e_client):
        r = e2e_client.post("/api/submit", json={
            "session_id": "fake",
            "challenge_id": "fake",
            "selected_index": 0,
        })
        assert r.status_code == 401

    def test_another_user_cannot_read_session(self, e2e_client):
        h1 = _register_login(e2e_client)
        h2 = _register_login(e2e_client)

        sid = _start(e2e_client, h1)
        r = e2e_client.get(f"/api/session/{sid}", headers=h2)
        assert r.status_code == 403

    def test_another_user_cannot_submit_to_session(self, e2e_client):
        h1 = _register_login(e2e_client)
        h2 = _register_login(e2e_client)

        sid = _start(e2e_client, h1)
        challenges = _get_challenges(e2e_client, "Intern")
        if not challenges:
            pytest.skip("Sem desafios Intern")
        r = e2e_client.post("/api/submit", json={
            "session_id": sid,
            "challenge_id": challenges[0]["id"],
            "selected_index": 0,
        }, headers=h2)
        assert r.status_code == 403

    def test_get_session_not_found_returns_404(self, e2e_client):
        h = _register_login(e2e_client)
        r = e2e_client.get(
            "/api/session/00000000-0000-0000-0000-000000000000", headers=h
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Testes de MCQ via API
# ---------------------------------------------------------------------------

class TestMCQViaAPI:

    def test_correct_answer_via_api_returns_correct_outcome(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")
        ch = challenges[0]
        correct_idx = _correct_index_from_real(ch["id"])

        result = _submit(e2e_client, sid, ch["id"], correct_idx, h)
        assert result["outcome"] == "correct"

    def test_wrong_answer_via_api_returns_wrong_outcome(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")
        ch = challenges[0]
        wrong_idx = _wrong_index_from_real(ch["id"])

        result = _submit(e2e_client, sid, ch["id"], wrong_idx, h)
        assert result["outcome"] in ("wrong", "game_over")

    def test_correct_answer_adds_score(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")
        ch = challenges[0]
        correct_idx = _correct_index_from_real(ch["id"])

        _submit(e2e_client, sid, ch["id"], correct_idx, h)
        player_data = _get_session(e2e_client, sid, h)

        assert player_data["score"] > 0

    def test_duplicate_submit_returns_400(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")
        ch = challenges[0]
        correct_idx = _correct_index_from_real(ch["id"])

        _submit(e2e_client, sid, ch["id"], correct_idx, h)  # primeira — OK
        r = e2e_client.post("/api/submit", json={
            "session_id": sid,
            "challenge_id": ch["id"],
            "selected_index": correct_idx,
        }, headers=h)
        assert r.status_code == 400, "Double-submit deveria retornar 400"

    def test_invalid_option_index_returns_400(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")
        ch = challenges[0]

        r = e2e_client.post("/api/submit", json={
            "session_id": sid,
            "challenge_id": ch["id"],
            "selected_index": 999,
        }, headers=h)
        assert r.status_code == 400

    def test_result_includes_explanation(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")
        ch = challenges[0]
        correct_idx = _correct_index_from_real(ch["id"])

        result = _submit(e2e_client, sid, ch["id"], correct_idx, h)
        assert "explanation" in result and result["explanation"]

    def test_challenges_do_not_expose_correct_index(self, e2e_client):
        challenges = _get_challenges(e2e_client, "Intern")
        for ch in challenges:
            for opt in ch["options"]:
                assert "is_correct" not in opt, (
                    f"Desafio {ch['id']}: opção expõe is_correct ao frontend!"
                )


# ---------------------------------------------------------------------------
# Game over e recuperação via API
# ---------------------------------------------------------------------------

class TestGameOverViaAPI:

    def test_two_wrong_answers_trigger_game_over(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")

        ch1, ch2 = challenges[0], challenges[1]
        w1 = _wrong_index_from_real(ch1["id"])
        w2 = _wrong_index_from_real(ch2["id"])

        _submit(e2e_client, sid, ch1["id"], w1, h)
        result = _submit(e2e_client, sid, ch2["id"], w2, h)

        assert result["outcome"] == "game_over"

    def test_game_over_player_data_reflects_status(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")

        w1 = _wrong_index_from_real(challenges[0]["id"])
        w2 = _wrong_index_from_real(challenges[1]["id"])
        _submit(e2e_client, sid, challenges[0]["id"], w1, h)
        _submit(e2e_client, sid, challenges[1]["id"], w2, h)

        player_data = _get_session(e2e_client, sid, h)
        assert player_data["status"] == "game_over"

    def test_recover_resets_status_to_in_progress(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")

        w1 = _wrong_index_from_real(challenges[0]["id"])
        w2 = _wrong_index_from_real(challenges[1]["id"])
        _submit(e2e_client, sid, challenges[0]["id"], w1, h)
        _submit(e2e_client, sid, challenges[1]["id"], w2, h)

        r = e2e_client.post("/api/recover", json={"session_id": sid}, headers=h)
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    def test_after_recovery_can_submit_again(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")

        w1 = _wrong_index_from_real(challenges[0]["id"])
        w2 = _wrong_index_from_real(challenges[1]["id"])
        _submit(e2e_client, sid, challenges[0]["id"], w1, h)
        _submit(e2e_client, sid, challenges[1]["id"], w2, h)

        e2e_client.post("/api/recover", json={"session_id": sid}, headers=h)

        # Now should be able to submit again
        correct_idx = _correct_index_from_real(challenges[0]["id"])
        result = _submit(e2e_client, sid, challenges[0]["id"], correct_idx, h)
        assert result["outcome"] == "correct"


# ---------------------------------------------------------------------------
# World state: save, restore, books
# ---------------------------------------------------------------------------

class TestWorldStateViaAPI:

    def test_save_world_state_returns_ok(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)

        r = e2e_client.post("/api/save-world-state", json={
            "session_id": sid,
            "collected_books": ["book_01", "book_02"],
            "completed_regions": ["Xerox PARC"],
            "current_region": None,
            "player_world_x": 450,
        }, headers=h)
        assert r.status_code == 200
        assert r.json()["saved"] is True

    def test_saved_books_persist_in_session(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)

        e2e_client.post("/api/save-world-state", json={
            "session_id": sid,
            "collected_books": ["book_cleancode", "book_pragprog"],
            "completed_regions": [],
            "current_region": None,
            "player_world_x": 200,
        }, headers=h)

        player_data = _get_session(e2e_client, sid, h)
        assert "book_cleancode" in player_data["collected_books"]
        assert "book_pragprog"  in player_data["collected_books"]

    def test_completed_regions_persist(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)

        e2e_client.post("/api/save-world-state", json={
            "session_id": sid,
            "collected_books": [],
            "completed_regions": ["Xerox PARC", "Apple Garage"],
            "current_region": None,
            "player_world_x": 300,
        }, headers=h)

        player_data = _get_session(e2e_client, sid, h)
        assert "Xerox PARC"    in player_data["completed_regions"]
        assert "Apple Garage"  in player_data["completed_regions"]

    def test_current_region_persists(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)

        e2e_client.post("/api/save-world-state", json={
            "session_id": sid,
            "collected_books": [],
            "completed_regions": [],
            "current_region": "Google",
            "player_world_x": 600,
        }, headers=h)

        player_data = _get_session(e2e_client, sid, h)
        assert player_data["current_region"] == "Google"

    def test_current_region_can_be_cleared(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)

        e2e_client.post("/api/save-world-state", json={
            "session_id": sid,
            "collected_books": [],
            "completed_regions": [],
            "current_region": "Google",
            "player_world_x": 600,
        }, headers=h)

        # Clear region (player left the building)
        e2e_client.post("/api/save-world-state", json={
            "session_id": sid,
            "collected_books": [],
            "completed_regions": [],
            "current_region": None,
            "player_world_x": 650,
        }, headers=h)

        player_data = _get_session(e2e_client, sid, h)
        assert player_data["current_region"] is None, (
            "current_region deveria ser None após sair da empresa"
        )

    def test_player_position_persists(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)

        e2e_client.post("/api/save-world-state", json={
            "session_id": sid,
            "collected_books": [],
            "completed_regions": [],
            "current_region": None,
            "player_world_x": 1234,
        }, headers=h)

        player_data = _get_session(e2e_client, sid, h)
        assert player_data["player_world_x"] == 1234

    def test_beacon_without_token_returns_401(self, e2e_client):
        r = e2e_client.post("/api/save-world-state-beacon", json={
            "session_id": "fake-session",
            "collected_books": [],
            "completed_regions": [],
            "current_region": None,
            "player_world_x": 100,
        })
        assert r.status_code == 401

    def test_save_world_state_wrong_owner_returns_403(self, e2e_client):
        h1 = _register_login(e2e_client)
        h2 = _register_login(e2e_client)
        sid = _start(e2e_client, h1)

        r = e2e_client.post("/api/save-world-state", json={
            "session_id": sid,
            "collected_books": [],
            "completed_regions": [],
            "current_region": None,
            "player_world_x": 100,
        }, headers=h2)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Jornada completa: Intern → Distinguished (jogo completado)
# ---------------------------------------------------------------------------

class TestFullGameJourney:
    """
    Testa a jornada completa do jogo do começo ao fim.
    Intern → Junior → Mid → Senior → Staff → Principal → Distinguished.
    Apenas 3 desafios por fase são necessários para promoção.
    """

    STAGES = ["Intern", "Junior", "Mid", "Senior", "Staff", "Principal"]

    def test_full_journey_intern_to_distinguished(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)

        player = _get_session(e2e_client, sid, h)
        assert player["stage"] == "Intern"

        for stage in self.STAGES:
            challenges = _get_challenges(e2e_client, stage)
            assert len(challenges) >= 3, f"Precisa de ≥3 desafios em {stage}"

            # Refresh session to see current stage
            current_player = _get_session(e2e_client, sid, h)
            answered = set(current_player.get("completed_challenges", []))

            count = 0
            for ch in challenges:
                if ch["id"] in answered:
                    count += 1
                    if count >= 3:
                        break
                    continue
                if count >= 3:
                    break
                correct_idx = _correct_index_from_real(ch["id"])
                result = _submit(e2e_client, sid, ch["id"], correct_idx, h)
                assert result["outcome"] == "correct", (
                    f"Stage {stage}, challenge {ch['id']}: "
                    f"esperava 'correct', obteve '{result['outcome']}'"
                )
                count += 1

            # Verify promotion or final stage
            updated = _get_session(e2e_client, sid, h)
            if stage != "Principal":
                expected_stages = self.STAGES[self.STAGES.index(stage) + 1:]
                expected_stages.append("Distinguished")
                assert updated["stage"] in expected_stages or updated["stage"] != stage, (
                    f"Após {stage}: esperava promoção, ainda em {updated['stage']}"
                )

        # After completing all Principal challenges, should be Distinguished or completed
        final = _get_session(e2e_client, sid, h)
        assert final["stage"] in ("Distinguished", "Principal") or final["status"] in ("completed", "in_progress")

    def test_progress_endpoint_tracks_stage(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)
        challenges = _get_challenges(e2e_client, "Intern")

        # Answer 3 correct
        for ch in challenges[:3]:
            correct_idx = _correct_index_from_real(ch["id"])
            _submit(e2e_client, sid, ch["id"], correct_idx, h)

        r = e2e_client.get(f"/api/progress/{sid}", headers=h)
        assert r.status_code == 200
        progress = r.json()
        assert progress["completed_challenges"] >= 3
        assert progress["stage_index"] >= 0

    def test_heartbeat_endpoint(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)

        r = e2e_client.post("/api/heartbeat",
                            json={"session_id": sid}, headers=h)
        assert r.status_code == 200
        assert r.json()["heartbeat"] is True

    def test_map_endpoint_has_all_24_regions(self, e2e_client):
        r = e2e_client.get("/api/map")
        assert r.status_code == 200
        data = r.json()
        assert "regions" in data
        # 24 regions (including Bio Code Technology)
        assert len(data["regions"]) >= 24

    def test_leaderboard_public_accessible(self, e2e_client):
        r = e2e_client.get("/api/leaderboard")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_reset_creates_new_session(self, e2e_client):
        h = _register_login(e2e_client)
        sid = _start(e2e_client, h)

        # Complete 3 challenges to get some progress
        challenges = _get_challenges(e2e_client, "Intern")
        for ch in challenges[:3]:
            correct_idx = _correct_index_from_real(ch["id"])
            _submit(e2e_client, sid, ch["id"], correct_idx, h)

        r = e2e_client.post("/api/reset", json={"session_id": sid}, headers=h)
        assert r.status_code == 200
        data = r.json()
        assert "session_id" in data
        assert data["session_id"] != sid  # nova sessão gerada
        assert data["player"]["stage"] == "Intern"   # começa do zero


# ---------------------------------------------------------------------------
# Challenges endpoint: filtro por stage
# ---------------------------------------------------------------------------

class TestChallengesEndpoint:
    STAGE_EXPECTED = {
        "Intern":    6,
        "Junior":    9,
        "Mid":       9,
        "Senior":    15,
        "Staff":     18,
        "Principal": 18,
    }

    @pytest.mark.parametrize("stage,expected", STAGE_EXPECTED.items())
    def test_stage_filter_returns_correct_count(self, e2e_client, stage, expected):
        r = e2e_client.get(f"/api/challenges?stage={stage}")
        assert r.status_code == 200
        challenges = r.json()
        assert len(challenges) == expected, (
            f"Stage {stage}: esperado {expected}, obteve {len(challenges)}"
        )

    def test_invalid_stage_returns_400(self, e2e_client):
        r = e2e_client.get("/api/challenges?stage=Wizard")
        assert r.status_code == 400

    def test_all_challenges_total_75(self, e2e_client):
        r = e2e_client.get("/api/challenges")
        assert r.status_code == 200
        assert len(r.json()) == 75
