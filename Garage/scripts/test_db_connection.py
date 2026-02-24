#!/usr/bin/env python3
"""Test Neon PostgreSQL connection and create tables if needed."""
import os
import sys
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv
env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_file)

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    print("[TEST] Validating Neon PostgreSQL connection...")

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("[ERROR] DATABASE_URL not set. Set it in .env or environment.")
        return False

    print(f"[INFO] Connecting to: {db_url[:80]}...")

    try:
        from app.infrastructure.database.connection import init_engine, create_tables, check_health

        print("[INFO] Initializing engine...")
        init_engine()

        print("[INFO] Creating tables...")
        create_tables()

        print("[INFO] Health check...")
        if check_health():
            print("[SUCCESS] Connection OK. Tables created/verified.")
            return True
        else:
            print("[ERROR] Health check failed.")
            return False
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
