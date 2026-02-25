"""Study Chat API routes -- authenticated learning coach for game content."""
from __future__ import annotations

import collections
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.infrastructure.auth.dependencies import get_current_user


router = APIRouter(prefix="/api/study", tags=["study"])

_player_repo = None
_challenge_repo = None

# In-memory rate limiter: max 12 requests per 60 s per user
_RATE_LIMIT_MAX = 12
_RATE_LIMIT_WINDOW = 60  # seconds
_rate_buckets: dict[str, collections.deque] = {}


def _check_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    dq = _rate_buckets.setdefault(user_id, collections.deque())
    # Purge timestamps outside the window
    while dq and now - dq[0] > _RATE_LIMIT_WINDOW:
        dq.popleft()
    if len(dq) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de {_RATE_LIMIT_MAX} mensagens por minuto atingido. Aguarde um momento.",
        )
    dq.append(now)


def init_study_routes(player_repo, challenge_repo):
    global _player_repo, _challenge_repo
    _player_repo = player_repo
    _challenge_repo = challenge_repo


class StudyMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class StudyBook(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=2000)
    lesson: str = Field(default="", max_length=2000)
    collected: bool = False


class StudyChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=4000)
    challenge_id: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    stage: Optional[str] = Field(default=None, max_length=40)
    recent_messages: list[StudyMessage] = Field(default_factory=list)
    books: list[StudyBook] = Field(default_factory=list)


def _assert_owner(player, current_user: dict):
    """Raise 403 if the authenticated user does not own the session."""
    if player.user_id and current_user and player.user_id != current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied.")


def _extract_output_text(payload: dict) -> str:
    """Best-effort extraction for Responses API payloads."""
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _is_model_unavailable_error(detail: str) -> bool:
    text = (detail or "").lower()
    hints = [
        "does not exist",
        "model_not_found",
        "invalid model",
        "unknown model",
        "not available",
        "not found",
        "do not have access",
        "not allowed",
        "permission",
    ]
    return any(h in text for h in hints)


def _unsupported_parameter_name(detail: str) -> Optional[str]:
    text = detail or ""
    match = re.search(r"Unsupported parameter:\s*'([^']+)'", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _candidate_models() -> list[str]:
    primary = os.environ.get("OPENAI_MODEL", "gpt-5").strip() or "gpt-5"
    fallback_raw = os.environ.get(
        "OPENAI_FALLBACK_MODELS",
        "gpt-5,gpt-4.1,gpt-4.1-mini",
    )
    models: list[str] = [primary]
    for item in fallback_raw.split(","):
        m = item.strip()
        if m and m not in models:
            models.append(m)
    return models


def _post_responses_request(endpoint: str, api_key: str, body: dict) -> dict:
    timeout_seconds = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "90") or "90")
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = f"HTTP {exc.code}"
        try:
            provider_payload = json.loads(exc.read().decode("utf-8"))
            provider_error = provider_payload.get("error", {})
            provider_msg = provider_error.get("message")
            if provider_msg:
                detail = provider_msg
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"Study provider error: {detail}")
    except urllib.error.URLError:
        raise HTTPException(status_code=502, detail="Study provider network error.")
    except (TimeoutError, socket.timeout):
        raise HTTPException(status_code=504, detail="Study provider timeout.")

    try:
        return json.loads(raw)
    except Exception:
        raise HTTPException(status_code=502, detail="Invalid response from study provider.")


def _call_openai_responses(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Study chat unavailable. Missing OPENAI_API_KEY in server environment.",
        )

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    endpoint = base_url + "/responses"
    max_output_tokens = int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "700") or "700")
    request_retries = int(os.environ.get("OPENAI_REQUEST_RETRIES", "2") or "2")
    request_retries = max(1, min(request_retries, 4))
    attempted: list[str] = []
    last_detail = "unknown error"

    for model in _candidate_models():
        attempted.append(model)
        body = {
            "model": model,
            "temperature": 0.2,
            "max_output_tokens": max_output_tokens,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {"type": "input_text", "text": system_prompt},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                    ],
                },
            ],
        }
        removed_params: set[str] = set()
        model_timeout_count = 0

        while True:
            try:
                payload = _post_responses_request(endpoint, api_key, body)
                text = _extract_output_text(payload)
                if not text:
                    last_detail = f"empty answer on model {model}"
                    break
                response_id = payload.get("id", "")
                return text, response_id, model
            except HTTPException as exc:
                detail = str(exc.detail)
                last_detail = detail

                unsupported_param = _unsupported_parameter_name(detail)
                if (
                    exc.status_code == 502
                    and unsupported_param
                    and unsupported_param in body
                    and unsupported_param not in removed_params
                ):
                    removed_params.add(unsupported_param)
                    body.pop(unsupported_param, None)
                    continue

                if exc.status_code == 504:
                    model_timeout_count += 1
                    if model_timeout_count < request_retries:
                        time.sleep(0.35)
                        continue
                    # Try next model after exhausting retries for this one.
                    break

                if exc.status_code == 502 and _is_model_unavailable_error(detail):
                    break
                raise

    models_str = ", ".join(attempted) if attempted else "(none)"
    status = 504 if "timeout" in (last_detail or "").lower() else 502
    raise HTTPException(
        status_code=status,
        detail=f"Study provider error: no available model from [{models_str}]. Last error: {last_detail}",
    )


@router.post("/chat")
def api_study_chat(req: StudyChatRequest, current_user: dict = Depends(get_current_user)):
    """Generate an authenticated study answer grounded in game context."""
    player = _player_repo.get(req.session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_owner(player, current_user)

    # Rate limit per authenticated user
    uid = (current_user or {}).get("sub") or req.session_id
    _check_rate_limit(uid)

    challenge = _challenge_repo.get_by_id(req.challenge_id) if req.challenge_id else None

    stage = (req.stage or player.stage.value or "").strip() if hasattr(player.stage, "value") else (req.stage or "").strip()
    if not stage:
        stage = "Intern"

    region = (req.region or "").strip()
    if not region and challenge:
        region = challenge.region.value if hasattr(challenge.region, "value") else str(challenge.region)
    if not region:
        region = "Garage"

    challenge_title = ""
    challenge_desc = ""
    if challenge:
        challenge_title = challenge.title
        challenge_desc = challenge.description

    recent = req.recent_messages[-8:]
    books = req.books[:40]
    collected_count = sum(1 for b in books if b.collected)
    prompt_books = [b for b in books if b.collected]
    if not prompt_books:
        prompt_books = books
    prompt_books = prompt_books[:12]

    history_lines = []
    for msg in recent:
        prefix = "Aluno" if msg.role == "user" else "Inteligencia Artificial"
        compact = (msg.content or "").strip()
        if len(compact) > 450:
            compact = compact[:450].rstrip() + "..."
        history_lines.append(f"- {prefix}: {compact}")
    history_text = "\n".join(history_lines) if history_lines else "- Sem historico anterior."

    if prompt_books:
        book_lines = []
        for b in prompt_books:
            status = "coletado" if b.collected else "nao coletado"
            insight = (b.lesson or b.summary or "").strip()
            if len(insight) > 140:
                insight = insight[:140].rstrip() + "..."
            book_lines.append(f"- [{status}] {b.title} ({b.author}): {insight}")
        omitted = max(0, len(books) - len(prompt_books))
        if omitted:
            book_lines.append(f"- ... {omitted} livro(s) omitido(s) para reduzir latencia.")
        books_text = "\n".join(book_lines)
    else:
        books_text = "- Catalogo de livros nao informado no request."

    system_prompt = (
        "Voce e a Inteligencia Artificial de Engenharia do jogo GARAGE. "
        "Objetivo: ensinar Java e Estruturas de Dados com nivel profissional, progressivo e pratico. "
        "Tambem pode responder perguntas gerais de tecnologia quando o jogador pedir. "
        "Seja rigoroso, didatico e direto. "
        "Sempre explique como um engenheiro pensa em producao: invariantes, complexidade, trade-offs, validacao e seguranca. "
        "Nao invente APIs inexistentes. "
        "Se faltar contexto, declare a suposicao."
    )

    user_prompt = (
        "Contexto do jogador:\n"
        f"- Stage: {stage}\n"
        f"- Regiao: {region}\n"
        f"- Sessao: {req.session_id}\n"
        f"- Livros recebidos: {len(books)} (coletados: {collected_count})\n"
        f"- Desafio atual: {challenge_title or 'N/A'}\n"
        f"- Enunciado atual: {challenge_desc or 'N/A'}\n\n"
        "Historico recente:\n"
        f"{history_text}\n\n"
        "Catalogo de livros no jogo:\n"
        f"{books_text}\n\n"
        "Instrucao de resposta:\n"
        "1) Explique a intuicao em linguagem simples.\n"
        "2) Traga a modelagem mental por nivel (junior/pleno/senior quando fizer sentido).\n"
        "3) Mostre abordagem Java com foco em sintaxe correta e estrutura de dados adequada.\n"
        "4) Inclua complexidade Big-O e trade-offs.\n"
        "5) Entregue um codigo Java de referencia (curto e executavel).\n"
        "6) Feche com checklist de validacao e um mini exercicio.\n\n"
        f"Pergunta do jogador:\n{req.message.strip()}"
    )

    answer, response_id, model = _call_openai_responses(system_prompt, user_prompt)
    return {
        "reply": answer,
        "model": model,
        "response_id": response_id,
        "stage": stage,
        "region": region,
    }
