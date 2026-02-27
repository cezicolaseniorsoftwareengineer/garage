"""Challenge entity -- questions, options, correct answers."""
from uuid import UUID, uuid4
from typing import List

from app.domain.enums import CareerStage, ChallengeCategory, MapRegion


class ChallengeOption:
    """A single answer option for a challenge."""

    def __init__(self, text: str, is_correct: bool, explanation: str):
        if not text:
            raise ValueError("Option text cannot be empty")
        self._text = text
        self._is_correct = is_correct
        self._explanation = explanation

    @property
    def text(self) -> str:
        return self._text

    @property
    def is_correct(self) -> bool:
        return self._is_correct

    @property
    def explanation(self) -> str:
        return self._explanation

    def to_dict(self) -> dict:
        return {
            "text": self._text,
            "explanation": self._explanation,
        }

    def to_dict_with_answer(self) -> dict:
        return {
            "text": self._text,
            "is_correct": self._is_correct,
            "explanation": self._explanation,
        }


class Challenge:
    """
    A technical challenge presented to the player.
    Immutable after creation.
    """

    def __init__(
        self,
        challenge_id: str,
        title: str,
        description: str,
        context_code: str | None,
        category: ChallengeCategory,
        required_stage: CareerStage,
        region: MapRegion,
        options: List[ChallengeOption],
        mentor_name: str | None = None,
        points_on_correct: int = 100,
        points_on_wrong: int = 0,
    ):
        if not options or len(options) < 2:
            raise ValueError("A challenge must have at least 2 options")
        correct_count = sum(1 for o in options if o.is_correct)
        if correct_count != 1:
            raise ValueError("Exactly one option must be correct")

        self._id = challenge_id
        self._title = title
        self._description = description
        self._context_code = context_code
        self._category = category
        self._required_stage = required_stage
        self._region = region
        self._options = options
        self._mentor_name = mentor_name
        self._points_on_correct = points_on_correct
        self._points_on_wrong = points_on_wrong

    @property
    def id(self) -> str:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def context_code(self) -> str | None:
        return self._context_code

    @property
    def category(self) -> ChallengeCategory:
        return self._category

    @property
    def required_stage(self) -> CareerStage:
        return self._required_stage

    @property
    def region(self) -> MapRegion:
        return self._region

    @property
    def options(self) -> List[ChallengeOption]:
        return list(self._options)

    @property
    def mentor_name(self) -> str | None:
        return self._mentor_name

    @property
    def points_on_correct(self) -> int:
        return self._points_on_correct

    @property
    def points_on_wrong(self) -> int:
        return self._points_on_wrong

    @property
    def correct_index(self) -> int:
        for i, opt in enumerate(self._options):
            if opt.is_correct:
                return i
        return -1  # pragma: no cover — Challenge invariant requires exactly one correct option

    def to_dict_for_player(self) -> dict:
        """Serialization for the frontend. Never exposes correct answer."""
        return {
            "id": self._id,
            "title": self._title,
            "description": self._description,
            "context_code": self._context_code,
            "category": self._category.value,
            "region": self._region.value,
            "mentor": self._mentor_name,
            "options": [o.to_dict() for o in self._options],
        }
