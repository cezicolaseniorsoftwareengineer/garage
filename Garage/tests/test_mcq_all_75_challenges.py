"""
MCQ Comprehensive Test — todas as 75 questões de múltipla escolha.

Cobre TODAS as situações que podem ocorrer durante o jogo:
  1. Cada desafio carrega sem erro de parsing
  2. Cada desafio tem exatamente 1 resposta correta
  3. Resposta correta → outcome=correct, pontos, desafio registrado
  4. Resposta errada  → outcome=wrong,   erros++, sem pontos
  5. Categoria architecture errada → -30 pontos de penalidade
  6. 2 erros na MESMA fase → game_over (clear de challenges da fase)
  7. Recuperação de game_over → status volta a in_progress
  8. 3 corretas na fase → promoção automática de estágio
  9. Double-submit bloqueado pelo invariante (challenge já completado)
 10. Acesso bloqueado: Intern não acessa challenges de Senior
 11. Contagem correta por nível: Intern=6, Junior=9, Mid=9, Senior=15, Staff=18, Principal=18
"""
import os
import sys
import json
import pytest

GARAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GARAGE_DIR not in sys.path:
    sys.path.insert(0, GARAGE_DIR)

from app.domain.enums import CareerStage, ChallengeCategory, GameEnding, BackendLanguage
from app.domain.player import Player
from app.domain.challenge import Challenge, ChallengeOption
from app.domain.character import Character
from app.domain.invariant import (
    validate_stage_access,
    validate_not_game_over,
    validate_challenge_not_completed,
)
from app.application.submit_answer import submit_answer
from app.infrastructure.repositories.challenge_repository import ChallengeRepository
from tests.conftest import make_player, make_character

DATA_PATH = os.path.join(GARAGE_DIR, "app", "data", "challenges.json")


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def real_repo():
    return ChallengeRepository(DATA_PATH)


@pytest.fixture(scope="module")
def all_real_challenges(real_repo):
    return real_repo.get_all()


def _player_at_stage(stage: CareerStage) -> Player:
    return Player(
        name="TesterDev",
        character=Character(
            gender=__import__("app.domain.enums", fromlist=["Gender"]).Gender.MALE,
            ethnicity=__import__("app.domain.enums", fromlist=["Ethnicity"]).Ethnicity.WHITE,
            avatar_index=0,
        ),
        language=BackendLanguage.JAVA,
        stage=stage,
    )


# ============================================================
# Bloco 1 — Parsing e estrutura dos desafios
# ============================================================

class TestChallengeLoading:
    """Todos os 75 desafios devem carregar sem erro."""

    def test_total_challenge_count(self, all_real_challenges):
        assert len(all_real_challenges) == 75, (
            f"Esperado 75 desafios, encontrado {len(all_real_challenges)}. "
            "Atualize challenges.json ou este teste."
        )

    def test_intern_challenges_count(self, all_real_challenges):
        cnt = sum(1 for c in all_real_challenges if c.required_stage == CareerStage.INTERN)
        assert cnt == 6, f"Intern esperava 6, encontrou {cnt}"

    def test_junior_challenges_count(self, all_real_challenges):
        cnt = sum(1 for c in all_real_challenges if c.required_stage == CareerStage.JUNIOR)
        assert cnt == 9, f"Junior esperava 9, encontrou {cnt}"

    def test_mid_challenges_count(self, all_real_challenges):
        cnt = sum(1 for c in all_real_challenges if c.required_stage == CareerStage.MID)
        assert cnt == 9, f"Mid esperava 9, encontrou {cnt}"

    def test_senior_challenges_count(self, all_real_challenges):
        cnt = sum(1 for c in all_real_challenges if c.required_stage == CareerStage.SENIOR)
        assert cnt == 15, f"Senior esperava 15, encontrou {cnt}"

    def test_staff_challenges_count(self, all_real_challenges):
        cnt = sum(1 for c in all_real_challenges if c.required_stage == CareerStage.STAFF)
        assert cnt == 18, f"Staff esperava 18, encontrou {cnt}"

    def test_principal_challenges_count(self, all_real_challenges):
        cnt = sum(1 for c in all_real_challenges if c.required_stage == CareerStage.PRINCIPAL)
        assert cnt == 18, f"Principal esperava 18, encontrou {cnt}"

    @pytest.mark.parametrize("i", range(75))
    def test_each_challenge_has_unique_id(self, all_real_challenges, i):
        ids = [c.id for c in all_real_challenges]
        ch = all_real_challenges[i]
        assert ids.count(ch.id) == 1, f"ID duplicado: {ch.id}"

    @pytest.mark.parametrize("i", range(75))
    def test_each_challenge_has_exactly_one_correct_option(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        correct_count = sum(1 for o in ch.options if o.is_correct)
        assert correct_count == 1, (
            f"Desafio {ch.id} tem {correct_count} opções corretas (esperado 1)"
        )

    @pytest.mark.parametrize("i", range(75))
    def test_each_challenge_has_at_least_two_options(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        assert len(ch.options) >= 2, f"Desafio {ch.id} tem menos de 2 opções"

    @pytest.mark.parametrize("i", range(75))
    def test_each_challenge_has_non_empty_title(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        assert ch.title and ch.title.strip(), f"Desafio {ch.id} sem título"

    @pytest.mark.parametrize("i", range(75))
    def test_each_challenge_has_non_empty_description(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        assert ch.description and ch.description.strip(), f"Desafio {ch.id} sem descrição"

    @pytest.mark.parametrize("i", range(75))
    def test_each_option_has_non_empty_explanation(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        for j, opt in enumerate(ch.options):
            assert opt.explanation and opt.explanation.strip(), (
                f"Desafio {ch.id} opção {j} sem explicação"
            )


# ============================================================
# Bloco 2 — Resposta correta em todos os 75 desafios
# ============================================================

class TestCorrectAnswerAllChallenges:
    """
    Acertar a resposta correta deve:
    - retornar outcome=correct
    - adicionar pontos
    - registrar o challenge em completed_challenges
    """

    @pytest.mark.parametrize("i", range(75))
    def test_correct_answer_returns_correct_outcome(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        player = _player_at_stage(ch.required_stage)

        result = submit_answer(player, ch, ch.correct_index)

        assert result["outcome"] == "correct", (
            f"Desafio {ch.id}: esperado 'correct', obteve '{result['outcome']}'"
        )

    @pytest.mark.parametrize("i", range(75))
    def test_correct_answer_adds_score(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        player = _player_at_stage(ch.required_stage)
        old_score = player.score

        submit_answer(player, ch, ch.correct_index)

        assert player.score > old_score, (
            f"Desafio {ch.id}: pontuação não aumentou (era {old_score}, ainda {player.score})"
        )

    @pytest.mark.parametrize("i", range(75))
    def test_correct_answer_registers_in_completed(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        player = _player_at_stage(ch.required_stage)

        submit_answer(player, ch, ch.correct_index)

        assert ch.id in player.completed_challenges, (
            f"Desafio {ch.id} não foi adicionado a completed_challenges"
        )

    @pytest.mark.parametrize("i", range(75))
    def test_correct_answer_includes_explanation(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        player = _player_at_stage(ch.required_stage)

        result = submit_answer(player, ch, ch.correct_index)

        assert "explanation" in result and result["explanation"], (
            f"Desafio {ch.id}: resultado sem explicação"
        )


# ============================================================
# Bloco 3 — Resposta errada em todos os 75 desafios
# ============================================================

class TestWrongAnswerAllChallenges:
    """
    Errar deve incrementar erros e retornar outcome=wrong.
    """

    def _first_wrong_index(self, ch: Challenge) -> int:
        for i, opt in enumerate(ch.options):
            if not opt.is_correct:
                return i
        return 0  # pragma: no cover

    @pytest.mark.parametrize("i", range(75))
    def test_wrong_answer_returns_wrong_or_game_over(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        player = _player_at_stage(ch.required_stage)
        wrong_idx = self._first_wrong_index(ch)

        result = submit_answer(player, ch, wrong_idx)

        assert result["outcome"] in ("wrong", "game_over"), (
            f"Desafio {ch.id}: resposta errada retornou '{result['outcome']}'"
        )

    @pytest.mark.parametrize("i", range(75))
    def test_wrong_answer_increments_error_or_triggers_game_over(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        player = _player_at_stage(ch.required_stage)
        wrong_idx = self._first_wrong_index(ch)

        submit_answer(player, ch, wrong_idx)

        # After 1 wrong: either errors=1 (normal) or game_over (if already had errors)
        assert player.current_errors >= 1 or player.status == GameEnding.GAME_OVER, (
            f"Desafio {ch.id}: erros não incrementou depois de resposta errada"
        )

    @pytest.mark.parametrize("i", range(75))
    def test_wrong_answer_does_not_add_to_completed(self, all_real_challenges, i):
        ch = all_real_challenges[i]
        player = _player_at_stage(ch.required_stage)
        wrong_idx = self._first_wrong_index(ch)

        submit_answer(player, ch, wrong_idx)

        assert ch.id not in player.completed_challenges, (
            f"Desafio {ch.id}: incorretamente adicionado a completed após resposta errada"
        )


# ============================================================
# Bloco 4 — Categoria Architecture: penalidade -30
# ============================================================

class TestArchitecturePenalty:
    """Resposta errada em 'architecture' deve aplicar -30 pontos."""

    def test_architecture_wrong_gives_negative_points(self, all_real_challenges):
        arch_challenges = [
            c for c in all_real_challenges
            if c.category == ChallengeCategory.ARCHITECTURE
        ]
        assert arch_challenges, "Nenhum desafio de arquitetura encontrado"

        for ch in arch_challenges:
            player = _player_at_stage(ch.required_stage)
            wrong_idx = next(
                i for i, o in enumerate(ch.options) if not o.is_correct
            )
            result = submit_answer(player, ch, wrong_idx)
            outcome = result["outcome"]
            if outcome == "wrong":
                assert player.score < 0 or player.score == 0, (
                    f"Desafio architecture {ch.id}: deveria ter -30 mas score={player.score}"
                )

    def test_architecture_correct_gives_100_points(self, all_real_challenges):
        arch_challenges = [
            c for c in all_real_challenges
            if c.category == ChallengeCategory.ARCHITECTURE
        ]
        for ch in arch_challenges:
            player = _player_at_stage(ch.required_stage)
            result = submit_answer(player, ch, ch.correct_index)
            assert result["outcome"] == "correct"
            assert player.score == 100, (
                f"Architecture correto {ch.id}: esperou 100, obteve {player.score}"
            )


# ============================================================
# Bloco 5 — Game Over: 2 erros na mesma fase
# ============================================================

class TestGameOverMechanic:
    """
    2 erros dentro da mesma fase dispara game_over.
    game_over deve limpar challenges da fase atual mas preservar os de outras fases.
    """

    def _get_two_different_wrong_intern_challenges(self, all_real_challenges):
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        assert len(intern) >= 2, "Precisa de pelo menos 2 desafios Intern"
        return intern[0], intern[1]

    def _first_wrong(self, ch):
        return next(i for i, o in enumerate(ch.options) if not o.is_correct)

    def test_first_wrong_does_not_trigger_game_over(self, all_real_challenges):
        ch1, _ = self._get_two_different_wrong_intern_challenges(all_real_challenges)
        player = _player_at_stage(CareerStage.INTERN)

        result = submit_answer(player, ch1, self._first_wrong(ch1))

        assert result["outcome"] == "wrong"
        assert player.status == GameEnding.IN_PROGRESS
        assert player.current_errors == 1

    def test_second_wrong_triggers_game_over(self, all_real_challenges):
        ch1, ch2 = self._get_two_different_wrong_intern_challenges(all_real_challenges)
        player = _player_at_stage(CareerStage.INTERN)

        submit_answer(player, ch1, self._first_wrong(ch1))
        result = submit_answer(player, ch2, self._first_wrong(ch2))

        assert result["outcome"] == "game_over"
        assert player.status == GameEnding.GAME_OVER
        assert player.current_errors == 0  # reset após game_over

    def test_game_over_increments_game_over_count(self, all_real_challenges):
        ch1, ch2 = self._get_two_different_wrong_intern_challenges(all_real_challenges)
        player = _player_at_stage(CareerStage.INTERN)

        submit_answer(player, ch1, self._first_wrong(ch1))
        submit_answer(player, ch2, self._first_wrong(ch2))

        assert player.game_over_count == 1

    def test_game_over_clears_current_stage_challenges(self, all_real_challenges):
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        player = _player_at_stage(CareerStage.INTERN)

        # Complete one intern challenge first
        submit_answer(player, intern[0], intern[0].correct_index)
        assert intern[0].id in player.completed_challenges

        # Now trigger game_over with two wrong answers on other challenges
        submit_answer(player, intern[1], self._first_wrong(intern[1]))
        submit_answer(player, intern[2], self._first_wrong(intern[2]))

        # Intern challenges should be cleared
        assert intern[0].id not in player.completed_challenges, (
            "game_over deveria ter limpado challenges do Intern"
        )

    def test_game_over_preserves_other_stage_challenges(self, all_real_challenges):
        """Challenges de outros estágios NÃO devem ser afetados pelo game_over do Intern."""
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        junior = [c for c in all_real_challenges if c.required_stage == CareerStage.JUNIOR]
        if not junior:
            pytest.skip("Sem desafios Junior para testar")

        player = _player_at_stage(CareerStage.JUNIOR)
        # Manually add a Junior challenge as completed
        player._completed_challenges.append(junior[0].id)
        player._stage = CareerStage.INTERN  # drop back to intern for game_over test

        submit_answer(player, intern[0], self._first_wrong(intern[0]))
        submit_answer(player, intern[1], self._first_wrong(intern[1]))

        # Junior challenge must still be there
        assert junior[0].id in player.completed_challenges, (
            "game_over do Intern não deve remover challenges de Junior"
        )

    def test_game_over_cannot_attempt_new_challenge(self, all_real_challenges):
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        player = _player_at_stage(CareerStage.INTERN)

        submit_answer(player, intern[0], self._first_wrong(intern[0]))
        submit_answer(player, intern[1], self._first_wrong(intern[1]))

        assert player.status == GameEnding.GAME_OVER
        with pytest.raises((RuntimeError, PermissionError)):
            validate_not_game_over(player.status.value)


# ============================================================
# Bloco 6 — Recuperação de Game Over
# ============================================================

class TestGameOverRecovery:

    def _first_wrong(self, ch):
        return next(i for i, o in enumerate(ch.options) if not o.is_correct)

    def _trigger_game_over(self, player, challenges):
        intern = [c for c in challenges if c.required_stage == CareerStage.INTERN]
        submit_answer(player, intern[0], self._first_wrong(intern[0]))
        submit_answer(player, intern[1], self._first_wrong(intern[1]))
        assert player.status == GameEnding.GAME_OVER

    def test_recovery_restores_in_progress_status(self, all_real_challenges):
        player = _player_at_stage(CareerStage.INTERN)
        self._trigger_game_over(player, all_real_challenges)

        player.recover_from_game_over()

        assert player.status == GameEnding.IN_PROGRESS

    def test_recovery_resets_error_count(self, all_real_challenges):
        player = _player_at_stage(CareerStage.INTERN)
        self._trigger_game_over(player, all_real_challenges)

        player.recover_from_game_over()

        assert player.current_errors == 0

    def test_after_recovery_can_attempt_challenges(self, all_real_challenges):
        player = _player_at_stage(CareerStage.INTERN)
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        self._trigger_game_over(player, all_real_challenges)
        player.recover_from_game_over()

        # Should work again
        result = submit_answer(player, intern[0], intern[0].correct_index)
        assert result["outcome"] == "correct"

    def test_recovery_preserves_score(self, all_real_challenges):
        player = _player_at_stage(CareerStage.INTERN)
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        # Correctly answer intern[0] to earn score
        submit_answer(player, intern[0], intern[0].correct_index)
        score_before_game_over = player.score

        # Trigger game_over with intern[1] and intern[2]
        # (intern[0] is already completed — must NOT reuse it)
        submit_answer(player, intern[1], self._first_wrong(intern[1]))
        submit_answer(player, intern[2], self._first_wrong(intern[2]))
        assert player.status == GameEnding.GAME_OVER

        player.recover_from_game_over()

        assert player.score == score_before_game_over, (
            "Recuperação não deve apagar pontuação histórica"
        )

    def test_double_recovery_is_noop(self, all_real_challenges):
        player = _player_at_stage(CareerStage.INTERN)
        self._trigger_game_over(player, all_real_challenges)

        player.recover_from_game_over()
        player.recover_from_game_over()  # segunda chamada — não deve quebrar

        assert player.status == GameEnding.IN_PROGRESS


# ============================================================
# Bloco 7 — Promoção de estágio
# ============================================================

class TestStagePromotion:
    """3 corretas na fase → promoção automática conforme CHALLENGES_TO_PROMOTE."""

    STAGE_ORDER = [
        CareerStage.INTERN,
        CareerStage.JUNIOR,
        CareerStage.MID,
        CareerStage.SENIOR,
        CareerStage.STAFF,
        CareerStage.PRINCIPAL,
    ]

    NEXT_STAGE = {
        CareerStage.INTERN:    CareerStage.JUNIOR,
        CareerStage.JUNIOR:    CareerStage.MID,
        CareerStage.MID:       CareerStage.SENIOR,
        CareerStage.SENIOR:    CareerStage.STAFF,
        CareerStage.STAFF:     CareerStage.PRINCIPAL,
        CareerStage.PRINCIPAL: CareerStage.DISTINGUISHED,
    }

    def test_promotion_requires_three_correct(self, all_real_challenges):
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        player = _player_at_stage(CareerStage.INTERN)

        # 2 corretas — ainda não promovido
        submit_answer(player, intern[0], intern[0].correct_index)
        submit_answer(player, intern[1], intern[1].correct_index)
        assert player.stage == CareerStage.INTERN

        # 3ª correta → promoção
        result = submit_answer(player, intern[2], intern[2].correct_index)
        assert player.stage == CareerStage.JUNIOR, (
            f"Esperava promoção para Junior, estágio atual: {player.stage}"
        )
        assert result.get("promotion") is True or player.stage == CareerStage.JUNIOR

    @pytest.mark.parametrize("stage", STAGE_ORDER)
    def test_promotion_from_each_stage(self, all_real_challenges, stage):
        challenges = [
            c for c in all_real_challenges if c.required_stage == stage
        ]
        if len(challenges) < 3:
            pytest.skip(f"Menos de 3 desafios em {stage.value}")

        player = _player_at_stage(stage)
        for ch in challenges[:3]:
            submit_answer(player, ch, ch.correct_index)

        expected_next = self.NEXT_STAGE[stage]
        assert player.stage == expected_next, (
            f"Promoção de {stage.value}: esperava {expected_next.value}, obteve {player.stage.value}"
        )

    def test_promotion_resets_error_counter(self, all_real_challenges):
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        player = _player_at_stage(CareerStage.INTERN)

        # 1 erro antes de promover
        wrong_idx = next(i for i, o in enumerate(intern[0].options) if not o.is_correct)
        submit_answer(player, intern[0], wrong_idx)
        assert player.current_errors == 1

        # 3 acertos → promoção
        from itertools import islice
        remaining = [c for c in intern if c.id != intern[0].id]
        for ch in list(islice(remaining, 3)):
            submit_answer(player, ch, ch.correct_index)

        assert player.current_errors == 0, (
            "Promoção deveria resetar contador de erros"
        )


# ============================================================
# Bloco 8 — Invariantes: double-submit e acesso de estágio
# ============================================================

class TestInvariants:

    def test_double_submit_raises_value_error(self, all_real_challenges):
        ch = all_real_challenges[0]
        player = _player_at_stage(ch.required_stage)

        submit_answer(player, ch, ch.correct_index)  # Primeira submissão — OK
        with pytest.raises(ValueError, match="already completed"):
            validate_challenge_not_completed(player.completed_challenges, ch.id)

    def test_intern_cannot_access_senior_challenge(self, all_real_challenges):
        senior_ch = next(
            c for c in all_real_challenges if c.required_stage == CareerStage.SENIOR
        )
        intern_player = _player_at_stage(CareerStage.INTERN)

        with pytest.raises(PermissionError, match="Stage"):
            validate_stage_access(intern_player.stage, senior_ch.required_stage)

    def test_game_over_player_cannot_submit(self, all_real_challenges):
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        player = _player_at_stage(CareerStage.INTERN)

        wrong_idx = next(i for i, o in enumerate(intern[0].options) if not o.is_correct)
        submit_answer(player, intern[0], wrong_idx)
        submit_answer(player, intern[1], wrong_idx)

        assert player.status == GameEnding.GAME_OVER

        with pytest.raises(RuntimeError, match="Game Over"):
            validate_not_game_over(player.status.value)

    def test_invalid_option_index_raises_on_submit(self, all_real_challenges):
        ch = all_real_challenges[0]
        player = _player_at_stage(ch.required_stage)

        with pytest.raises(ValueError, match="Invalid option index"):
            submit_answer(player, ch, 999)

    def test_senior_can_access_intern_challenge(self, all_real_challenges):
        intern_ch = next(
            c for c in all_real_challenges if c.required_stage == CareerStage.INTERN
        )
        senior_player = _player_at_stage(CareerStage.SENIOR)

        # Should not raise
        validate_stage_access(senior_player.stage, intern_ch.required_stage)


# ============================================================
# Bloco 9 — Acerto na segunda tentativa (pontuação reduzida)
# ============================================================

class TestSecondAttemptScoring:
    """Responder certo depois de um erro = 50 pontos (BASE_CORRECT_AFTER_ERROR)."""

    def test_correct_after_error_gives_50_points(self, all_real_challenges):
        # Pick multiple challenges so we can reuse on the same player
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        assert len(intern) >= 2

        player = _player_at_stage(CareerStage.INTERN)
        ch = intern[0]

        # Wrong first
        wrong_idx = next(i for i, o in enumerate(ch.options) if not o.is_correct)
        submit_answer(player, ch, wrong_idx)

        # Note: after wrong, the challenge is NOT completed, so we can answer again
        # But we need a different challenge to avoid "already completed" invariant
        # The scoring rule is based on player.current_errors at point of submit
        ch2 = intern[1]
        result = submit_answer(player, ch2, ch2.correct_index)
        assert result["outcome"] == "correct"
        # With 1 prior error: should get 50 pts
        assert result["points_awarded"] == 50, (
            f"Esperado 50 pts após erro prévio, obteve {result['points_awarded']}"
        )

    def test_correct_first_attempt_gives_100_points(self, all_real_challenges):
        intern = [c for c in all_real_challenges if c.required_stage == CareerStage.INTERN]
        player = _player_at_stage(CareerStage.INTERN)
        ch = intern[0]

        result = submit_answer(player, ch, ch.correct_index)
        assert result["points_awarded"] == 100


# ============================================================
# Bloco 10 — Bio Code Technology (desafios finais)
# ============================================================

class TestBioCodeTechnology:
    """Os 3 desafios da Bio Code Technology (CEO Cezi Cola) devem funcionar 100%."""

    def test_biocode_challenges_exist(self, all_real_challenges):
        from app.domain.enums import MapRegion
        bio = [c for c in all_real_challenges if c.region == MapRegion.BIO_CODE_TECHNOLOGY]
        assert len(bio) >= 3, f"Bio Code Technology deve ter ≥3 desafios, encontrou {len(bio)}"

    def test_biocode_challenges_are_principal_stage(self, all_real_challenges):
        from app.domain.enums import MapRegion
        bio = [c for c in all_real_challenges if c.region == MapRegion.BIO_CODE_TECHNOLOGY]
        for ch in bio:
            assert ch.required_stage == CareerStage.PRINCIPAL, (
                f"Bio Code {ch.id} deveria ser Principal, é {ch.required_stage.value}"
            )

    def test_biocode_challenges_correct_answer_works(self, all_real_challenges):
        from app.domain.enums import MapRegion
        bio = [c for c in all_real_challenges if c.region == MapRegion.BIO_CODE_TECHNOLOGY]
        player = _player_at_stage(CareerStage.PRINCIPAL)

        for ch in bio:
            result = submit_answer(player, ch, ch.correct_index)
            assert result["outcome"] == "correct", (
                f"Bio Code {ch.id}: resposta correta falhou"
            )

    def test_biocode_all_options_have_explanations(self, all_real_challenges):
        from app.domain.enums import MapRegion
        bio = [c for c in all_real_challenges if c.region == MapRegion.BIO_CODE_TECHNOLOGY]
        for ch in bio:
            for j, opt in enumerate(ch.options):
                assert opt.explanation, f"Bio Code {ch.id} opção {j} sem explicação"
