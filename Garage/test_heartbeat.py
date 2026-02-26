"""Test heartbeat endpoint and online presence system."""
import os
import sys
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.infrastructure.database.connection import init_engine, get_session_factory
from app.infrastructure.repositories.pg_player_repository import PgPlayerRepository
from app.infrastructure.database.models import GameSessionModel

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not set. Cannot test PostgreSQL online presence.")
    sys.exit(1)

print("=" * 70)
print("TESTING HEARTBEAT & ONLINE PRESENCE SYSTEM")
print("=" * 70)

try:
    init_engine()
    sf = get_session_factory()
    player_repo = PgPlayerRepository(sf)

    # 1. Check all sessions
    with sf() as session:
        all_sessions = session.query(GameSessionModel).all()
        print(f"\n📊 Total sessions in database: {len(all_sessions)}")

        if all_sessions:
            print("\nSessions:")
            for s in all_sessions[:5]:  # Show first 5
                print(f"  - ID: {s.id}")
                print(f"    Name: {s.name}")
                print(f"    Status: {s.status}")
                print(f"    Updated: {s.updated_at}")
                print(f"    User ID: {s.user_id}")
                print()

    # 2. Check active sessions (last 5 minutes)
    active_5min = player_repo.get_active_sessions(minutes=5)
    print(f"\n🟢 Active sessions (last 5 min): {len(active_5min)}")

    if active_5min:
        for s in active_5min:
            print(f"  - {s['player_name']} (stage: {s['stage']}, score: {s['score']})")
            print(f"    Last active: {s.get('last_active_at', 'N/A')}")
    else:
        print("  (none)")

    # 3. Check sessions by status
    with sf() as session:
        in_progress = session.query(GameSessionModel).filter_by(status="in_progress").count()
        completed = session.query(GameSessionModel).filter_by(status="completed").count()
        game_over = session.query(GameSessionModel).filter_by(status="game_over").count()

        print(f"\n📈 Sessions by status:")
        print(f"  - in_progress: {in_progress}")
        print(f"  - completed: {completed}")
        print(f"  - game_over: {game_over}")

    # 4. Check sessions updated recently
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    with sf() as session:
        recent = session.query(GameSessionModel).filter(
            GameSessionModel.updated_at >= cutoff
        ).all()

        print(f"\n⏱️ Sessions updated in last 5 minutes: {len(recent)}")
        if recent:
            for s in recent:
                age_seconds = (datetime.now(timezone.utc) - s.updated_at).total_seconds()
                print(f"  - {s.name} (status: {s.status}, {int(age_seconds)}s ago)")

    # 5. Diagnose why active sessions might be empty
    print(f"\n🔍 DIAGNOSIS:")
    if len(all_sessions) == 0:
        print("  ❌ No sessions in database at all")
    elif in_progress == 0:
        print("  ❌ No sessions with status='in_progress'")
    elif len(recent) == 0:
        print("  ❌ No sessions updated in last 5 minutes")
        print("     → Heartbeat not working OR no active players")
    else:
        print("  ✅ System working correctly!")

except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
