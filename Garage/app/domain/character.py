"""
GARAGE - Domain Layer: Character Entity.

A character is purely visual. No stats, no bonuses, no hidden advantages.
Skill belongs to the player, not the avatar.
"""
from uuid import UUID, uuid4

from app.domain.enums import Gender, Ethnicity


class Character:
    """Playable character (cosmetic only)."""

    def __init__(
        self,
        gender: Gender,
        ethnicity: Ethnicity,
        avatar_index: int,
        character_id: UUID | None = None,
    ):
        if avatar_index < 0 or avatar_index > 5:
            raise ValueError("avatar_index must be between 0 and 5")

        self._id = character_id or uuid4()
        self._gender = gender
        self._ethnicity = ethnicity
        self._avatar_index = avatar_index

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def gender(self) -> Gender:
        return self._gender

    @property
    def ethnicity(self) -> Ethnicity:
        return self._ethnicity

    @property
    def avatar_index(self) -> int:
        return self._avatar_index

    def to_dict(self) -> dict:
        return {
            "id": str(self._id),
            "gender": self._gender.value,
            "ethnicity": self._ethnicity.value,
            "avatar_index": self._avatar_index,
        }
