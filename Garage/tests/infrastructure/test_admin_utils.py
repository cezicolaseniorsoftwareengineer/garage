"""Unit tests for admin_utils (DRY admin email helpers)."""
import os
import pytest
from app.infrastructure.auth.admin_utils import configured_admin_emails, is_admin_email


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)


class TestConfiguredAdminEmails:
    def test_empty_env_returns_empty_set(self):
        assert configured_admin_emails() == set()

    def test_single_admin_email(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
        emails = configured_admin_emails()
        assert "boss@example.com" in emails

    def test_email_normalized_lowercase(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "BOSS@EXAMPLE.COM")
        emails = configured_admin_emails()
        assert "boss@example.com" in emails

    def test_multiple_emails_from_admin_emails(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "a@x.com, B@X.COM, c@x.com")
        emails = configured_admin_emails()
        assert "a@x.com" in emails
        assert "b@x.com" in emails
        assert "c@x.com" in emails

    def test_combined_primary_and_aliases(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "main@x.com")
        monkeypatch.setenv("ADMIN_EMAILS", "alias1@x.com,alias2@x.com")
        emails = configured_admin_emails()
        assert len(emails) == 3

    def test_empty_entries_ignored(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", ",, ,")
        emails = configured_admin_emails()
        assert emails == set()


class TestIsAdminEmail:
    def test_none_returns_false(self):
        assert is_admin_email(None) is False

    def test_empty_string_returns_false(self):
        assert is_admin_email("") is False

    def test_matching_email_returns_true(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@garage.com")
        assert is_admin_email("admin@garage.com") is True

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@garage.com")
        assert is_admin_email("ADMIN@GARAGE.COM") is True

    def test_non_admin_email_returns_false(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@garage.com")
        assert is_admin_email("hacker@evil.com") is False

    def test_not_in_aliases_returns_false(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "a@x.com,b@x.com")
        assert is_admin_email("c@x.com") is False
