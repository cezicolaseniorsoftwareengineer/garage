"""Use case: create a new game session."""
from uuid import UUID

from app.domain.character import Character
from app.domain.player import Player
from app.domain.enums import Gender, Ethnicity, BackendLanguage


def start_game(
    player_name: str,
    gender: str,
    ethnicity: str,
    avatar_index: int,
    language: str,
    user_id: str | None = None,
) -> Player:
    """
    Creates a new game session with validated inputs.
    Returns a fully initialized Player aggregate.
    """
    character = Character(
        gender=Gender(gender),
        ethnicity=Ethnicity(ethnicity),
        avatar_index=avatar_index,
    )

    player = Player(
        name=player_name,
        character=character,
        language=BackendLanguage(language),
        user_id=user_id,
    )

    return player
