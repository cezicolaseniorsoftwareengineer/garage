"""Full system integration test - validates entire GARAGE game stack."""
import json
import os
import subprocess
import sys
from datetime import datetime

from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

print("Database: " + ("PostgreSQL (Neon)" if DATABASE_URL else "JSON (local)"))
print("Time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


tests = []


def test(name):
    """Decorator to track test results."""
    def decorator(func):
        def wrapper():
            print("\nTesting: " + name + "...", end=" ")
            try:
                func()
                print("PASS")
                tests.append((name, "PASS", None))
            except AssertionError as exc:
                print("FAIL: " + str(exc))
                tests.append((name, "FAIL", str(exc)))
            except Exception as exc:
                err = type(exc).__name__ + ": " + str(exc)
                print("ERROR: " + err)
                tests.append((name, "ERROR", err))
        return wrapper
    return decorator


# ============================================================================
# Test 1: Database Connection
# ============================================================================

@test("Database Connection")
def test_database():
    if DATABASE_URL:
        from app.infrastructure.database.connection import init_engine, check_health

        init_engine()
        assert check_health(), "Database health check failed"
    else:
        assert os.path.exists(os.path.join("app", "data", "challenges.json")), "challenges.json missing"


# ============================================================================
# Test 2: Repositories Initialization
# ============================================================================

@test("Repositories Initialization")
def test_repos():
    if DATABASE_URL:
        from app.infrastructure.database.connection import init_engine, get_session_factory
        from app.infrastructure.repositories.pg_challenge_repository import PgChallengeRepository
        from app.infrastructure.repositories.pg_player_repository import PgPlayerRepository
        from app.infrastructure.repositories.pg_user_repository import PgUserRepository
        from app.infrastructure.repositories.pg_leaderboard_repository import PgLeaderboardRepository

        init_engine()
        session_factory = get_session_factory()

        challenge_repo = PgChallengeRepository(session_factory)
        PgPlayerRepository(session_factory)
        PgUserRepository(session_factory)
        PgLeaderboardRepository(session_factory)

        challenges = challenge_repo.get_all()
        assert len(challenges) > 0, "No challenges loaded"
        assert len(challenges) == 72, "Expected 72 challenges, got " + str(len(challenges))
    else:
        from app.infrastructure.repositories.challenge_repository import ChallengeRepository

        repo = ChallengeRepository(os.path.join("app", "data", "challenges.json"))
        challenges = repo.get_all()
        assert len(challenges) == 72, "Expected 72 challenges, got " + str(len(challenges))


# ============================================================================
# Test 3: All 24 Challenges Validate
# ============================================================================

@test("All 24 Challenges Validate")
def test_challenges():
    result = subprocess.run(
        ["node", "test_all_challenges.js"],
        capture_output=True,
        text=True,
        cwd=BASE_DIR,
    )

    assert result.returncode == 0, "Challenge validation failed"
    assert "PASSED, 0 FAILED" in result.stdout, "Challenge validation output missing"
    assert "out of 24" in result.stdout, "Expected 24 code challenges"


# ============================================================================
# Test 4: FastAPI Routes Load
# ============================================================================

@test("FastAPI Routes Load")
def test_routes():
    from app.main import app

    routes = [r.path for r in app.routes]
    critical = [
        "/",
        "/health",
        "/admin",
        "/api/auth/register",
        "/api/auth/login",
        "/api/start",
        "/api/submit",
        "/api/heartbeat",
        "/api/admin/dashboard",
        "/api/admin/online",
    ]

    for endpoint in critical:
        assert endpoint in routes, "Missing route: " + endpoint


# ============================================================================
# Test 5: Authentication System
# ============================================================================

@test("Authentication System")
def test_auth():
    from app.infrastructure.auth.password import hash_password, verify_password
    from app.infrastructure.auth.jwt_handler import create_access_token, verify_token

    pwd = "test123"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed), "Password verification failed"
    assert not verify_password("wrong", hashed), "Wrong password accepted"

    token = create_access_token("test123", "testuser", "player")
    assert token, "Token creation failed"

    payload = verify_token(token)
    assert payload.get("sub") == "test123", "Token payload wrong"
    assert payload.get("username") == "testuser", "Token username wrong"


# ============================================================================
# Test 6: Java Code Analyzer
# ============================================================================

@test("Java Code Analyzer")
def test_java_analyzer():
    test_code = """
class TempTest {
    public static void main(String[] args) {
        System.out.println(\"Hello\");
    }
}
"""

    java_file = "temp_test.java"
    with open(java_file, "w", encoding="utf-8") as f:
        f.write(test_code)

    try:
        result = subprocess.run(
            ["javac", java_file],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "javac failed: " + result.stderr
    finally:
        for file_name in ["temp_test.java", "TempTest.class"]:
            if os.path.exists(file_name):
                os.remove(file_name)


# ============================================================================
# Test 7: Heartbeat System
# ============================================================================

@test("Heartbeat System (Online Presence)")
def test_heartbeat_system():
    if DATABASE_URL:
        from app.infrastructure.database.connection import init_engine, get_session_factory
        from app.infrastructure.repositories.pg_player_repository import PgPlayerRepository

        init_engine()
        session_factory = get_session_factory()
        player_repo = PgPlayerRepository(session_factory)

        assert hasattr(player_repo, "get_active_sessions"), "get_active_sessions missing"
        active = player_repo.get_active_sessions(minutes=5)
        assert isinstance(active, list), "get_active_sessions should return list"


# ============================================================================
# Test 8: SCALE_MISSIONS Configuration
# ============================================================================

@test("SCALE_MISSIONS Configuration")
def test_scale_missions():
    with open(os.path.join("app", "static", "game.js"), "r", encoding="utf-8") as f:
        content = f.read()

    assert "SCALE_MISSIONS = {" in content, "SCALE_MISSIONS not found"

    companies = [
        "code_var",
        "code_fizzbuzz",
        "code_hashmap",
        "code_queue",
        "code_bsearch",
        "code_anagram",
        "code_kadane",
        "code_hashset",
        "code_twosum",
        "code_fibonacci",
        "code_sort",
        "code_mergesort",
        "code_bfs",
        "code_palindrome",
        "code_reverse",
        "code_heap",
        "code_dp",
        "code_tree",
    ]

    for company in companies:
        assert (company + ":") in content, "Missing SCALE_MISSION: " + company


# ============================================================================
# Test 9: Frontend Files Exist
# ============================================================================

@test("Frontend Files Exist")
def test_frontend_files():
    files = [
        os.path.join("app", "static", "index.html"),
        os.path.join("app", "static", "game.js"),
        os.path.join("app", "static", "style.css"),
        os.path.join("app", "static", "admin.html"),
    ]

    for file_path in files:
        assert os.path.exists(file_path), "Missing file: " + file_path


# ============================================================================
# Test 10: Environment Variables
# ============================================================================

@test("Environment Variables")
def test_env():
    required = ["JWT_SECRET_KEY", "ADMIN_PASSWORD"]

    for var in required:
        value = os.environ.get(var)
        assert value, "Missing environment variable: " + var
        assert len(value) >= 8, var + " too short (< 8 chars)"


# ============================================================================
# Test 11: Data Files Integrity
# ============================================================================

@test("Data Files Integrity")
def test_data_files():
    with open(os.path.join("app", "data", "challenges.json"), "r", encoding="utf-8") as f:
        challenges = json.load(f)

    assert len(challenges) == 72, "Expected 72 challenges, got " + str(len(challenges))

    for ch in challenges:
        assert "id" in ch, "Challenge missing 'id'"
        assert "required_stage" in ch, "Challenge missing 'required_stage'"
        assert "region" in ch, "Challenge missing 'region'"
        assert "title" in ch, "Challenge missing 'title'"
        assert "description" in ch, "Challenge missing 'description'"


# ============================================================================
# Test 12: Metrics & Events (if PostgreSQL)
# ============================================================================

@test("Metrics & Events System")
def test_metrics_events():
    if DATABASE_URL:
        from app.infrastructure.database.connection import init_engine, get_session_factory
        from app.application.metrics_service import MetricsService
        from app.application.event_service import EventService

        init_engine()
        session_factory = get_session_factory()

        metrics_service = MetricsService(session_factory)
        event_service = EventService(session_factory)

        assert metrics_service is not None
        assert event_service is not None


# ============================================================================
# Run All Tests
# ============================================================================

print("\n" + "=" * 80)
print("RUNNING TESTS")
print("=" * 80)

test_database()
test_repos()
test_challenges()
test_routes()
test_auth()
test_java_analyzer()
test_heartbeat_system()
test_scale_missions()
test_frontend_files()
test_env()
test_data_files()
test_metrics_events()


# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

passed = sum(1 for _, status, _ in tests if status == "PASS")
failed = sum(1 for _, status, _ in tests if status == "FAIL")
errors = sum(1 for _, status, _ in tests if status == "ERROR")

for name, status, msg in tests:
    print("- " + name + ": " + status)
    if msg:
        print("  -> " + msg)

print("\n" + "=" * 80)
print("TOTAL: " + str(len(tests)) + " tests")
print("  PASSED: " + str(passed))
print("  FAILED: " + str(failed))
print("  ERRORS: " + str(errors))
print("=" * 80)

if failed > 0 or errors > 0:
    print("\nSYSTEM NOT READY FOR PRODUCTION")
    sys.exit(1)
else:
    print("\nALL SYSTEMS GREEN - READY FOR PRODUCTION")
    sys.exit(0)
