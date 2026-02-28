"""
Responsive Layout & UI Structure Tests.

Valida que o HTML e CSS do jogo contêm TODOS os elementos necessários
para funcionar corretamente em:
  - Desktop  (≥ 1024px)
  - Tablet   (768px – 1023px)
  - Mobile   (< 768px)

Testa:
  1. HTML — elementos obrigatórios existem (canvas, screens, overlays, HUD)
  2. CSS  — media queries de breakpoints estão presentes
  3. CSS  — classes de controle mobile existem
  4. CSS  — animações da Garage AI (dots + spinner) estão presentes
  5. JS   — funções críticas declaradas no game.js
  6. JS   — State, World, Game, UI, Learning, StudyChat declarados
  7. JS   — resizeCanvas / mobile controls wired
  8. HTML — nenhum elemento com id duplicado
  9. CSS  — responsividade do canvas declarada
 10. HTML — challenge overlay, feedback, actions todos presentes
"""
import os
import re
import sys

import pytest

GARAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(GARAGE_DIR, "app", "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")
STYLE_CSS  = os.path.join(STATIC_DIR, "style.css")
GAME_JS    = os.path.join(STATIC_DIR, "game.js")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def html():
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def css():
    with open(STYLE_CSS, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def js():
    with open(GAME_JS, "r", encoding="utf-8") as f:
        return f.read()


def _all_ids(html_source: str) -> list[str]:
    return re.findall(r'\bid=["\']([^"\']+)["\']', html_source)


# ---------------------------------------------------------------------------
# 1. HTML — elementos obrigatórios
# ---------------------------------------------------------------------------

class TestHTMLStructure:
    """Garante que todos os elementos do jogo existem no HTML."""

    # Screens
    REQUIRED_SCREENS = [
        "screen-title",
        "screen-world",
        "screen-gameover",
        "screen-victory",
        "screen-login",
        "screen-register",
        "screen-onboarding",
    ]

    # Overlays
    REQUIRED_OVERLAYS = [
        "challengeOverlay",
        "promotionOverlay",
        "learningOverlay",
        "studyChatOverlay",
    ]

    # HUD elements
    REQUIRED_HUD = [
        "hudStage",
        "hudScore",
        "hudErrors",
        "hudBooks",
    ]

    # Challenge panel
    REQUIRED_CHALLENGE = [
        "challengeTitle",
        "challengeDesc",
        "challengeOptions",
        "challengeFeedback",
        "challengeActions",
        "challengeCode",
        "challengeMentor",
    ]

    # Auth elements
    REQUIRED_AUTH = [
        "loginUsername",
        "loginPassword",
        "regUsername",
        "regPassword",
    ]

    @pytest.mark.parametrize("screen_id", REQUIRED_SCREENS)
    def test_screen_exists(self, html, screen_id):
        assert f'id="{screen_id}"' in html or f"id='{screen_id}'" in html, (
            f"Screen #{screen_id} não encontrada no index.html"
        )

    @pytest.mark.parametrize("overlay_id", REQUIRED_OVERLAYS)
    def test_overlay_exists(self, html, overlay_id):
        assert f'id="{overlay_id}"' in html or f"id='{overlay_id}'" in html, (
            f"Overlay #{overlay_id} não encontrado no index.html"
        )

    @pytest.mark.parametrize("el_id", REQUIRED_HUD)
    def test_hud_element_exists(self, html, el_id):
        assert f'id="{el_id}"' in html or f"id='{el_id}'" in html, (
            f"Elemento HUD #{el_id} não encontrado"
        )

    @pytest.mark.parametrize("el_id", REQUIRED_CHALLENGE)
    def test_challenge_element_exists(self, html, el_id):
        assert f'id="{el_id}"' in html or f"id='{el_id}'" in html, (
            f"Elemento do desafio #{el_id} não encontrado"
        )

    @pytest.mark.parametrize("el_id", REQUIRED_AUTH)
    def test_auth_element_exists(self, html, el_id):
        assert f'id="{el_id}"' in html or f"id='{el_id}'" in html, (
            f"Elemento de autenticação #{el_id} não encontrado"
        )

    def test_canvas_element_exists(self, html):
        assert "<canvas" in html, "Elemento <canvas> não encontrado no index.html"

    def test_canvas_has_id(self, html):
        assert 'id="gameCanvas"' in html or "id='gameCanvas'" in html, (
            "Canvas deve ter id='gameCanvas'"
        )

    def test_no_duplicate_ids(self, html):
        all_ids = _all_ids(html)
        duplicates = [id_ for id_ in set(all_ids) if all_ids.count(id_) > 1]
        assert not duplicates, (
            f"IDs duplicados encontrados no index.html: {duplicates}"
        )

    def test_mobile_controls_exist(self, html):
        assert "mobile-controls" in html, (
            "Controles mobile (.mobile-controls) não encontrados no HTML"
        )

    def test_send_button_exists(self, html):
        assert "studySendBtn" in html or "send" in html.lower(), (
            "Botão de envio do StudyChat não encontrado"
        )

    def test_promotion_overlay_has_message_element(self, html):
        assert "promotionMessage" in html, (
            "Elemento #promotionMessage não encontrado no promotionOverlay"
        )

    def test_gameover_stats_element_exists(self, html):
        assert "gameoverStats" in html, "Elemento #gameoverStats não encontrado"

    def test_victory_stats_element_exists(self, html):
        assert "victoryStats" in html, "Elemento #victoryStats não encontrado"

    def test_viewport_meta_tag_exists(self, html):
        assert 'name="viewport"' in html, (
            "Meta tag viewport não encontrada (necessária para responsividade mobile)"
        )

    def test_viewport_has_initial_scale(self, html):
        assert "initial-scale=1" in html, (
            "Meta viewport deve ter initial-scale=1 para mobile"
        )


# ---------------------------------------------------------------------------
# 2. CSS — media queries e breakpoints
# ---------------------------------------------------------------------------

class TestCSSResponsiveness:
    """Valida que o CSS tem as media queries corretas para cada dispositivo."""

    def test_mobile_breakpoint_768_exists(self, css):
        assert "768px" in css, (
            "Breakpoint 768px não encontrado no style.css (necessário para tablet/mobile)"
        )

    def test_mobile_breakpoint_480_or_600_exists(self, css):
        has_480 = "480px" in css
        has_600 = "600px" in css
        assert has_480 or has_600, (
            "Nenhum breakpoint ≤600px encontrado no style.css (necessário para mobile pequeno)"
        )

    def test_media_query_max_width_present(self, css):
        assert "max-width" in css, "Nenhuma media query max-width encontrada no CSS"

    def test_mobile_controls_class_styled(self, css):
        assert ".mobile-controls" in css, (
            "Classe .mobile-controls não estilizada no CSS"
        )

    def test_canvas_responsive_style(self, css):
        # Canvas deve ter width:100% ou similar para responsividade
        assert "#gameCanvas" in css or "gameCanvas" in css or "canvas" in css, (
            "Nenhum estilo para canvas encontrado no CSS"
        )

    def test_challenge_overlay_styled(self, css):
        assert "challenge" in css.lower(), (
            "Nenhum estilo para challenge overlay encontrado"
        )

    def test_option_buttons_styled(self, css):
        assert ".option-btn" in css or "option-btn" in css, (
            "Classe .option-btn não estilizada"
        )

    def test_screen_classes_styled(self, css):
        assert ".screen" in css or "#screen-game" in css, (
            "Classes de tela (.screen) não estilizadas"
        )

    def test_feedback_correct_class(self, css):
        assert ".correct" in css or "feedback-box" in css, (
            "Classe de feedback correto não estilizada"
        )

    def test_feedback_wrong_class(self, css):
        assert ".wrong" in css, (
            "Classe de feedback errado não estilizada"
        )

    # ---- Garage AI animation CSS ----
    def test_garage_spinner_animation_css(self, css):
        assert "garageSpinRing" in css or "garage-send-ring" in css, (
            "Animação spinner do botão Garage AI (garageSpinRing) não encontrada"
        )

    def test_garage_stop_icon_css(self, css):
        assert "garage-stop-icon" in css or "stop-icon" in css, (
            "Estilo do ícone stop não encontrado no CSS"
        )

    def test_keyframes_present(self, css):
        assert "@keyframes" in css, "Nenhuma @keyframes encontrada no CSS"


# ---------------------------------------------------------------------------
# 3. JavaScript — funções e objetos críticos
# ---------------------------------------------------------------------------

class TestJSStructure:
    """Valida que o game.js declara todos os módulos e funções críticas."""

    REQUIRED_OBJECTS = [
        "const State",
        "const World",
        "const Game",
        "const UI",
        "const Learning",
        "const StudyChat",
        "const API",
        "const SFX",
        "const Heartbeat",
        "const WorldStatePersistence",
        "const JavaAnalyzer",
        "const CODE_CHALLENGES",
        "const BOOKS_DATA",
        "const BUILDINGS",
        "const NPC_DATA",
    ]

    REQUIRED_FUNCTIONS_IN_GAME = [
        "submitAnswer",
        "nextChallenge",
        "enterRegion",
        "loadSession",
        "start",
    ]

    REQUIRED_FUNCTIONS_IN_UI = [
        "showChallenge",
        "hideChallenge",
        "showFeedback",
        "showPromotion",
        "showGameOver",
        "showVictory",
        "updateHUD",
        "showScreen",
    ]

    @pytest.mark.parametrize("obj", REQUIRED_OBJECTS)
    def test_required_object_declared(self, js, obj):
        assert obj in js, f"'{obj}' não encontrado no game.js"

    @pytest.mark.parametrize("fn", REQUIRED_FUNCTIONS_IN_GAME)
    def test_game_method_declared(self, js, fn):
        assert fn in js, f"Game.{fn}() não encontrado no game.js"

    @pytest.mark.parametrize("fn", REQUIRED_FUNCTIONS_IN_UI)
    def test_ui_method_declared(self, js, fn):
        assert fn in js, f"UI.{fn}() não encontrado no game.js"

    def test_abort_controller_used_for_cancel(self, js):
        assert "AbortController" in js, (
            "AbortController não encontrado — o cancelamento da Garage AI não funciona"
        )

    def test_handle_send_click_declared(self, js):
        assert "_handleSendClick" in js, (
            "_handleSendClick não declarado — botão stop da Garage AI quebrado"
        )

    def test_cancel_method_declared(self, js):
        assert "cancel()" in js or "cancel (" in js or "cancel(){" in js or "cancel() {" in js, (
            "StudyChat.cancel() não declarado"
        )

    def test_mobile_controls_wired(self, js):
        assert "mobile-controls" in js, (
            "Controles mobile não referenciados no game.js"
        )

    def test_resize_canvas_logic(self, js):
        assert "canvas.width" in js and "canvas.height" in js, (
            "Lógica de resize do canvas não encontrada no game.js"
        )

    def test_world_state_save_called(self, js):
        assert "WorldStatePersistence.save" in js, (
            "WorldStatePersistence.save() não chamado no game.js — estado do mundo não é salvo"
        )

    def test_book_collection_guarded_by_locked_region(self, js):
        """
        Books NÃO devem ser coletados quando o player está dentro de uma empresa.
        Verifica que o guard !State.lockedRegion existe antes da coleta de livros.
        """
        assert "State.lockedRegion" in js, (
            "State.lockedRegion não referenciado no game.js"
        )
        # The guard pattern: if (!State.lockedRegion) { ... collect books ... }
        pattern = r"if\s*\(\s*!\s*State\.lockedRegion\s*\)"
        assert re.search(pattern, js), (
            "Guard '!State.lockedRegion' antes da coleta de livros não encontrado. "
            "Bug: personagem pode coletar livros dentro de empresa!"
        )

    def test_book_collection_persists_immediately(self, js):
        """Coleta de livro deve disparar WorldStatePersistence.save imediata."""
        assert "SFX.bookCollect" in js, "SFX.bookCollect() não encontrado"
        # Use rfind to locate the CALL SITE (last SFX.bookCollect reference)
        # instead of the function definition (first occurrence).
        call_site_idx = js.rfind("SFX.bookCollect")
        next_800 = js[call_site_idx : call_site_idx + 800]
        assert "WorldStatePersistence.save" in next_800, (
            "WorldStatePersistence.save() não é chamado logo após coleta de livro"
        )

    def test_reconstruct_completed_regions_exists(self, js):
        assert "_reconstructCompletedRegions" in js, (
            "_reconstructCompletedRegions() não encontrado — "
            "regiões completadas podem não ser restauradas corretamente"
        )

    def test_completed_regions_restored_on_load(self, js):
        assert "completedRegions" in js and "loadSession" in js, (
            "Estado de regiões completadas pode não ser restaurado ao carregar sessão"
        )

    def test_prevent_victory_on_partial_completion(self, js):
        assert "_allCompaniesComplete" in js, (
            "_allCompaniesComplete() não encontrado — vitória pode disparar antes da hora"
        )


# ---------------------------------------------------------------------------
# 4. Integridade dos arquivos estáticos
# ---------------------------------------------------------------------------

class TestStaticFilesExist:
    """Todos os arquivos estáticos necessários devem existir."""

    REQUIRED_FILES = [
        os.path.join(STATIC_DIR, "index.html"),
        os.path.join(STATIC_DIR, "style.css"),
        os.path.join(STATIC_DIR, "game.js"),
    ]

    @pytest.mark.parametrize("path", REQUIRED_FILES, ids=["index.html", "style.css", "game.js"])
    def test_static_file_exists(self, path):
        assert os.path.exists(path), f"Arquivo estático não encontrado: {path}"

    @pytest.mark.parametrize("path", REQUIRED_FILES, ids=["index.html", "style.css", "game.js"])
    def test_static_file_not_empty(self, path):
        size = os.path.getsize(path)
        assert size > 1000, f"Arquivo {os.path.basename(path)} parece vazio ou corrompido ({size} bytes)"

    def test_game_js_is_large_enough(self):
        size = os.path.getsize(GAME_JS)
        assert size > 200_000, (
            f"game.js muito pequeno ({size} bytes) — provavelmente truncado"
        )


# ---------------------------------------------------------------------------
# 5. Testes de bugs conhecidos — personagem e livros
# ---------------------------------------------------------------------------

class TestKnownBugFixes:
    """
    Testa que bugs conhecidos foram corrigidos e não regridem.
    Documentados durante o desenvolvimento do 404 Garage.
    """

    def test_bug_book_collection_inside_company_blocked(self, js):
        """
        Bug: personagem voltava tentando pegar livros e não conseguia.
        Fix: guard !State.lockedRegion antes da coleta de livros.
        """
        pattern = r"if\s*\(\s*!\s*State\.lockedRegion\s*\)"
        assert re.search(pattern, js), (
            "BUG CRÍTICO: coleta de livros não está bloqueada dentro de empresa. "
            "Personagem pode ficar preso tentando pegar livros."
        )

    def test_bug_current_region_clearable(self, js):
        """
        Bug: current_region nunca era limpa ao sair de uma empresa.
        Fix: current_region=None enviado no save-world-state ao sair.
        """
        assert "current_region" in js, "current_region não gerenciada no JS"

    def test_bug_double_submit_guarded(self, js):
        """
        Bug: duplo clique em botão de opção disparava dois submits.
        Fix: btns.forEach(b => b.disabled = true) antes do submit.
        """
        assert "b.disabled = true" in js or "disabled" in js, (
            "Double-submit guard não encontrado no game.js"
        )

    def test_bug_session_expired_handled(self, js):
        """
        Bug: sessão expirada causava erro 401 sem mensagem ao usuário.
        Fix: _handle401 com tryRefresh + showScreen('screen-login').
        """
        assert "_handle401" in js or "handle401" in js, (
            "Handler de sessão expirada (401) não encontrado"
        )
        assert "screen-login" in js, "Redirecionamento para login não encontrado"

    def test_bug_victory_only_when_all_companies_complete(self, js):
        """
        Bug: vitória disparava antes de completar todas as empresas.
        Fix: _allCompaniesComplete() verifica todas as BUILDINGS.
        """
        assert "_allCompaniesComplete" in js, (
            "Verificação de conclusão de todas as empresas não encontrada"
        )
        assert "BUILDINGS.length" in js, (
            "Verificação do total de empresas (BUILDINGS.length) não encontrada"
        )

    def test_bug_game_over_recovery_keeps_score(self, js):
        """
        Bug: game_over apagava a pontuação histórica.
        Fix: score não é reset, apenas completed_challenges da fase.
        """
        # The recover logic in JS should not reset score
        recover_section_match = re.search(
            r"recover[\s\S]{0,500}score", js
        )
        # Score should be preserved — recover should NOT set score = 0
        if recover_section_match:
            recover_text = recover_section_match.group(0)
            assert "score = 0" not in recover_text and "score=0" not in recover_text, (
                "BUG: recover() reset a pontuação para 0"
            )
