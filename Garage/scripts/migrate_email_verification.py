"""Migration: add email_verified column and email_verifications table.

Run once on the database before deploying the verification feature.

Safe to run multiple times (idempotent via IF NOT EXISTS).
"""
import os
import sys

# Resolve project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)  # Garage/
ROOT_DIR = os.path.dirname(PROJECT_DIR)    # workspace root (for .env)

sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))
load_dotenv(os.path.join(PROJECT_DIR, ".env"))  # fallback

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("[ERROR] DATABASE_URL not set. Aborting.")
    sys.exit(1)

from sqlalchemy import create_engine, text

engine = create_engine(DATABASE_URL)

MIGRATIONS = [
    # 1. Add email_verified to users (DEFAULT TRUE = existing users stay verified)
    """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE;
    """,

    # 2. Create email_verifications table
    """
    CREATE TABLE IF NOT EXISTS email_verifications (
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash   VARCHAR(64) NOT NULL,
        expires_at   TIMESTAMPTZ NOT NULL,
        used_at      TIMESTAMPTZ,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,

    # 3. Index for fast lookup by user_id
    """
    CREATE INDEX IF NOT EXISTS idx_email_verif_user_id
    ON email_verifications (user_id);
    """,
]

def run():
    with engine.begin() as conn:
        for i, sql in enumerate(MIGRATIONS, 1):
            print(f"[{i}/{len(MIGRATIONS)}] Running migration...")
            conn.execute(text(sql.strip()))
            print(f"    ✅ Done.")
    print("\n✅ email_verification migration complete.")
    print("   All existing users have email_verified=TRUE (grandfathered).")
    print("   New registrations will require e-mail verification.")

if __name__ == "__main__":
    run()
