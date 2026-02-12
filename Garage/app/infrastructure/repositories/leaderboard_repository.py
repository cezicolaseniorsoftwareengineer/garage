"""Leaderboard persistence (JSON file)."""
import json
import os
from datetime import datetime, timezone
from typing import List


class LeaderboardRepository:
    """File-based leaderboard persistence."""

    def __init__(self, data_path: str = "data/leaderboard.json"):
        self._data_path = data_path

    def submit(self, player_name: str, score: int, stage: str, language: str) -> dict:
        entries = self._load()
        entry = {
            "player_name": player_name,
            "score": score,
            "stage": stage,
            "language": language,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        entries.append(entry)
        entries.sort(key=lambda x: x["score"], reverse=True)
        self._save(entries)
        rank = next(
            (i + 1 for i, e in enumerate(entries) if e["timestamp"] == entry["timestamp"]),
            len(entries),
        )
        return {"rank": rank, "total_entries": len(entries)}

    def get_top(self, limit: int = 10) -> List[dict]:
        entries = self._load()
        entries.sort(key=lambda x: x["score"], reverse=True)
        return entries[:limit]

    def _load(self) -> List[dict]:
        if not os.path.exists(self._data_path):
            return []
        try:
            with open(self._data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save(self, entries: List[dict]) -> None:
        os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
        with open(self._data_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
