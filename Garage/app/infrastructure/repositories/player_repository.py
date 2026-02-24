"""Player session persistence (JSON file + in-memory cache)."""
import json
import os
from uuid import UUID
from typing import Dict

from app.domain.player import Player, Attempt
from app.domain.character import Character
from app.domain.enums import (
    Gender,
    Ethnicity,
    BackendLanguage,
    CareerStage,
    GameEnding,
)


class PlayerRepository:
    """JSON-backed player session storage."""

    def __init__(self, data_path: str = "data/sessions.json"):
        self._data_path = data_path
        self._sessions: Dict[str, Player] = {}

    def save(self, player: Player) -> None:
        """Persist player to file."""
        self._sessions[str(player.id)] = player
        self._persist()

    def get(self, player_id: str) -> Player | None:
        """Retrieve player from cache or file."""
        if player_id in self._sessions:
            return self._sessions[player_id]
        self._load()
        return self._sessions.get(player_id)

    def find_by_user_id(self, user_id: str) -> list:
        """Return all sessions belonging to a user."""
        self._load()
        results = []
        for player in self._sessions.values():
            if player.user_id == user_id:
                d = player.to_dict()
                d["attempts"] = [a.to_dict() for a in player.attempts]
                results.append(d)
        return results

    def get_all(self) -> list:
        """Return all sessions as Player objects."""
        self._load()
        return list(self._sessions.values())

    def get_all_dict(self) -> list:
        """Return all sessions as dicts (with attempts)."""
        self._load()
        results = []
        for player in self._sessions.values():
            d = player.to_dict()
            d["attempts"] = [a.to_dict() for a in player.attempts]
            results.append(d)
        return results

    def _persist(self) -> None:
        """Write all sessions to JSON file."""
        os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
        data = {}
        for pid, player in self._sessions.items():
            data[pid] = {
                **player.to_dict(),
                "attempts": [a.to_dict() for a in player.attempts],
            }
        # Write atomically: write to tempfile then replace
        tmp_path = f"{self._data_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Atomic replace
        try:
            os.replace(tmp_path, self._data_path)
        except Exception:
            # Best-effort fallback
            with open(self._data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> None:
        """Load sessions from JSON file."""
        if not os.path.exists(self._data_path):
            return
        try:
            with open(self._data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        for pid, pdata in data.items():
            char_data = pdata["character"]
            character = Character(
                gender=Gender(char_data["gender"]),
                ethnicity=Ethnicity(char_data["ethnicity"]),
                avatar_index=char_data["avatar_index"],
                character_id=UUID(char_data["id"]),
            )
            attempts = [
                Attempt(
                    challenge_id=a["challenge_id"],
                    selected_index=a["selected_index"],
                    is_correct=a["is_correct"],
                    points_awarded=a["points_awarded"],
                    timestamp=a["timestamp"],
                )
                for a in pdata.get("attempts", [])
            ]
            player = Player(
                name=pdata["name"],
                character=character,
                language=BackendLanguage(pdata["language"]),
                player_id=UUID(pid),
                stage=CareerStage(pdata["stage"]),
                score=pdata["score"],
                current_errors=pdata["current_errors"],
                completed_challenges=pdata["completed_challenges"],
                attempts=attempts,
                game_over_count=pdata["game_over_count"],
                status=GameEnding(pdata["status"]),
                created_at=pdata.get("created_at"),
            )
            self._sessions[pid] = player
