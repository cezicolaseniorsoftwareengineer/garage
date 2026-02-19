"""Seed challenge data from JSON into PostgreSQL."""
import json
import os

from app.infrastructure.database.models import ChallengeModel


def seed_challenges(session_factory, json_path: str) -> int:
    """Load challenges from a JSON file into the challenges table.

    Seeds when empty OR when DB count differs from JSON count (stale data
    detection). Truncates and re-seeds on mismatch so enum schema changes
    applied after initial deploy are always reflected.
    Returns the number of rows seeded (0 if already up-to-date).
    """
    if not os.path.exists(json_path):
        return 0

    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    json_count = len(raw)

    with session_factory() as session:
        existing = session.query(ChallengeModel).count()

        if existing == json_count:
            # Counts match: assume data is current, skip re-seed.
            return 0

        # Count mismatch (includes empty table): truncate and re-seed.
        if existing > 0:
            print(
                f"[GARAGE][SEED] DB has {existing} challenges, JSON has "
                f"{json_count}. Truncating and re-seeding."
            )
            session.query(ChallengeModel).delete()
            session.commit()

        count = 0
        for item in raw:
            model = ChallengeModel(
                id=item["id"],
                title=item["title"],
                description=item["description"],
                context_code=item.get("context_code"),
                category=item["category"],
                required_stage=item["required_stage"],
                region=item["region"],
                options=item["options"],  # stored as JSONB
                mentor=item.get("mentor"),
                points_on_correct=item.get("points_on_correct", 100),
            )
            session.add(model)
            count += 1

        session.commit()
        return count
