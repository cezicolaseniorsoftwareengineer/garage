"""Loads challenges from JSON into domain entities."""
import json
import os
from typing import List

from app.domain.challenge import Challenge, ChallengeOption
from app.domain.enums import ChallengeCategory, CareerStage, MapRegion


class ChallengeRepository:
    """JSON-backed challenge storage."""

    def __init__(self, data_path: str):
        self._data_path = data_path
        self._challenges: List[Challenge] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._data_path):
            self._challenges = []
            return

        with open(self._data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self._challenges = []
        for item in raw:
            options = [
                ChallengeOption(
                    text=opt["text"],
                    is_correct=opt["is_correct"],
                    explanation=opt["explanation"],
                )
                for opt in item["options"]
            ]
            challenge = Challenge(
                challenge_id=item["id"],
                title=item["title"],
                description=item["description"],
                context_code=item.get("context_code"),
                category=ChallengeCategory(item["category"]),
                required_stage=CareerStage(item["required_stage"]),
                region=MapRegion(item["region"]),
                options=options,
                mentor_name=item.get("mentor"),
                points_on_correct=item.get("points_on_correct", 100),
            )
            self._challenges.append(challenge)

    def get_all(self) -> List[Challenge]:
        return list(self._challenges)

    def get_by_id(self, challenge_id: str) -> Challenge | None:
        for c in self._challenges:
            if c.id == challenge_id:
                return c
        return None

    def get_by_stage(self, stage: CareerStage) -> List[Challenge]:
        return [c for c in self._challenges if c.required_stage == stage]

    def get_by_region(self, region: MapRegion) -> List[Challenge]:
        return [c for c in self._challenges if c.region == region]
