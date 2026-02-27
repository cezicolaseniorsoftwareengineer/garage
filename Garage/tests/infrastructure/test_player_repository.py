"""Unit tests for JSON-backed PlayerRepository."""
import os
import json
import pytest
import tempfile
import shutil
from app.infrastructure.repositories.player_repository import PlayerRepository
from tests.conftest import make_player


@pytest.fixture
def repo(tmp_path):
    path = str(tmp_path / "sessions.json")
    return PlayerRepository(data_path=path)


class TestPlayerRepositorySave:
    def test_save_and_get(self, repo):
        p = make_player(name="Repo Test")
        repo.save(p)
        loaded = repo.get(str(p.id))
        assert loaded is not None
        assert loaded.name == "Repo Test"

    def test_save_persists_to_file(self, repo):
        p = make_player()
        repo.save(p)
        assert os.path.exists(repo._data_path)

    def test_save_is_atomic(self, repo):
        """The tmp+replace strategy means no half-written files."""
        p = make_player()
        repo.save(p)
        # File must be valid JSON
        with open(repo._data_path) as f:
            data = json.load(f)
        assert str(p.id) in data


class TestPlayerRepositoryGet:
    def test_get_missing_returns_none(self, repo):
        assert repo.get("nonexistent-id") is None

    def test_get_from_cache(self, repo):
        p = make_player()
        repo.save(p)
        # Get twice — second from cache
        p1 = repo.get(str(p.id))
        p2 = repo.get(str(p.id))
        assert p1 is p2  # same object from cache

    def test_get_reloads_from_disk_after_cache_clear(self, repo):
        p = make_player(name="Persistent")
        repo.save(p)
        repo._sessions.clear()  # clear in-memory cache
        loaded = repo.get(str(p.id))
        assert loaded is not None
        assert loaded.name == "Persistent"


class TestPlayerRepositoryFindByUserId:
    def test_find_by_user_id(self, repo):
        p = make_player(user_id="owner-uid-1")
        repo.save(p)
        results = repo.find_by_user_id("owner-uid-1")
        assert any(r["id"] == str(p.id) for r in results)

    def test_find_by_user_id_different_owner(self, repo):
        p = make_player(user_id="owner-A")
        repo.save(p)
        results = repo.find_by_user_id("owner-B")
        assert results == []


class TestPlayerRepositoryGetAll:
    def test_get_all_returns_list(self, repo):
        repo.save(make_player(name="P1"))
        repo.save(make_player(name="P2"))
        all_players = repo.get_all()
        assert len(all_players) >= 2
