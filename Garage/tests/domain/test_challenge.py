"""Unit tests for Challenge and ChallengeOption entities."""
import pytest
from app.domain.challenge import Challenge, ChallengeOption
from app.domain.enums import CareerStage, ChallengeCategory, MapRegion


def _opts(n=4, correct_index=0):
    return [
        ChallengeOption(f"Option {i}", i == correct_index, f"Expl {i}")
        for i in range(n)
    ]


class TestChallengeOption:
    def test_valid_option(self):
        o = ChallengeOption("Yes", True, "Because yes")
        assert o.text == "Yes"
        assert o.is_correct is True
        assert o.explanation == "Because yes"

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="empty"):
            ChallengeOption("", False, "explanation")

    def test_to_dict_hides_is_correct(self):
        o = ChallengeOption("Answer", True, "reason")
        d = o.to_dict()
        assert "is_correct" not in d
        assert d["text"] == "Answer"

    def test_to_dict_with_answer_exposes_is_correct(self):
        o = ChallengeOption("Right", True, "r")
        d = o.to_dict_with_answer()
        assert d["is_correct"] is True


class TestChallengeCreation:
    def test_valid_challenge(self):
        c = Challenge(
            challenge_id="intern_01",
            title="T",
            description="D",
            context_code=None,
            category=ChallengeCategory.LOGIC,
            required_stage=CareerStage.INTERN,
            region=MapRegion.XEROX_PARC,
            options=_opts(4, 0),
        )
        assert c.id == "intern_01"
        assert c.correct_index == 0

    def test_correct_index_last_option(self):
        c = Challenge("x", "T", "D", None, ChallengeCategory.LOGIC,
                      CareerStage.JUNIOR, MapRegion.MICROSOFT, _opts(4, 3))
        assert c.correct_index == 3

    def test_less_than_two_options_raises(self):
        with pytest.raises(ValueError, match="2 options"):
            Challenge("x", "T", "D", None, ChallengeCategory.LOGIC,
                      CareerStage.INTERN, MapRegion.XEROX_PARC,
                      [ChallengeOption("A", True, "a")])

    def test_zero_correct_raises(self):
        opts = [ChallengeOption(f"O{i}", False, "e") for i in range(3)]
        with pytest.raises(ValueError, match="Exactly one"):
            Challenge("x", "T", "D", None, ChallengeCategory.LOGIC,
                      CareerStage.INTERN, MapRegion.XEROX_PARC, opts)

    def test_two_correct_raises(self):
        opts = [ChallengeOption(f"O{i}", True, "e") for i in range(2)]
        with pytest.raises(ValueError, match="Exactly one"):
            Challenge("x", "T", "D", None, ChallengeCategory.LOGIC,
                      CareerStage.INTERN, MapRegion.XEROX_PARC, opts)

    def test_options_are_copies(self):
        ch = Challenge("x", "T", "D", None, ChallengeCategory.LOGIC,
                       CareerStage.INTERN, MapRegion.XEROX_PARC, _opts())
        assert ch.options is not ch.options  # new list each call

    def test_to_dict_for_player_no_correct_answer(self):
        ch = Challenge("x", "T", "D", "code", ChallengeCategory.ARCHITECTURE,
                       CareerStage.MID, MapRegion.GOOGLE, _opts(4, 2))
        d = ch.to_dict_for_player()
        assert "id" in d
        for opt in d["options"]:
            assert "is_correct" not in opt, "Correct answer must NOT be in player dict"
