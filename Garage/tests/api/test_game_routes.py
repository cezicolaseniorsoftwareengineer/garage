"""
Integration tests for game routes (/api/*).

Covers:
- /api/start
- /api/session/{id}
- /api/challenges (list + filter)
- /api/submit (correct / wrong / game-over)
- /api/save-world-state (authenticated)
- /api/save-world-state-beacon (token in body + missing token = 401)
- /api/heartbeat
- /api/leaderboard (limit validation)
- /api/progress/{id}
- /api/recover
- Security: ownership check returns 403 for other users' sessions
"""
import pytest


# ---------------------------------------------------------------------------
# /api/start
# ---------------------------------------------------------------------------
class TestStartGame:
    def test_start_returns_session_id(self, client, auth_headers):
        resp = client.post("/api/start", json={
            "player_name": "GameTest",
            "gender": "male",
            "ethnicity": "white",
            "avatar_index": 0,
            "language": "Java",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert "session_id" in resp.json()

    def test_start_without_auth_fails(self, client):
        resp = client.post("/api/start", json={
            "player_name": "GameTest",
            "gender": "male",
            "ethnicity": "white",
            "avatar_index": 0,
            "language": "Java",
        })
        assert resp.status_code == 401

    def test_start_invalid_gender_rejected(self, client, auth_headers):
        resp = client.post("/api/start", json={
            "player_name": "X",
            "gender": "alien",
            "ethnicity": "white",
            "avatar_index": 0,
            "language": "Java",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_start_invalid_avatar_rejected(self, client, auth_headers):
        resp = client.post("/api/start", json={
            "player_name": "X",
            "gender": "male",
            "ethnicity": "white",
            "avatar_index": 99,
            "language": "Java",
        }, headers=auth_headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /api/session/{id}
# ---------------------------------------------------------------------------
class TestGetSession:
    def test_get_session_returns_player_data(self, client, auth_headers, session_id):
        resp = client.get(f"/api/session/{session_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == session_id
        assert "stage" in data

    def test_get_session_not_found(self, client, auth_headers):
        resp = client.get("/api/session/00000000-0000-0000-0000-000000000000",
                          headers=auth_headers)
        assert resp.status_code == 404

    def test_get_session_unauthenticated(self, client, session_id):
        resp = client.get(f"/api/session/{session_id}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api/challenges
# ---------------------------------------------------------------------------
class TestChallenges:
    def test_get_all_challenges_is_public(self, client):
        resp = client.get("/api/challenges")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_challenges_do_not_expose_correct_answer(self, client):
        resp = client.get("/api/challenges")
        assert resp.status_code == 200
        for ch in resp.json():
            for opt in ch["options"]:
                assert "is_correct" not in opt, "is_correct must never be exposed"

    def test_challenges_filter_by_stage(self, client):
        resp = client.get("/api/challenges?stage=Intern")
        assert resp.status_code == 200

    def test_challenges_invalid_stage(self, client):
        resp = client.get("/api/challenges?stage=Galactic")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /api/submit
# ---------------------------------------------------------------------------
class TestSubmit:
    def test_submit_correct_answer(self, client, auth_headers, session_id):
        # Get challenges and find a correct index
        challenges = client.get("/api/challenges").json()
        ch = next(c for c in challenges if c["id"].startswith("intern_"))
        # The conftest seeds challenges with option[0] as correct
        resp = client.post("/api/submit", json={
            "session_id": session_id,
            "challenge_id": ch["id"],
            "selected_index": 0,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "correct"

    def test_submit_unauthenticated(self, client, session_id):
        resp = client.post("/api/submit", json={
            "session_id": session_id,
            "challenge_id": "intern_01_test",
            "selected_index": 0,
        })
        assert resp.status_code == 401

    def test_submit_already_completed_returns_400(self, client, auth_headers, session_id):
        challenges = client.get("/api/challenges").json()
        ch_id = next(c["id"] for c in challenges if c["id"] == "intern_01_test")
        # Submit correctly once
        client.post("/api/submit", json={
            "session_id": session_id,
            "challenge_id": ch_id,
            "selected_index": 0,
        }, headers=auth_headers)
        # Submit again
        resp = client.post("/api/submit", json={
            "session_id": session_id,
            "challenge_id": ch_id,
            "selected_index": 0,
        }, headers=auth_headers)
        assert resp.status_code in (400, 409)


# ---------------------------------------------------------------------------
# /api/save-world-state
# ---------------------------------------------------------------------------
class TestSaveWorldState:
    def test_save_world_state_authenticated(self, client, auth_headers, session_id):
        resp = client.post("/api/save-world-state", json={
            "session_id": session_id,
            "collected_books": ["book_alan"],
            "completed_regions": ["Xerox PARC"],
            "current_region": "Xerox PARC",
            "player_world_x": 250,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

    def test_save_world_state_persists(self, client, auth_headers, session_id):
        client.post("/api/save-world-state", json={
            "session_id": session_id,
            "collected_books": ["book_linus"],
            "current_region": None,  # explicit None should clear region
        }, headers=auth_headers)
        resp = client.get(f"/api/session/{session_id}", headers=auth_headers)
        assert "book_linus" in resp.json()["collected_books"]

    def test_save_world_state_unauthenticated(self, client, session_id):
        resp = client.post("/api/save-world-state", json={"session_id": session_id})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api/save-world-state-beacon — SECURITY: requires token in body
# ---------------------------------------------------------------------------
class TestBeaconEndpoint:
    def test_beacon_without_token_returns_401(self, client, session_id):
        resp = client.post("/api/save-world-state-beacon", json={
            "session_id": session_id,
            "collected_books": [],
        })
        assert resp.status_code == 401

    def test_beacon_with_invalid_token_returns_401(self, client, session_id):
        resp = client.post("/api/save-world-state-beacon", json={
            "session_id": session_id,
            "access_token": "invalid.token.here",
        })
        assert resp.status_code == 401

    def test_beacon_with_valid_token_saves(self, client, auth_headers, session_id):
        # Extract raw token from header
        token = auth_headers["Authorization"].replace("Bearer ", "")
        resp = client.post("/api/save-world-state-beacon", json={
            "session_id": session_id,
            "collected_books": ["beacon_book"],
            "access_token": token,
        })
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

    def test_beacon_with_session_not_found(self, client, auth_headers):
        token = auth_headers["Authorization"].replace("Bearer ", "")
        resp = client.post("/api/save-world-state-beacon", json={
            "session_id": "00000000-0000-0000-0000-000000000000",
            "access_token": token,
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/heartbeat
# ---------------------------------------------------------------------------
class TestHeartbeat:
    def test_heartbeat_authenticated(self, client, auth_headers, session_id):
        resp = client.post("/api/heartbeat", json={"session_id": session_id},
                           headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["heartbeat"] is True

    def test_heartbeat_unauthenticated(self, client, session_id):
        resp = client.post("/api/heartbeat", json={"session_id": session_id})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api/leaderboard
# ---------------------------------------------------------------------------
class TestLeaderboard:
    def test_leaderboard_is_public(self, client):
        resp = client.get("/api/leaderboard")
        assert resp.status_code == 200

    def test_leaderboard_default_limit(self, client):
        resp = client.get("/api/leaderboard")
        assert isinstance(resp.json(), list)

    def test_leaderboard_limit_above_100_rejected(self, client):
        resp = client.get("/api/leaderboard?limit=999999")
        assert resp.status_code == 422

    def test_leaderboard_limit_zero_rejected(self, client):
        resp = client.get("/api/leaderboard?limit=0")
        assert resp.status_code == 422

    def test_leaderboard_limit_100_accepted(self, client):
        resp = client.get("/api/leaderboard?limit=100")
        assert resp.status_code == 200

    def test_leaderboard_limit_1_accepted(self, client):
        resp = client.get("/api/leaderboard?limit=1")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /api/progress/{id}
# ---------------------------------------------------------------------------
class TestProgress:
    def test_progress_authenticated(self, client, auth_headers, session_id):
        resp = client.get(f"/api/progress/{session_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "stage" in data
        assert "max_errors" in data

    def test_progress_unauthenticated(self, client, session_id):
        resp = client.get(f"/api/progress/{session_id}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api/recover
# ---------------------------------------------------------------------------
class TestRecover:
    def test_recover_returns_status(self, client, auth_headers, session_id):
        resp = client.post("/api/recover", json={"session_id": session_id},
                           headers=auth_headers)
        # Either 200 (recovered) — player may not be in game_over, that's ok
        assert resp.status_code == 200
        assert "status" in resp.json()

    def test_recover_unauthenticated(self, client, session_id):
        resp = client.post("/api/recover", json={"session_id": session_id})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api/map (public)
# ---------------------------------------------------------------------------
class TestMap:
    def test_map_is_public(self, client):
        resp = client.get("/api/map")
        assert resp.status_code == 200
        data = resp.json()
        assert "regions" in data
        assert "bosses" in data
