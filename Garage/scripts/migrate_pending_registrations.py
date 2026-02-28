"""Migration: create pending_registrations table + clean up ghost unverified users.

Run once:
  python scripts/migrate_pending_registrations.py

Safe to run multiple times (idempotent).
"""
import os
import sys

# Ensure the project root is in sys.path
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE, ".env"))

from app.infrastructure.database.connection import init_engine, get_session_factory
from app.infrastructure.database.models import Base, PendingRegistrationModel, UserModel


def run():
    print("[migrate] Initialising engine...")
    init_engine()

    from app.infrastructure.database.connection import _engine
    if _engine is None:
        print("[migrate] ERROR: DATABASE_URL not set or engine failed to init.")
        sys.exit(1)

    # Create pending_registrations if it doesn't exist
    print("[migrate] Creating pending_registrations table (if not exists)...")
    PendingRegistrationModel.__table__.create(bind=_engine, checkfirst=True)
    print("[migrate] pending_registrations table: OK")

    # Clean up ghost users: users with email_verified=False that were created
    # under the old insecure flow (saved to users table before verification).
    _sf = get_session_factory()
    with _sf() as session:
        ghosts = (
            session.query(UserModel)
            .filter(UserModel.email_verified == False)
            .all()
        )

        if not ghosts:
            print("[migrate] No ghost (unverified) users found. Database is clean.")
            return

        print(f"[migrate] Found {len(ghosts)} ghost unverified user(s):")
        for u in ghosts:
            print(f"  - {u.username} / {u.email} (id={u.id})")

        confirm = input("\nDelete all ghost users? [y/N] ").strip().lower()
        if confirm != "y":
            print("[migrate] Skipped deletion. You can rerun this script to delete later.")
            return

        from sqlalchemy import text
        for u in ghosts:
            uid = u.id
            # Cascade manually (same order as pg_user_repository.delete_user)
            session.execute(text(
                "DELETE FROM attempts WHERE session_id IN "
                "(SELECT id FROM game_sessions WHERE user_id = :uid)"
            ), {"uid": uid})
            session.execute(text("DELETE FROM leaderboard_entries WHERE user_id = :uid"), {"uid": uid})
            session.execute(text("DELETE FROM game_sessions WHERE user_id = :uid"), {"uid": uid})
            session.execute(text("DELETE FROM email_verifications WHERE user_id = :uid"), {"uid": uid})
            session.execute(text("DELETE FROM user_metrics WHERE user_id = :uid"), {"uid": uid})
            session.execute(text("DELETE FROM game_events WHERE user_id = :uid"), {"uid": uid})
            session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
            print(f"  [deleted] {u.username} / {u.email}")

        session.commit()
        print(f"[migrate] {len(ghosts)} ghost user(s) deleted. Database is now clean.")


if __name__ == "__main__":
    run()
