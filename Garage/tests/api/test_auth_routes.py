"""
Integration tests for auth routes (/api/auth/*).

Uses the shared TestClient from conftest.py (JSON repos, no real DB).
"""
import pytest


class TestRegister:
    def test_register_new_user(self, client):
        resp = client.post("/api/auth/register", json={
            "full_name": "New Player",
            "username": "newplayer_auth",
            "email": "newplayer@test.com",
            "whatsapp": "11988888888",
            "profession": "estudante",
            "password": "Secure123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    def test_register_duplicate_username(self, client):
        payload = {
            "full_name": "Dup User",
            "username": "dupuser_test",
            "email": "dup1@test.com",
            "whatsapp": "11977777777",
            "profession": "autonomo",
            "password": "Pass123!",
        }
        client.post("/api/auth/register", json=payload)
        # Try again with same username
        payload["email"] = "dup2@test.com"
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code in (400, 409)

    def test_register_invalid_profession(self, client):
        resp = client.post("/api/auth/register", json={
            "full_name": "Bad Prof",
            "username": "badprof_x",
            "email": "bp@test.com",
            "whatsapp": "11900000000",
            "profession": "hacker",  # invalid
            "password": "Pass123!",
        })
        assert resp.status_code == 422

    def test_register_short_password_rejected(self, client):
        resp = client.post("/api/auth/register", json={
            "full_name": "Short Pass",
            "username": "shortpass_x",
            "email": "sp@test.com",
            "whatsapp": "11900000000",
            "profession": "estudante",
            "password": "ab",  # too short
        })
        assert resp.status_code == 422


class TestLogin:
    def test_login_valid_credentials(self, client, auth_headers):
        # auth_headers fixture already registered and logged in
        assert auth_headers["Authorization"].startswith("Bearer ")

    def test_login_wrong_password(self, client):
        # Register then try wrong password
        client.post("/api/auth/register", json={
            "full_name": "Login Test",
            "username": "logintest_x",
            "email": "lt@test.com",
            "whatsapp": "11911111111",
            "profession": "estudante",
            "password": "CorrectPass1!",
        })
        resp = client.post("/api/auth/login", json={
            "username": "logintest_x",
            "password": "WrongPass999!",
        })
        assert resp.status_code in (401, 403)

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "ghost_nobody_zzz",
            "password": "AnyPass123!",
        })
        assert resp.status_code in (401, 404)

    def test_login_returns_access_and_refresh_tokens(self, client):
        client.post("/api/auth/register", json={
            "full_name": "Token Test",
            "username": "tokentest_x",
            "email": "tt@test.com",
            "whatsapp": "11922222222",
            "profession": "empresario",
            "password": "TokenPass1!",
        })
        resp = client.post("/api/auth/login", json={
            "username": "tokentest_x",
            "password": "TokenPass1!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data


class TestProfile:
    def test_get_profile_authenticated(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "username" in data

    def test_get_profile_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestRefreshToken:
    def test_refresh_token_works(self, client):
        client.post("/api/auth/register", json={
            "full_name": "Refresh Test",
            "username": "refreshtest_x",
            "email": "rt@test.com",
            "whatsapp": "11933333333",
            "profession": "estudante",
            "password": "RefreshPass1!",
        })
        login = client.post("/api/auth/login", json={
            "username": "refreshtest_x",
            "password": "RefreshPass1!",
        })
        refresh_token = login.json()["refresh_token"]
        resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_refresh_with_invalid_token(self, client):
        resp = client.post("/api/auth/refresh", json={"refresh_token": "not.a.real.token"})
        assert resp.status_code in (401, 422)
