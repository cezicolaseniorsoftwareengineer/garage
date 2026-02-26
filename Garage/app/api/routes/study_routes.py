"""Study Chat API routes -- authenticated learning coach for game content."""
from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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


def _build_stream_body(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> dict:
    return {
        "model": model,
        "stream": True,
        "max_output_tokens": max_tokens,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user",   "content": [{"type": "input_text", "text": user_prompt}]},
        ],
    }


def _stream_openai_sse(system_prompt: str, user_prompt: str):
    """Generator: yields SSE lines to the client token-by-token.

    Falls back gracefully to emitting the full answer as a single event when
    the model returns a plain JSON response instead of an SSE stream (e.g.
    when the 'stream' parameter is silently ignored or unsupported).
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        yield 'data: {"err": "Study chat unavailable: missing API key."}\n\n'
        return

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    endpoint = base_url + "/responses"
    max_tokens = int(os.environ.get("AI_MAX_TOKENS", "4096") or "4096")
    timeout = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "90") or "90")

    for model in _candidate_models():
        # Try WITHOUT stream first for maximum compatibility; if successful but
        # the model also supports SSE the non-stream path is just as correct.
        body_nostream = {
            "model": model,
            "max_output_tokens": max_tokens,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user",   "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        }
        body_stream = dict(body_nostream, stream=True)

        # --- Attempt 1: streaming SSE ---
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body_stream).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            raw_bytes = b""
            got_delta = False
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                for raw in resp:
                    raw_bytes += raw
                    line = raw.decode("utf-8").rstrip("\r\n")
                    if not line:
                        continue
                    if line == "data: [DONE]":
                        if got_delta:
                            yield f'data: {{"done": true, "model": {json.dumps(model)}}}\n\n'
                        break
                    if not line.startswith("data: "):
                        continue
                    try:
                        chunk = json.loads(line[6:])
                    except Exception:
                        continue
                    ev = chunk.get("type", "")
                    if ev in ("response.output_text.delta", "content_block_delta"):
                        delta = chunk.get("delta", "")
                        if isinstance(delta, dict):
                            delta = delta.get("text", "")
                        if delta:
                            got_delta = True
                            yield f'data: {json.dumps({"d": delta})}\n\n'
                    elif ev in ("response.done", "response.completed", "message_stop"):
                        if got_delta:
                            yield f'data: {{"done": true, "model": {json.dumps(model)}}}\n\n'
                        break

            if got_delta:
                return  # streaming worked fine

            # --- Fallback: response was non-SSE JSON (stream ignored/unsupported) ---
            try:
                payload = json.loads(raw_bytes.decode("utf-8"))
                text = _extract_output_text(payload)
                if text:
                    yield f'data: {json.dumps({"d": text})}\n\n'
                    yield f'data: {{"done": true, "model": {json.dumps(model)}}}\n\n'
                    return
            except Exception:
                pass

            # --- Attempt 2: explicit non-stream call ---
            request2 = urllib.request.Request(
                endpoint,
                data=json.dumps(body_nostream).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request2, timeout=timeout) as resp2:
                    payload2 = json.loads(resp2.read().decode("utf-8"))
                text2 = _extract_output_text(payload2)
                if text2:
                    yield f'data: {json.dumps({"d": text2})}\n\n'
                    yield f'data: {{"done": true, "model": {json.dumps(model)}}}\n\n'
                    return
            except urllib.error.HTTPError as exc2:
                try:
                    err_body = json.loads(exc2.read().decode("utf-8"))
                    msg = err_body.get("error", {}).get("message", "")
                except Exception:
                    msg = f"HTTP {exc2.code}"
                if _is_model_unavailable_error(msg):
                    continue
                yield f'data: {{"err": {json.dumps(msg)}}}\n\n'
                return
            except (urllib.error.URLError, TimeoutError, socket.timeout):
                continue

        except urllib.error.HTTPError as exc:
            try:
                err_body = json.loads(exc.read().decode("utf-8"))
                msg = err_body.get("error", {}).get("message", "")
            except Exception:
                msg = f"HTTP {exc.code}"
            if _is_model_unavailable_error(msg):
                continue
            # If 'stream' param itself is unsupported, retry without it
            if _unsupported_parameter_name(msg) == "stream":
                request3 = urllib.request.Request(
                    endpoint,
                    data=json.dumps(body_nostream).encode("utf-8"),
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request3, timeout=timeout) as resp3:
                        payload3 = json.loads(resp3.read().decode("utf-8"))
                    text3 = _extract_output_text(payload3)
                    if text3:
                        yield f'data: {json.dumps({"d": text3})}\n\n'
                        yield f'data: {{"done": true, "model": {json.dumps(model)}}}\n\n'
                        return
                except Exception:
                    continue
                continue
            yield f'data: {{"err": {json.dumps(msg)}}}\n\n'
            return
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            continue

    yield 'data: {"err": "Nenhum modelo disponivel no momento. Tente novamente."}\n\n'


def _call_openai_responses(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:
    """Non-streaming call to OpenAI Responses API. Returns (text, response_id, model)."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Study chat unavailable. Missing OPENAI_API_KEY in server environment.",
        )

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    endpoint = base_url + "/responses"
    max_output_tokens = int(os.environ.get("AI_MAX_TOKENS", "4096") or "4096")
    request_retries = int(os.environ.get("OPENAI_REQUEST_RETRIES", "2") or "2")
    request_retries = max(1, min(request_retries, 4))
    attempted: list[str] = []
    last_detail = "unknown error"

    for model in _candidate_models():
        attempted.append(model)
        body = {
            "model": model,
            "max_output_tokens": max_output_tokens,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
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


# Limite de tokens de saida compartilhado por todos os provedores (default: 4096)
_AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "4096") or "4096")


def _call_gemini(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:
    """Non-streaming call to Google Gemini. Returns (text, response_id, model)."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    max_tokens = int(os.environ.get("AI_MAX_TOKENS", "4096") or "4096")
    timeout = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "90") or "90")
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = f"HTTP {exc.code}"
        try:
            msg = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
            if msg:
                detail = msg
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"Gemini error: {detail}")
    except (urllib.error.URLError, TimeoutError, socket.timeout):
        raise HTTPException(status_code=504, detail="Gemini timeout.")
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail="Gemini retornou resposta vazia ou inesperada.")
    return text, "", model


def _stream_gemini_sse(system_prompt: str, user_prompt: str):
    """Generator: yields SSE lines using Google Gemini streaming API."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        yield 'data: {"err": "Study chat unavailable: missing GEMINI_API_KEY."}\n\n'
        return
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    max_tokens = int(os.environ.get("AI_MAX_TOKENS", "4096") or "4096")
    timeout = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "90") or "90")
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":streamGenerateContent?key={api_key}&alt=sse"
    )
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        got_delta = False
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8").rstrip("\r\n")
                if not line or not line.startswith("data: "):
                    continue
                try:
                    chunk = json.loads(line[6:])
                    delta = chunk["candidates"][0]["content"]["parts"][0]["text"]
                    if delta:
                        got_delta = True
                        yield f'data: {json.dumps({"d": delta})}\n\n'
                except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                    continue
        if got_delta:
            yield f'data: {{"done": true, "model": {json.dumps(model)}}}\n\n'
        else:
            yield 'data: {"err": "Gemini nao retornou resposta."}\n\n'
    except urllib.error.HTTPError as exc:
        try:
            msg = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", f"HTTP {exc.code}")
        except Exception:
            msg = f"HTTP {exc.code}"
        yield f'data: {{"err": {json.dumps(msg)}}}\n\n'
    except (urllib.error.URLError, TimeoutError, socket.timeout):
        yield 'data: {"err": "Gemini timeout. Tente novamente."}\n\n'


def _call_groq(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:
    """Non-streaming call to Groq Chat Completions API. Returns (text, request_id, model)."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant").strip()
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    max_tokens = int(os.environ.get("AI_MAX_TOKENS", "4096") or "4096")
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        request_id = data.get("id", "groq")
        used_model = data.get("model", model)
        return text, request_id, used_model
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", f"HTTP {exc.code}")
        except Exception:
            detail = f"HTTP {exc.code}"
        raise HTTPException(status_code=502, detail=f"Groq error: {detail}")
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise HTTPException(status_code=504, detail=f"Groq timeout: {exc}")


def _stream_groq_sse(system_prompt: str, user_prompt: str):
    """Streaming SSE generator for Groq Chat Completions API."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        yield 'data: {"err": "Study chat unavailable: missing GROQ_API_KEY."}\n\n'
        return
    model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant").strip()
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    max_tokens = int(os.environ.get("AI_MAX_TOKENS", "4096") or "4096")
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "stream": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                payload_str = line[5:].strip()
                if payload_str == "[DONE]":
                    yield 'data: {"done": true}\n\n'
                    return
                try:
                    chunk = json.loads(payload_str)
                    token = chunk["choices"][0].get("delta", {}).get("content", "")
                    if token:
                        yield f'data: {json.dumps({"token": token})}\n\n'
                except (KeyError, json.JSONDecodeError):
                    continue
    except urllib.error.HTTPError as exc:
        try:
            msg = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", f"HTTP {exc.code}")
        except Exception:
            msg = f"HTTP {exc.code}"
        yield f'data: {{"err": {json.dumps(msg)}}}\n\n'
    except (urllib.error.URLError, TimeoutError, socket.timeout):
        yield 'data: {"err": "Groq timeout. Tente novamente."}\n\n'


# ---------------------------------------------------------------------------
# Fallback de streaming: Gemini → Groq → OpenAI em runtime
# ---------------------------------------------------------------------------
def _stream_with_fallback(system_prompt: str, user_prompt: str):
    """
    Tenta cada provedor em ordem. Se o primeiro evento SSE contiver {"err": ...}
    (quota esgotada, auth, timeout), abandona e tenta o proximo proovedor.
    Se nenhum funcionar, emite o ultimo erro ao frontend.
    """
    providers: list[tuple[str, object]] = []
    if os.environ.get("GROQ_API_KEY", "").strip():
        providers.append(("Groq", lambda: _stream_groq_sse(system_prompt, user_prompt)))
    if os.environ.get("OPENAI_API_KEY", "").strip():
        providers.append(("OpenAI", lambda: _stream_openai_sse(system_prompt, user_prompt)))

    if not providers:
        yield 'data: {"err": "Nenhuma API key de IA configurada no servidor."}\n\n'
        return

    last_err = "Erro desconhecido."
    for name, factory in providers:
        gen = factory()
        try:
            first = next(gen)
        except StopIteration:
            continue

        # Verifica se o primeiro evento e um erro
        try:
            first_data = first.strip()
            if first_data.startswith("data: "):
                first_json = json.loads(first_data[6:])
                if "err" in first_json:
                    last_err = f"[{name}] {first_json['err']}"
                    continue  # tenta o proximo provedor
        except (json.JSONDecodeError, KeyError):
            pass  # nao e JSON ou nao tem 'err' — pode ser um token, prossegue

        # Primeiro evento e valido: emite e continua o stream normalmente
        yield first
        yield from gen
        return

    yield f'data: {{"err": {json.dumps(last_err)}}}\n\n'


# ---------------------------------------------------------------------------
# Response cache — evita chamadas de API repetidas (TTL 1 hora)
# ---------------------------------------------------------------------------
_RESPONSE_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 3600  # segundos
_CACHE_MAX = 500   # max entradas antes de eviction


def _cache_key(challenge_id: str | None, message: str) -> str:
    raw = f"{challenge_id or ''}::{message.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()  # nosec — não é uso criptográfico


def _cache_get(key: str) -> str | None:
    entry = _RESPONSE_CACHE.get(key)
    if entry and time.monotonic() - entry[1] < _CACHE_TTL:
        return entry[0]
    _RESPONSE_CACHE.pop(key, None)
    return None


def _cache_set(key: str, value: str) -> None:
    if len(_RESPONSE_CACHE) >= _CACHE_MAX:
        oldest = sorted(_RESPONSE_CACHE.items(), key=lambda x: x[1][1])[:100]
        for k, _ in oldest:
            del _RESPONSE_CACHE[k]
    _RESPONSE_CACHE[key] = (value, time.monotonic())


# ---------------------------------------------------------------------------
# Agente especialista: Logica de Programacao + ED + Algoritmos (Intern→Principal)
# ---------------------------------------------------------------------------

# Curriculo progressivo completo por stage
_STAGE_CURRICULUM: dict[str, dict] = {
    "Intern": {
        "foco": "Logica de Programacao Fundamental",
        "topicos": (
            "Logica de programacao: sequencia, selecao (if/else/switch), repeticao (for/while/do-while). "
            "Variaveis, tipos primitivos (int, double, boolean, char), casting. "
            "Operadores: aritmeticos, relacionais, logicos (&&, ||, !), ternario. "
            "Metodos: parametros, retorno, sobrecarga. Escopo de variaveis. "
            "Arrays unidimensionais: declaracao, inicializacao, iteracao, busca linear. "
            "Strings: length, charAt, substring, equals, contains, split. "
            "Recursao basica: fatorial, fibonacci (identifique caso base e recursivo). "
            "OOP basico: classe, objeto, construtor, this, encapsulamento (get/set)."
        ),
        "estruturas": "Array, String, int[], ArrayList<Integer> (introducao).",
        "algoritmos": "Busca linear O(n), contagem, soma de array, inversao de string, palindromo.",
        "complexidade": "Introducao a O(n) e O(1). Explique com contagem de passos, nao formula.",
        "erros_comuns": "ArrayIndexOutOfBounds, NullPointerException, loop infinito, off-by-one.",
        "tom": "Use analogias do cotidiano. Explique CADA linha de codigo. Evite jargoes.",
    },
    "Junior": {
        "foco": "Estruturas de Dados Lineares e Ordenacao Basica",
        "topicos": (
            "Collections: ArrayList, LinkedList, Stack, Queue, ArrayDeque. Iterator, for-each. "
            "OOP intermediario: heranca, polimorfismo, interfaces, classes abstratas, super. "
            "Generics basico: List<T>, Map<K,V>. Autoboxing/unboxing. "
            "Excecoes: try/catch/finally, throw/throws, checked vs unchecked. "
            "Ordenacao: Bubble Sort (didatico), Selection Sort, Insertion Sort. "
            "Busca binaria: pre-requisito (array ordenado), implementacao iterativa e recursiva. "
            "Two Pointers: problemas de par com soma alvo, palindromo em array. "
            "Prefix Sum: soma de subarray em O(1) apos pre-processamento O(n)."
        ),
        "estruturas": "ArrayList, LinkedList, Stack, Queue, ArrayDeque, int[][].",
        "algoritmos": "Bubble/Selection/Insertion Sort O(n^2), Busca binaria O(log n), Two Pointers O(n).",
        "complexidade": "O(n), O(n^2), O(log n), O(n log n). Mostre na pratica contando iteracoes.",
        "erros_comuns": "Modificar lista durante iteracao (ConcurrentModificationException), comparar objetos com == em vez de equals.",
        "tom": "Mostre o 'antes e depois' da estrutura. Use diagramas textuais (ex: [1]→[2]→[3]).",
    },
    "Mid": {
        "foco": "Estruturas Nao-Lineares, Hashing e Ordenacao Eficiente",
        "topicos": (
            "HashMap/HashSet: funcao hash, colisao (chaining/open addressing), load factor, rehashing. "
            "TreeMap/TreeSet: BST, balanceamento (conceito Red-Black), operacoes O(log n). "
            "Merge Sort: divisao e conquista, estavel, O(n log n) garantido. "
            "Quick Sort: pivot, particao in-place, pior caso O(n^2) vs medio O(n log n). "
            "Heap/PriorityQueue: MinHeap, MaxHeap, heapify, K maiores/menores elementos. "
            "BFS/DFS basico: grafo como lista de adjacencia, deteccao de ciclo, componentes conexos. "
            "Sliding Window: subarray/substring com tamanho fixo e variavel. "
            "Streams API: filter, map, reduce, collect, sorted, distinct, limit."
        ),
        "estruturas": "HashMap, HashSet, TreeMap, TreeSet, PriorityQueue, Grafo (List<List<Integer>>).",
        "algoritmos": "Merge Sort, Quick Sort, Heap Sort, BFS, DFS, Sliding Window, Kadane (max subarray).",
        "complexidade": "Analise amortizada de HashMap. Custo de rehashing. Best/average/worst case.",
        "erros_comuns": "hashCode sem equals, equals sem hashCode, NPE em unboxing, ConcurrentModification em stream.",
        "tom": "Mostre invariantes do algoritmo. Explique POR QUE funciona, nao so como.",
    },
    "Senior": {
        "foco": "Grafos Avancados, Programacao Dinamica e Engenharia de Producao",
        "topicos": (
            "Grafos: Dijkstra (min-heap), Bellman-Ford (pesos negativos), Floyd-Warshall (all-pairs). "
            "Trie: insercao/busca/prefixo, autocompletar, contagem de palavras. "
            "Union-Find (DSU): path compression, union by rank, deteccao de ciclo em grafo nao-dirigido. "
            "Programacao Dinamica: subproblemas sobrepostos, subestrutura otima. "
            "Problemas classicos de DP: LCS, LIS, Knapsack 0/1, Coin Change, Edit Distance, DP em grid. "
            "Backtracking: N-Queens, subsets, permutacoes, sudoku solver, poda (pruning). "
            "SOLID na pratica: exemplos de violacao e correcao. Strategy, Factory Method, Builder, Observer. "
            "Concorrencia Java: Thread, Runnable, synchronized, volatile, AtomicInteger, CountDownLatch."
        ),
        "estruturas": "Trie, DSU, Segment Tree (consulta), grafo dirigido/nao-dirigido, matriz de DP.",
        "algoritmos": "Dijkstra O((V+E)logV), BFS/DFS avancado, DP classica, Backtracking com poda.",
        "complexidade": "Analise de DP (espaco pode ser otimizado de O(n^2) para O(n)). Amortized analysis.",
        "erros_comuns": "Race condition, deadlock, misuse de Optional, off-by-one em intervals de DP.",
        "tom": "Discuta invariantes, edge cases e otimizacoes. Mostre versao O(n^2) antes de O(n log n).",
    },
    "Staff": {
        "foco": "Sistemas Distribuidos, Concorrencia Avancada e Algoritmos de Alta Performance",
        "topicos": (
            "Concorrencia avancada: ExecutorService, CompletableFuture (thenApply/thenCompose/allOf), "
            "ForkJoinPool, ReentrantLock, ReadWriteLock, Semaphore, BlockingQueue, ConcurrentHashMap. "
            "Segment Tree: range query (soma, min, max), range update (lazy propagation). "
            "Fenwick Tree (BIT): prefix sum mutavel em O(log n). "
            "Algoritmos de string: KMP (falha array), Rabin-Karp (hash rolling), Z-Algorithm. "
            "Topological Sort: Kahn (BFS) e DFS. Deteccao de ciclo em DAG. "
            "Algoritmos gulosos avancados: Interval Scheduling, Huffman Coding, Prim, Kruskal (MST). "
            "Design de sistemas: consistencia eventual, CAP theorem, rate limiting, sharding, caching. "
            "JVM internals: GC (G1, ZGC), JIT compilation, stack vs heap, memory model Java."
        ),
        "estruturas": "Segment Tree, Fenwick Tree, Sparse Table, Skip List (conceito), B-Tree (conceito).",
        "algoritmos": "KMP O(n+m), Topological Sort O(V+E), MST O(E log V), Segment Tree O(log n).",
        "complexidade": "Analise de espaco em Segment Tree. Trade-off memoria vs tempo em Sparse Table.",
        "erros_comuns": "Memory leak em listeners, thread starvation, false sharing em cache de CPU.",
        "tom": "Discuta como decisoes de design impactam escala. Sempre mencione producao e monitoramento.",
    },
    "Principal": {
        "foco": "Arquitetura FAANG-Level, Algoritmos de Competicao e Lideranca Tecnica",
        "topicos": (
            "Algoritmos de competicao: Bit manipulation avancado (bitmask DP), "
            "Mo's Algorithm, CDQ Divide and Conquer, Heavy-Light Decomposition em arvore. "
            "Persistent Data Structures: persistent segment tree, versioning. "
            "Suffix Array + LCP Array: O(n log n), aplicacoes em busca de padroes e LCS de multiplas strings. "
            "Network Flow: Ford-Fulkerson, Edmonds-Karp, Dinic O(V^2 * E). Bipartite Matching. "
            "Convex Hull Trick: otimizacao de DP O(n^2) para O(n). "
            "Arquitetura de plataformas: event sourcing, CQRS, saga pattern, circuit breaker, bulkhead. "
            "Lideranca tecnica: como revisar codigo de forma pedagogica, ADRs (Architecture Decision Records), "
            "definicao de SLOs/SLAs, post-mortem sem culpa, design de APIs publicas evolutivas."
        ),
        "estruturas": "Persistent Segment Tree, Suffix Array, Union-Find com rollback, Link-Cut Tree (conceito).",
        "algoritmos": "Dinic O(V^2E), Suffix Array O(n log n), bitmask DP O(2^n * n), CHT O(n).",
        "complexidade": "Prova formal de complexidade. Reducoes entre problemas. NP-completude basica.",
        "erros_comuns": "Over-engineering, pre-optimizacao prematura, ignorar observabilidade em producao.",
        "tom": "Trate como par senior. Discuta trade-offs arquiteturais e impacto no negocio. Cite exemplos reais de FAANG.",
    },
}

# Diretriz curta (usada no system prompt)
_STAGE_GUIDANCE: dict[str, str] = {
    k: v["foco"] for k, v in _STAGE_CURRICULUM.items()
}


def _build_prompts(
    stage: str,
    region: str,
    challenge_title: str,
    challenge_desc: str,
    history_text: str,
    books_text: str,
    message: str,
) -> tuple[str, str]:
    """Constroi system + user prompt para o agente especialista por stage."""
    curriculum = _STAGE_CURRICULUM.get(stage, _STAGE_CURRICULUM["Mid"])

    system_prompt = (
        "Voce e o Professor CeziCola — agente especialista em Logica de Programacao, "
        "Estruturas de Dados e Algoritmos, do nivel Intern ao Principal Engineer.\n\n"

        # ── Logica de Programacao ──────────────────────────────────────────
        "LOGICA DE PROGRAMACAO (base de tudo):\n"
        "Sequencia, selecao (if/else/switch), repeticao (for/while/do-while/for-each). "
        "Decomposicao de problemas em subproblemas. Recursao (caso base, caso recursivo, pilha de chamadas). "
        "Invariantes de loop (o que e verdade antes/durante/apos cada iteracao). "
        "Raciocinio por exemplos: trace manual linha a linha antes de codificar.\n\n"

        # ── Java ──────────────────────────────────────────────────────────
        "JAVA JDK 21+ (linguagem exclusiva de implementacao):\n"
        "Tipos primitivos e wrappers. OOP: heranca, polimorfismo, encapsulamento, abstracao, interfaces. "
        "Generics, Collections Framework (List/Set/Map/Queue/Deque), Streams API, lambdas, Optional. "
        "Records, sealed classes, pattern matching (instanceof). "
        "Excecoes: checked vs unchecked, try-with-resources. "
        "Concorrencia: Thread, ExecutorService, CompletableFuture, synchronized, volatile, "
        "ReentrantLock, AtomicInteger, ConcurrentHashMap, BlockingQueue. "
        "JVM: stack vs heap, GC basico, JIT. JUnit 5 para testes.\n\n"

        # ── Estruturas de Dados ───────────────────────────────────────────
        "ESTRUTURAS DE DADOS (conhecimento completo):\n"
        "Lineares: Array, ArrayList, LinkedList (simples/dupla/circular), Stack, Queue, Deque, CircularBuffer.\n"
        "Hash: HashMap, LinkedHashMap, TreeMap, HashSet, LinkedHashSet, TreeSet — "
        "funcao hash, colisao (chaining/open addressing), load factor, rehashing.\n"
        "Arvores: BST, AVL (conceito), Red-Black Tree (conceito), Heap (MinHeap/MaxHeap), "
        "Trie, Segment Tree (point update, range query, lazy propagation), Fenwick Tree.\n"
        "Grafos: lista de adjacencia, matriz de adjacencia, grafo dirigido/nao-dirigido/ponderado.\n"
        "Avancadas: Union-Find (DSU) com path compression e union by rank, "
        "Sparse Table (RMQ), Suffix Array, Persistent Segment Tree (conceito).\n\n"

        # ── Algoritmos ────────────────────────────────────────────────────
        "ALGORITMOS (repertorio completo):\n"
        "Busca: linear O(n), binaria O(log n), ternaria O(log n).\n"
        "Ordenacao: Bubble/Selection/Insertion O(n^2) [didatico], "
        "Merge Sort O(n log n) [estavel], Quick Sort O(n log n) medio [in-place], "
        "Heap Sort O(n log n), Counting/Radix Sort O(n+k) [nao-comparativo].\n"
        "Grafos: BFS O(V+E), DFS O(V+E), Dijkstra O((V+E)log V), Bellman-Ford O(VE), "
        "Floyd-Warshall O(V^3), Prim/Kruskal O(E log V), Topological Sort, Tarjan (SCC).\n"
        "Programacao Dinamica: memoizacao top-down, tabulacao bottom-up, reconstrucao. "
        "Classicos: Fibonacci, LCS, LIS, Knapsack 0/1, Coin Change, Edit Distance, "
        "DP em grid, DP em arvore, bitmask DP.\n"
        "Tecnicas: Two Pointers, Sliding Window (fixo/variavel), Prefix Sum, "
        "Monotonic Stack, Monotonic Queue, Backtracking com poda, "
        "Divisao e Conquista, Algoritmos Gulosos, Bit Manipulation.\n"
        "Strings: KMP O(n+m), Rabin-Karp O(n+m) medio, Z-Algorithm O(n).\n\n"

        # ── Complexidade ──────────────────────────────────────────────────
        "ANALISE DE COMPLEXIDADE:\n"
        "Big-O (pior caso), Big-Theta (caso medio), Big-Omega (melhor caso). "
        "Complexidade espacial (auxiliar vs total). Analise amortizada. "
        "Comparacao de crescimento: O(1) < O(log n) < O(n) < O(n log n) < O(n^2) < O(2^n) < O(n!).\n\n"

        # ── Engenharia ────────────────────────────────────────────────────
        "ENGENHARIA DE SOFTWARE:\n"
        "SOLID, DRY, KISS, YAGNI. Design Patterns (GoF): Strategy, Factory Method, Builder, "
        "Observer, Singleton (thread-safe), Decorator, Composite, Iterator, Command, Proxy. "
        "DDD basico: entidade, value object, repositorio, servico de dominio. "
        "Clean Code: nomes expressivos, funcoes pequenas, comentarios apenas quando necessario. "
        "Testes: JUnit 5, AAA (Arrange/Act/Assert), TDD conceito, mocking basico.\n\n"

        # ── Regras absolutas ──────────────────────────────────────────────
        "REGRAS ABSOLUTAS — NUNCA VIOLE:\n"
        "1. Todo codigo Java deve ser SEMPRE COMPLETO e compilavel no JDK 21 sem dependencias externas.\n"
        "   Isso significa: NUNCA truncar blocos de codigo, NUNCA omitir fechamento de chaves, "
        "NUNCA escrever '// resto do codigo...' ou '// ...' ou comentarios que substituam codigo real.\n"
        "2. Todo codigo Java postado DEVE incluir a classe completa com 'public static void main(String[] args)' "
        "   e TODOS os metodos mencionados completamente implementados — sem esqueletos vazios.\n"
        "3. Se o desafio ativo na IDE tiver um nome de classe especifico (ex: AnagramCheck, MaxSubarray), "
        "   o codigo gerado DEVE usar exatamente esse nome de classe.\n"
        "4. Sempre informe complexidade de TEMPO e ESPACO com justificativa.\n"
        "5. Jamais invente metodos, classes ou APIs inexistentes no Java stdlib.\n"
        "6. Se faltar informacao, declare a suposicao ANTES de responder.\n"
        "7. Responda em pt-BR. Nomes de variaveis, metodos e classes em ingles.\n"
        "8. Adapte profundidade e linguagem EXATAMENTE ao nivel do aluno (abaixo).\n\n"

        # ── Nivel do aluno ────────────────────────────────────────────────
        f"NIVEL DO ALUNO: {stage}\n"
        f"FOCO DESTE NIVEL: {curriculum['foco']}\n"
        f"TOPICOS PRIORITARIOS: {curriculum['topicos']}\n"
        f"ESTRUTURAS-CHAVE: {curriculum['estruturas']}\n"
        f"ALGORITMOS-CHAVE: {curriculum['algoritmos']}\n"
        f"ANALISE DE COMPLEXIDADE: {curriculum['complexidade']}\n"
        f"ERROS COMUNS NESTE NIVEL: {curriculum['erros_comuns']}\n"
        f"TOM E ABORDAGEM: {curriculum['tom']}"
    )

    desc_trunc = (challenge_desc[:300] + "...") if len(challenge_desc) > 300 else challenge_desc

    # Formato de resposta varia por stage
    if stage in ("Intern", "Junior"):
        response_format = (
            "1. INTUICAO: Explique em 2-3 linhas com analogia do cotidiano.\n"
            "2. TRACE MANUAL: Mostre passo a passo com valores concretos (ex: i=0, arr=[3,1,2]).\n"
            "3. CODIGO JAVA: Curto, comentado linha a linha. Inclua main() com exemplo executavel.\n"
            "4. COMPLEXIDADE: Tempo O(??) | Espaco O(??) — explique contando passos, nao formula.\n"
            "5. ERRO COMUM: Um erro tipico neste nivel e como evitar.\n"
            "6. DESAFIO: Uma variacao simples para praticar (1-2 linhas)."
        )
    elif stage in ("Mid", "Senior"):
        response_format = (
            "1. INTUICAO: Conceito central em 2-3 linhas. Por que esta estrutura/algoritmo existe?\n"
            "2. INVARIANTE: O que e verdade em todo momento de execucao do algoritmo?\n"
            "3. CODIGO JAVA: Implementacao limpa com comentarios nos pontos criticos.\n"
            "4. COMPLEXIDADE: Tempo O(??) | Espaco O(??) — justifique cada termo.\n"
            "5. TRADE-OFFS: Quando usar vs. quando evitar. Compare com alternativas.\n"
            "6. DESAFIO: Um exercicio que exige adaptacao do conceito, nao copia direta."
        )
    else:  # Staff, Principal
        response_format = (
            "1. CONTEXTO: Por que esse problema/estrutura existe em sistemas reais? Cite exemplo FAANG.\n"
            "2. ABORDAGEM OTIMA: Algoritmo com complexidade maxima justificada.\n"
            "3. CODIGO JAVA: Implementacao production-grade (thread-safety se aplicavel, edge cases tratados).\n"
            "4. ANALISE FORMAL: Prova ou argumento rigoroso de corretude e complexidade.\n"
            "5. ALTERNATIVAS E TRADE-OFFS: Outras abordagens, quando cada uma vence.\n"
            "6. EXTENSAO: Como escalar para 10^8 elementos ou ambiente distribuido?"
        )

    user_prompt = (
        "=== CONTEXTO DO JOGADOR ===\n"
        f"Stage: {stage} | Regiao: {region}\n"
        f"Desafio: {challenge_title or 'N/A'}\n"
        f"Enunciado: {desc_trunc or 'N/A'}\n\n"
        "=== HISTORICO RECENTE ===\n"
        f"{history_text}\n\n"
        "=== LIVROS COLETADOS ===\n"
        f"{books_text}\n\n"
        f"=== FORMATO DE RESPOSTA OBRIGATORIO (nivel {stage}) ===\n"
        f"{response_format}\n\n"
        f"=== PERGUNTA DO ALUNO ===\n{message}"
    )

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Fallback em runtime: Groq → OpenAI (tenta o proximo se 4xx/5xx)
# ---------------------------------------------------------------------------
def _call_with_fallback(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:
    """Tenta provedores em ordem de prioridade com fallback automatico em runtime."""
    errors: list[str] = []

    # 401/403 = key invalida/revogada; 429 = quota; 5xx = erro do servidor
    _RETRIABLE = (401, 403, 429, 500, 502, 503, 504)

    if os.environ.get("GROQ_API_KEY", "").strip():
        try:
            return _call_groq(system_prompt, user_prompt)
        except HTTPException as exc:
            if exc.status_code in _RETRIABLE:
                errors.append(f"Groq HTTP {exc.status_code}")
            else:
                raise
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Groq erro: {exc}")

    if os.environ.get("OPENAI_API_KEY", "").strip():
        return _call_openai_responses(system_prompt, user_prompt)

    raise HTTPException(
        status_code=503,
        detail=f"Todos os provedores de IA indisponiveis: {', '.join(errors) or 'nenhuma API key configurada'}.",
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
    prompt_books = prompt_books[:5]  # keep prompt small for speed

    history_lines = []
    for msg in recent:
        prefix = "Aluno" if msg.role == "user" else "Inteligencia Artificial"
        compact = (msg.content or "").strip()
        if len(compact) > 180:
            compact = compact[:180].rstrip() + "..."
        history_lines.append(f"- {prefix}: {compact}")
    history_text = "\n".join(history_lines) if history_lines else "- Sem historico anterior."

    if prompt_books:
        book_lines = []
        for b in prompt_books:
            status = "coletado" if b.collected else "nao coletado"
            insight = (b.lesson or b.summary or "").strip()
            if len(insight) > 70:
                insight = insight[:70].rstrip() + "..."
            book_lines.append(f"- [{status}] {b.title} ({b.author}): {insight}")
        omitted = max(0, len(books) - len(prompt_books))
        if omitted:
            book_lines.append(f"- ... {omitted} livro(s) omitido(s) para reduzir latencia.")
        books_text = "\n".join(book_lines)
    else:
        books_text = "- Catalogo de livros nao informado no request."

    # Input validation
    msg_clean = req.message.strip()[:1000]
    if not msg_clean:
        raise HTTPException(status_code=422, detail="Mensagem nao pode ser vazia.")

    # Cache lookup (ignora mensagens muito curtas)
    c_key = _cache_key(req.challenge_id, msg_clean)
    if len(msg_clean) > 20:
        cached = _cache_get(c_key)
        if cached:
            return {"reply": cached, "model": "cache", "response_id": "cached", "stage": stage, "region": region}

    system_prompt, user_prompt = _build_prompts(
        stage, region, challenge_title, challenge_desc, history_text, books_text, msg_clean
    )

    # Fallback em runtime: Gemini → Groq → OpenAI
    answer, response_id, model = _call_with_fallback(system_prompt, user_prompt)

    if len(msg_clean) > 20:
        _cache_set(c_key, answer)

    return {
        "reply": answer,
        "model": model,
        "response_id": response_id,
        "stage": stage,
        "region": region,
    }


@router.post("/chat/stream")
def api_study_chat_stream(req: StudyChatRequest, current_user: dict = Depends(get_current_user)):
    """Streaming SSE version of study chat — sends tokens as they arrive."""
    player = _player_repo.get(req.session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_owner(player, current_user)

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

    challenge_title = challenge.title if challenge else ""
    challenge_desc  = challenge.description if challenge else ""

    recent = req.recent_messages[-8:]
    books  = req.books[:40]
    collected_count = sum(1 for b in books if b.collected)
    prompt_books = [b for b in books if b.collected] or books
    prompt_books = prompt_books[:5]

    history_lines = []
    for msg in recent:
        prefix  = "Aluno" if msg.role == "user" else "IA"
        compact = (msg.content or "").strip()[:180]
        history_lines.append(f"- {prefix}: {compact}")
    history_text = "\n".join(history_lines) or "- Sem historico."

    book_lines = []
    for b in prompt_books:
        status  = "OK" if b.collected else "--"
        insight = (b.lesson or b.summary or "").strip()[:70]
        book_lines.append(f"[{status}] {b.title}: {insight}")
    books_text = "\n".join(book_lines) or "(sem livros)"

    msg_clean = req.message.strip()[:1000]
    if not msg_clean:
        raise HTTPException(status_code=422, detail="Mensagem nao pode ser vazia.")

    system_prompt, user_prompt = _build_prompts(
        stage, region, challenge_title, challenge_desc, history_text, books_text, msg_clean
    )

    # Fallback em runtime: Gemini → Groq → OpenAI
    gen = _stream_with_fallback(system_prompt, user_prompt)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
