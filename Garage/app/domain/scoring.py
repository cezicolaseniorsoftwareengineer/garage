"""Scoring rules and map configuration."""


class ScoringRules:
    """Point calculation constants and logic."""

    BASE_CORRECT = 100
    BASE_CORRECT_AFTER_ERROR = 50
    BONUS_JUSTIFICATION = 25
    PENALTY_WRONG_ARCHITECTURE = -30
    ZERO_SHALLOW_THINKING = 0

    @staticmethod
    def calculate_points(
        is_correct: bool,
        previous_errors_on_challenge: int,
        category: str,
    ) -> int:
        if not is_correct:
            if category == "architecture":
                return ScoringRules.PENALTY_WRONG_ARCHITECTURE
            return ScoringRules.ZERO_SHALLOW_THINKING

        if previous_errors_on_challenge == 0:
            return ScoringRules.BASE_CORRECT
        return ScoringRules.BASE_CORRECT_AFTER_ERROR


class MapConfig:
    """
    Silicon Valley map regions and their associated career stages.
    """

    REGION_STAGE_MAP = {
        "Xerox PARC": "Intern",
        "Apple Garage": "Intern",
        "Microsoft": "Junior",
        "Google": "Mid",
        "Facebook": "Mid",
        "Amazon": "Senior",
        "PayPal": "Senior",
        "Tesla / SpaceX": "Staff",
        "Cloud Valley": "Principal",
    }

    BOSS_ARCHETYPES = {
        "The Visionary Founder": {
            "region": "Apple Garage",
            "stage": "Intern",
            "description": "Product thinking and simplicity.",
        },
        "The Platform Builder": {
            "region": "Microsoft",
            "stage": "Junior",
            "description": "Operating systems and scale.",
        },
        "The Search Architects": {
            "region": "Google",
            "stage": "Mid",
            "description": "Algorithms, data, distributed systems.",
        },
        "The Social Networker": {
            "region": "Facebook",
            "stage": "Mid",
            "description": "Social scale and consistency.",
        },
        "The Cloud Strategist": {
            "region": "Amazon",
            "stage": "Senior",
            "description": "E-commerce to Cloud infrastructure.",
        },
        "The First Principles Engineer": {
            "region": "Tesla / SpaceX",
            "stage": "Staff",
            "description": "Extreme engineering under constraints.",
        },
    }

    MENTOR_ARCHETYPES = {
        "The Craftsman": {
            "teaching": "Clean Code",
            "stage": "Intern",
        },
        "The Refactorer": {
            "teaching": "Safe Evolution",
            "stage": "Junior",
        },
        "The Simplifier": {
            "teaching": "TDD",
            "stage": "Mid",
        },
        "The Pragmatist": {
            "teaching": "Performance",
            "stage": "Senior",
        },
        "The Logician": {
            "teaching": "Formal Thinking",
            "stage": "Staff",
        },
    }
