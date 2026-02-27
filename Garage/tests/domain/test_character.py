"""Unit tests for Character entity."""
import pytest
from uuid import UUID
from app.domain.character import Character
from app.domain.enums import Gender, Ethnicity


class TestCharacterCreation:
    def test_valid_male_white(self):
        c = Character(Gender.MALE, Ethnicity.WHITE, 0)
        assert c.gender == Gender.MALE
        assert c.ethnicity == Ethnicity.WHITE
        assert c.avatar_index == 0

    def test_valid_female_black(self):
        c = Character(Gender.FEMALE, Ethnicity.BLACK, 3)
        assert c.gender == Gender.FEMALE
        assert c.ethnicity == Ethnicity.BLACK
        assert c.avatar_index == 3

    def test_valid_max_avatar_index(self):
        c = Character(Gender.MALE, Ethnicity.ASIAN, 5)
        assert c.avatar_index == 5

    def test_invalid_avatar_index_negative(self):
        with pytest.raises(ValueError, match="avatar_index"):
            Character(Gender.MALE, Ethnicity.WHITE, -1)

    def test_invalid_avatar_index_too_large(self):
        with pytest.raises(ValueError, match="avatar_index"):
            Character(Gender.MALE, Ethnicity.WHITE, 6)

    def test_id_is_uuid(self):
        c = Character(Gender.MALE, Ethnicity.WHITE, 0)
        assert isinstance(c.id, UUID)

    def test_explicit_id_preserved(self):
        from uuid import uuid4
        uid = uuid4()
        c = Character(Gender.MALE, Ethnicity.WHITE, 0, character_id=uid)
        assert c.id == uid


class TestCharacterSerialization:
    def test_to_dict_keys(self):
        c = Character(Gender.FEMALE, Ethnicity.ASIAN, 2)
        d = c.to_dict()
        assert set(d.keys()) == {"id", "gender", "ethnicity", "avatar_index"}

    def test_to_dict_values(self):
        c = Character(Gender.MALE, Ethnicity.BLACK, 1)
        d = c.to_dict()
        assert d["gender"] == "male"
        assert d["ethnicity"] == "black"
        assert d["avatar_index"] == 1
