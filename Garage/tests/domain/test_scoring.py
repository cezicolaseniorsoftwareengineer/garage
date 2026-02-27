"""Unit tests for ScoringRules."""
import pytest
from app.domain.scoring import ScoringRules


class TestScoringRules:
    def test_correct_first_attempt_100(self):
        pts = ScoringRules.calculate_points(True, 0, "logic")
        assert pts == 100

    def test_correct_after_error_50(self):
        pts = ScoringRules.calculate_points(True, 1, "logic")
        assert pts == 50

    def test_correct_after_many_errors_50(self):
        pts = ScoringRules.calculate_points(True, 5, "domain_modeling")
        assert pts == 50

    def test_wrong_logic_zero(self):
        pts = ScoringRules.calculate_points(False, 0, "logic")
        assert pts == 0

    def test_wrong_architecture_negative(self):
        pts = ScoringRules.calculate_points(False, 0, "architecture")
        assert pts == -30

    def test_wrong_distributed_zero(self):
        pts = ScoringRules.calculate_points(False, 0, "distributed_systems")
        assert pts == 0

    def test_wrong_domain_modeling_zero(self):
        pts = ScoringRules.calculate_points(False, 0, "domain_modeling")
        assert pts == 0

    def test_constants_defined(self):
        assert ScoringRules.BASE_CORRECT == 100
        assert ScoringRules.BASE_CORRECT_AFTER_ERROR == 50
        assert ScoringRules.PENALTY_WRONG_ARCHITECTURE == -30
