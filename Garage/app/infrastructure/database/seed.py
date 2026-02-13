"""Seed challenge data from JSON into PostgreSQL."""
import json
import os

from app.infrastructure.database.models import ChallengeModel


def seed_challenges(session_factory, json_path: str) -> int:
    """Load challenges from a JSON file into the challenges table.

    Only inserts if the table is empty (idempotent on subsequent deploys).
    Returns the number of rows seeded.
    """
    if not os.path.exists(json_path):
        return 0

    with session_factory() as session:
        existing = session.query(ChallengeModel).count()
        if existing > 0:
            return 0

        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

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
