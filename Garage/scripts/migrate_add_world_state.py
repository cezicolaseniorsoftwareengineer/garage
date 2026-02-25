#!/usr/bin/env python3
"""Migration script to add world state persistence columns to game_sessions table.

Run this script once to add the new columns for:
- collected_books: books the player has collected
- completed_regions: regions/companies the player has completed
- current_region: the region the player is currently in (locked)
- player_world_x: the player's X position in the world

Usage:
    python scripts/migrate_add_world_state.py
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
env_file = project_root / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

from sqlalchemy import text
from app.infrastructure.database.connection import init_engine, get_engine


def main():
    print("\n" + "=" * 70)
    print("GARAGE - World State Migration")
    print("=" * 70)

    # Initialize engine
    init_engine()
    engine = get_engine()

    if engine is None:
        print("[ERROR] Database engine not initialized. Check DATABASE_URL.")
        return False

    migration_statements = [
        # Add collected_books column
        """
        ALTER TABLE game_sessions
        ADD COLUMN IF NOT EXISTS collected_books VARCHAR[] DEFAULT '{}' NOT NULL;
        """,
        # Add completed_regions column
        """
        ALTER TABLE game_sessions
        ADD COLUMN IF NOT EXISTS completed_regions VARCHAR[] DEFAULT '{}' NOT NULL;
        """,
        # Add current_region column
        """
        ALTER TABLE game_sessions
        ADD COLUMN IF NOT EXISTS current_region VARCHAR(50) DEFAULT NULL;
        """,
        # Add player_world_x column
        """
        ALTER TABLE game_sessions
        ADD COLUMN IF NOT EXISTS player_world_x INTEGER DEFAULT 100 NOT NULL;
        """,
    ]

    try:
        with engine.connect() as conn:
            for stmt in migration_statements:
                print(f"[MIGRATE] Executing: {stmt.strip()[:60]}...")
                conn.execute(text(stmt))
            conn.commit()

        print("\n[SUCCESS] Migration completed successfully!")
        print("[INFO] New columns added to game_sessions table:")
        print("  - collected_books: VARCHAR[] (array of book IDs)")
        print("  - completed_regions: VARCHAR[] (array of region names)")
        print("  - current_region: VARCHAR(50) (current locked region)")
        print("  - player_world_x: INTEGER (player X position)")
        return True

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
