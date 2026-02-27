"""Tests for LeaderboardRepository — JSON persistence."""
import json
import os
import tempfile
import pytest

from app.infrastructure.repositories.leaderboard_repository import LeaderboardRepository


@pytest.fixture
def repo_path(tmp_path):
    return str(tmp_path / "test_leaderboard.json")


@pytest.fixture
def repo(repo_path):
    return LeaderboardRepository(data_path=repo_path)


class TestLeaderboardSubmit:
    def test_submit_single_entry(self, repo):
        result = repo.submit("Alice", 500, "Senior", "Java")
        assert "rank" in result
        assert "total_entries" in result
        assert result["total_entries"] == 1

    def test_submit_entry_persisted(self, repo, repo_path):
        repo.submit("Bob", 300, "Junior", "Java")
        with open(repo_path, "r") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["player_name"] == "Bob"

    def test_submit_returns_correct_rank(self, repo):
        repo.submit("Charlie", 100, "Intern", "Java")
        res = repo.submit("Dan", 500, "Senior", "Java")
        # Dan has higher score → rank 1
        assert res["rank"] == 1

    def test_submit_multiple_entries_sorted(self, repo):
        repo.submit("Alice", 500, "Senior", "Java")
        repo.submit("Bob", 300, "Junior", "Java")
        repo.submit("Charlie", 700, "Staff", "Python")
        top = repo.get_top(3)
        assert top[0]["score"] == 700
        assert top[1]["score"] == 500

    def test_submit_total_entries_grows(self, repo):
        for i in range(5):
            repo.submit(f"Player{i}", i * 100, "Intern", "Java")
        result = repo.submit("Sixth", 1000, "Senior", "Java")
        assert result["total_entries"] == 6


class TestLeaderboardGetTop:
    def test_get_top_empty(self, repo):
        top = repo.get_top()
        assert top == []

    def test_get_top_default_limit(self, repo):
        for i in range(15):
            repo.submit(f"P{i}", i * 10, "Intern", "Java")
        top = repo.get_top()
        assert len(top) == 10  # default limit

    def test_get_top_custom_limit(self, repo):
        for i in range(10):
            repo.submit(f"P{i}", i * 10, "Intern", "Java")
        top = repo.get_top(3)
        assert len(top) == 3

    def test_get_top_first_is_highest_score(self, repo):
        repo.submit("A", 100, "Intern", "Java")
        repo.submit("B", 999, "Senior", "Java")
        top = repo.get_top()
        assert top[0]["player_name"] == "B"


class TestLeaderboardLoad:
    def test_load_nonexistent_file_returns_empty(self, tmp_path):
        """_load() on missing file returns []."""
        repo = LeaderboardRepository(data_path=str(tmp_path / "missing.json"))
        assert repo.get_top() == []

    def test_load_corrupted_file_returns_empty(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("{invalid json}")
        repo = LeaderboardRepository(data_path=path)
        assert repo.get_top() == []

    def test_load_existing_file(self, tmp_path):
        path = str(tmp_path / "existing.json")
        data = [{"player_name": "Eve", "score": 400, "stage": "Mid",
                 "language": "Java", "timestamp": "2024-01-01T00:00:00+00:00"}]
        with open(path, "w") as f:
            json.dump(data, f)
        repo = LeaderboardRepository(data_path=path)
        top = repo.get_top()
        assert len(top) == 1
        assert top[0]["player_name"] == "Eve"
