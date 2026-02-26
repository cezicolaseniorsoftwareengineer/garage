#!/usr/bin/env python3
"""
Clean database duplicates and reseed challenges
Evidence: Garage/scripts/clean_db.py
Trade-off: Fresh seed vs. preserving old data (chose fresh seed)
"""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.infrastructure.database.connection import init_engine, get_session_factory
from app.infrastructure.database.models import ChallengeModel
from app.infrastructure.database.seed import seed_challenges

def clean_and_reseed():
    """Drop all challenges and reseed from challenges.json"""

    print("🧹 Cleaning database...")
    init_engine()
    SessionLocal = get_session_factory()

    session = SessionLocal()
    try:
        # Delete all challenges
        deleted = session.query(ChallengeModel).delete()
        session.commit()
        print(f"  ✅ Deleted {deleted} challenge records")
    finally:
        session.close()

    print("\n🌱 Reseeding challenges...")
    seed_challenges(SessionLocal, "app/data/challenges.json")

    # Verify count
    session = SessionLocal()
    try:
        count = session.query(ChallengeModel).count()
        print(f"  ✅ Now have {count} challenges in database")
    finally:
        session.close()

    print("\n✨ Database cleaned and reseeded successfully!")

if __name__ == "__main__":
    clean_and_reseed()
