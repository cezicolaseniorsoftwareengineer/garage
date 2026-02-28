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

import httpx

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


def _post_responses_request(endpoint: str, api_key: str, body: dict) -> dict:  # pragma: no cover
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


def _build_stream_body(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> dict:  # pragma: no cover
    return {
        "model": model,
        "stream": True,
        "max_output_tokens": max_tokens,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user",   "content": [{"type": "input_text", "text": user_prompt}]},
        ],
    }


async def _stream_openai_sse(system_prompt: str, user_prompt: str):  # pragma: no cover
    """Async generator: yields SSE lines token-by-token using OpenAI Responses API."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        yield 'data: {"err": "Study chat unavailable: missing API key."}\n\n'
        return

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    endpoint = base_url + "/responses"
    max_tokens = int(os.environ.get("AI_CHAT_MAX_TOKENS", "350") or "350")
    timeout = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30") or "30")
    hdrs = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in _candidate_models():
            body_nostream = {
                "model": model,
                "max_output_tokens": max_tokens,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user",   "content": [{"type": "input_text", "text": user_prompt}]},
                ],
            }
            body_stream = dict(body_nostream, stream=True)

            # --- Tentativa 1: SSE streaming ---
            got_delta = False
            try_nostream = False
            try:
                async with client.stream("POST", endpoint, json=body_stream, headers=hdrs) as resp:
                    if resp.status_code >= 400:
                        err_bytes = await resp.aread()
                        try:
                            msg = json.loads(err_bytes).get("error", {}).get("message", f"HTTP {resp.status_code}")
                        except Exception:
                            msg = f"HTTP {resp.status_code}"
                        if _is_model_unavailable_error(msg):
                            continue
                        if _unsupported_parameter_name(msg) == "stream":
                            try_nostream = True
                        else:
                            yield f'data: {{"err": {json.dumps(msg)}}}\n\n'
                            return
                    else:
                        async for line in resp.aiter_lines():
                            line = line.strip()
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
            except (httpx.TimeoutException, httpx.RequestError):
                continue

            if got_delta:
                return  # streaming funcionou

            # --- Tentativa 2: non-stream fallback ---
            try:
                resp2 = await client.post(endpoint, json=body_nostream, headers=hdrs)
                if resp2.status_code >= 400:
                    try:
                        msg = resp2.json().get("error", {}).get("message", f"HTTP {resp2.status_code}")
                    except Exception:
                        msg = f"HTTP {resp2.status_code}"
                    if _is_model_unavailable_error(msg):
                        continue
                    yield f'data: {{"err": {json.dumps(msg)}}}\n\n'
                    return
                payload2 = resp2.json()
                text2 = _extract_output_text(payload2)
                if text2:
                    yield f'data: {json.dumps({"d": text2})}\n\n'
                    yield f'data: {{"done": true, "model": {json.dumps(model)}}}\n\n'
                    return
            except (httpx.TimeoutException, httpx.RequestError):
                continue

    yield 'data: {"err": "Nenhum modelo disponivel no momento. Tente novamente."}\n\n'


def _call_openai_responses(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:  # pragma: no cover
    """Non-streaming call to OpenAI Responses API. Returns (text, response_id, model)."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Study chat unavailable. Missing OPENAI_API_KEY in server environment.",
        )

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    endpoint = base_url + "/responses"
    max_output_tokens = int(os.environ.get("AI_CHAT_MAX_TOKENS", "350") or "350")
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


# Limite de tokens para o chat de estudo -- respostas curtas e rapidas
# Separado de AI_MAX_TOKENS (que vale para todo o sistema)
_AI_CHAT_MAX_TOKENS = int(os.environ.get("AI_CHAT_MAX_TOKENS", "350") or "350")


def _call_gemini(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:  # pragma: no cover
    """Non-streaming call to Google Gemini. Returns (text, response_id, model)."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    max_tokens = int(os.environ.get("AI_CHAT_MAX_TOKENS", "350") or "350")
    timeout = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30") or "30")
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.5},
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


async def _stream_gemini_sse(system_prompt: str, user_prompt: str):  # pragma: no cover
    """Async generator: yields SSE lines using Google Gemini streaming API."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        yield 'data: {"err": "Study chat unavailable: missing GEMINI_API_KEY."}\n\n'
        return
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    max_tokens = int(os.environ.get("AI_CHAT_MAX_TOKENS", "350") or "350")
    timeout = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30") or "30")
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":streamGenerateContent?key={api_key}&alt=sse"
    )
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.5},
    }
    try:
        got_delta = False
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", endpoint, json=body, headers={"Content-Type": "application/json"}) as resp:
                if resp.status_code >= 400:
                    err_bytes = await resp.aread()
                    try:
                        msg = json.loads(err_bytes).get("error", {}).get("message", f"HTTP {resp.status_code}")
                    except Exception:
                        msg = f"HTTP {resp.status_code}"
                    yield f'data: {{"err": {json.dumps(msg)}}}\n\n'
                    return
                async for line in resp.aiter_lines():
                    line = line.strip()
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
    except httpx.TimeoutException:
        yield 'data: {"err": "Gemini timeout. Tente novamente."}\n\n'
    except httpx.RequestError as exc:
        yield f'data: {{"err": {json.dumps(str(exc))}}}\n\n'


def _call_groq(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:  # pragma: no cover
    """Non-streaming call to Groq Chat Completions API. Returns (text, request_id, model)."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    max_tokens = int(os.environ.get("AI_CHAT_MAX_TOKENS", "350") or "350")
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
            "Accept": "application/json",
            "User-Agent": "groq-python/0.18.0",
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


async def _stream_groq_sse(system_prompt: str, user_prompt: str):  # pragma: no cover
    """Async streaming SSE generator for Groq Chat Completions API."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        yield 'data: {"err": "Study chat unavailable: missing GROQ_API_KEY."}\n\n'
        return
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    max_tokens = int(os.environ.get("AI_CHAT_MAX_TOKENS", "350") or "350")
    hdrs = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": "groq-python/0.18.0",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "stream": True,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", endpoint, json=body, headers=hdrs) as resp:
                if resp.status_code >= 400:
                    err_bytes = await resp.aread()
                    try:
                        msg = json.loads(err_bytes).get("error", {}).get("message", f"HTTP {resp.status_code}")
                    except Exception:
                        msg = f"HTTP {resp.status_code}"
                    yield f'data: {{"err": {json.dumps(msg)}}}\n\n'
                    return
                async for line in resp.aiter_lines():
                    line = line.strip()
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
                            yield f'data: {json.dumps({"d": token})}\n\n'
                    except (KeyError, json.JSONDecodeError):
                        continue
    except httpx.TimeoutException:
        yield 'data: {"err": "Groq timeout. Tente novamente."}\n\n'
    except httpx.RequestError as exc:
        yield f'data: {{"err": {json.dumps(str(exc))}}}\n\n'


# ---------------------------------------------------------------------------
# Anthropic Claude — _call_anthropic (sync) e _stream_anthropic_sse (async)
# ---------------------------------------------------------------------------
def _candidate_anthropic_models() -> list[str]:  # pragma: no cover
    primary = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"
    fallback_raw = os.environ.get(
        "ANTHROPIC_FALLBACK_MODELS",
        "claude-sonnet-4-6,claude-opus-4-6,claude-sonnet-4-5",
    )
    models: list[str] = [primary]
    for item in fallback_raw.split(","):
        m = item.strip()
        if m and m not in models:
            models.append(m)
    return models


def _call_anthropic(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:  # pragma: no cover
    """Non-streaming call to Anthropic Messages API. Returns (text, response_id, model)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Missing ANTHROPIC_API_KEY.")
    max_tokens = int(os.environ.get("AI_CHAT_MAX_TOKENS", "350") or "350")
    timeout = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30") or "30")
    endpoint = "https://api.anthropic.com/v1/messages"
    hdrs = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    last_detail = "unknown error"
    for model in _candidate_anthropic_models():
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=hdrs,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            text = payload["content"][0]["text"].strip()
            response_id = payload.get("id", "")
            return text, response_id, model
        except urllib.error.HTTPError as exc:
            detail = f"HTTP {exc.code}"
            try:
                err_body = json.loads(exc.read().decode("utf-8"))
                msg = (err_body.get("error") or {}).get("message", "")
                if msg:
                    detail = msg
            except Exception:
                pass
            last_detail = detail
            # 404 = model not found — try next candidate
            if exc.code == 404 or "model" in detail.lower():
                continue
            raise HTTPException(status_code=502, detail=f"Anthropic error: {detail}")
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            raise HTTPException(status_code=504, detail="Anthropic timeout.")
    raise HTTPException(status_code=502, detail=f"Anthropic: nenhum modelo disponivel. Ultimo erro: {last_detail}")


async def _stream_anthropic_sse(system_prompt: str, user_prompt: str):  # pragma: no cover
    """Async generator: yields SSE lines token-by-token using Anthropic Messages API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        yield 'data: {"err": "Study chat unavailable: missing ANTHROPIC_API_KEY."}\n\n'
        return
    max_tokens = int(os.environ.get("AI_CHAT_MAX_TOKENS", "350") or "350")
    timeout = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30") or "30")
    endpoint = "https://api.anthropic.com/v1/messages"
    hdrs = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in _candidate_anthropic_models():
            body = {
                "model": model,
                "max_tokens": max_tokens,
                "stream": True,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            got_delta = False
            try:
                async with client.stream("POST", endpoint, json=body, headers=hdrs) as resp:
                    if resp.status_code >= 400:
                        err_bytes = await resp.aread()
                        try:
                            msg = json.loads(err_bytes).get("error", {}).get("message", f"HTTP {resp.status_code}")
                        except Exception:
                            msg = f"HTTP {resp.status_code}"
                        # 404 = model not found — try next
                        if resp.status_code == 404 or "model" in msg.lower():
                            continue
                        yield f'data: {{"err": {json.dumps(msg)}}}\n\n'
                        return
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        payload_str = line[5:].strip()
                        try:
                            chunk = json.loads(payload_str)
                        except json.JSONDecodeError:
                            continue
                        ev_type = chunk.get("type", "")
                        if ev_type == "content_block_delta":
                            delta = chunk.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    got_delta = True
                                    yield f'data: {json.dumps({"d": text})}\n\n'
                        elif ev_type == "message_stop":
                            if got_delta:
                                yield f'data: {{"done": true, "model": {json.dumps(model)}}}\n\n'
                            break
            except (httpx.TimeoutException, httpx.RequestError):
                continue
            if got_delta:
                return
    yield 'data: {"err": "Anthropic: nenhum modelo Claude disponivel. Confira ANTHROPIC_API_KEY."}\n\n'


# ---------------------------------------------------------------------------
# Fallback de streaming: Anthropic → OpenAI → Groq → Gemini em runtime
# ---------------------------------------------------------------------------
async def _stream_with_fallback(system_prompt: str, user_prompt: str):  # pragma: no cover
    """
    Tenta cada provedor em ordem de prioridade: Anthropic (Claude) → OpenAI → Groq → Gemini.
    Se o primeiro evento SSE contiver {"err": ...} (quota esgotada, auth, timeout),
    abandona e tenta o proximo provedor.
    """
    providers: list[tuple[str, object]] = []
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        providers.append(("Anthropic", lambda: _stream_anthropic_sse(system_prompt, user_prompt)))

    # AI_GROQ_PRIORITY=true coloca Groq antes do OpenAI para respostas mais rápidas (~300-800ms)
    groq_priority = os.environ.get("AI_GROQ_PRIORITY", "false").strip().lower() in ("1", "true", "yes")
    openai_entry = ("OpenAI", lambda: _stream_openai_sse(system_prompt, user_prompt))
    groq_entry = ("Groq", lambda: _stream_groq_sse(system_prompt, user_prompt))

    if groq_priority:
        if os.environ.get("GROQ_API_KEY", "").strip():
            providers.append(groq_entry)
        if os.environ.get("OPENAI_API_KEY", "").strip():
            providers.append(openai_entry)
    else:
        if os.environ.get("OPENAI_API_KEY", "").strip():
            providers.append(openai_entry)
        if os.environ.get("GROQ_API_KEY", "").strip():
            providers.append(groq_entry)

    if os.environ.get("GEMINI_API_KEY", "").strip():
        providers.append(("Gemini", lambda: _stream_gemini_sse(system_prompt, user_prompt)))

    if not providers:
        yield 'data: {"err": "Nenhuma API key de IA configurada no servidor."}\n\n'
        return

    last_err = "Erro desconhecido."
    for name, factory in providers:
        gen = factory()
        try:
            first = await gen.__anext__()
        except StopAsyncIteration:
            continue

        # Verifica se o primeiro evento e um erro
        try:
            first_data = first.strip()
            if first_data.startswith("data: "):
                first_json = json.loads(first_data[6:])
                if "err" in first_json:
                    last_err = f"[{name}] {first_json['err']}"
                    await gen.aclose()
                    continue  # tenta o proximo provedor
        except (json.JSONDecodeError, KeyError):
            pass  # nao e JSON ou nao tem 'err' — pode ser um token, prossegue

        # Primeiro evento e valido: emite e continua o stream normalmente
        yield first
        async for chunk in gen:
            yield chunk
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
    """Constroi system + user prompt ENXUTO para respostas rapidas."""
    curriculum = _STAGE_CURRICULUM.get(stage, _STAGE_CURRICULUM["Mid"])

    # System prompt compacto com regras rigorosas de formatacao Java
    system_prompt = (
        "Voce e Cezi Cola — Senior Engineer, criador do jogo 404 Garage. "
        "Humano, direto, apaixonado por ensinar. Nunca se apresente como IA.\n\n"
        "DOMINIO: Responda QUALQUER pergunta de tecnologia, programacao, engenharia de software, "
        "sistemas distribuidos, arquitetura, integracao, banco de dados, redes, seguranca, "
        "estruturas de dados, algoritmos, logica e ciencia da computacao — sem restricao de nivel "
        "(desde basico ate ultra-avancado e ultra-moderno). "
        "Linguagem padrao do jogo: Java JDK 21. Se o aluno perguntar em outra linguagem "
        "ou tecnologia, responda normalmente nessa tecnologia, sem forcar Java.\n\n"
        f"NIVEL DO ALUNO: {stage} — {curriculum['foco']}\n"
        f"Foco do desafio atual: {curriculum['topicos'][:400]}\n"
        f"Tom: {curriculum['tom']}\n\n"
        "REGRAS INEGOCIAVEIS:\n"
        "1. Responda em pt-BR. Nomes de variaveis/metodos/classes em ingles.\n"
        "2. SEJA PRECISO E OBJETIVO: use quantos paragrafos forem necessarios para "
        "   responder bem. Sem rodeios, sem repeticoes. Respostas simples = curtas; "
        "   topicos complexos = completos.\n"
        "3. Se a pergunta nao pede codigo, responda em prosa direta sem bloco de codigo.\n"
        "4. Complexidade O(tempo) e O(espaco) obrigatoria em 1 linha quando houver codigo.\n\n"
        "REGRAS DE CODIGO JAVA — VIOLACAO ZERO (quando o codigo for Java):\n"
        "A. O codigo DEVE compilar sem erros no JDK 21. Teste mentalmente cada linha.\n"
        "B. INDENTACAO: 4 espacos por nivel. NUNCA use tab. Chaves no nivel correto.\n"
        "C. NUNCA truncar: proibido '// ...', '// resto do codigo', esqueletos vazios.\n"
        "D. Todo codigo tem 'public static void main(String[] args)' com exemplo executavel.\n"
        "E. Feche TODAS as chaves corretamente.\n"
        "F. Fence correto: ```java ... ``` em linha propria.\n"
        "G. Imports completos no topo. Sem imports desnecessarios.\n"
        "H. ASSINATURA EXATA: se o enunciado especificar nome de classe/metodo/tipo de retorno, "
        "   use EXATAMENTE esses nomes e tipos sem variacao."
    )

    desc_trunc = (challenge_desc[:200] + "...") if len(challenge_desc) > 200 else challenge_desc

    user_prompt = (
        f"Stage: {stage} | Regiao: {region} | Desafio: {challenge_title or 'N/A'}\n"
        f"Enunciado: {desc_trunc or 'N/A'}\n\n"
        f"Historico:\n{history_text}\n\n"
        f"Pergunta: {message}"
    )

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Fallback em runtime: Groq → OpenAI (tenta o proximo se 4xx/5xx)
# ---------------------------------------------------------------------------
def _call_with_fallback(system_prompt: str, user_prompt: str) -> tuple[str, str, str]:  # pragma: no cover
    """Tenta provedores em ordem: Groq (rapido ~300ms) → Gemini → OpenAI → Anthropic."""
    errors: list[str] = []

    # 401/403 = key invalida/revogada; 429 = quota esgotada; 5xx = erro do servidor
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

    if os.environ.get("GEMINI_API_KEY", "").strip():
        try:
            return _call_gemini(system_prompt, user_prompt)
        except HTTPException as exc:
            if exc.status_code in _RETRIABLE:
                errors.append(f"Gemini HTTP {exc.status_code}")
            else:
                raise
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Gemini erro: {exc}")

    if os.environ.get("OPENAI_API_KEY", "").strip():
        try:
            return _call_openai_responses(system_prompt, user_prompt)
        except HTTPException as exc:
            if exc.status_code in _RETRIABLE:
                errors.append(f"OpenAI HTTP {exc.status_code}")
            else:
                raise
        except Exception as exc:  # noqa: BLE001
            errors.append(f"OpenAI erro: {exc}")

    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        try:
            return _call_anthropic(system_prompt, user_prompt)
        except HTTPException as exc:
            if exc.status_code in _RETRIABLE:
                errors.append(f"Anthropic HTTP {exc.status_code}")
            else:
                raise
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Anthropic erro: {exc}")

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

    recent = req.recent_messages[-4:]  # apenas 4 mensagens — suficiente para contexto
    books = req.books[:10]
    prompt_books = [b for b in books if b.collected][:3]  # max 3 livros no prompt

    history_lines = []
    for msg in recent:
        prefix = "Aluno" if msg.role == "user" else "IA"
        compact = (msg.content or "").strip()[:120]  # truncado em 120 chars
        history_lines.append(f"{prefix}: {compact}")
    history_text = "\n".join(history_lines) if history_lines else "(sem historico)"

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

    # Fallback em runtime: Groq (rapido) → Gemini → OpenAI → Anthropic
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
async def api_study_chat_stream(req: StudyChatRequest, current_user: dict = Depends(get_current_user)):  # pragma: no cover
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

    recent = req.recent_messages[-4:]  # apenas 4 mensagens
    books  = req.books[:10]
    prompt_books = ([b for b in books if b.collected] or books)[:3]  # max 3 livros

    history_lines = []
    for msg in recent:
        prefix  = "Aluno" if msg.role == "user" else "IA"
        compact = (msg.content or "").strip()[:120]
        history_lines.append(f"{prefix}: {compact}")
    history_text = "\n".join(history_lines) or "(sem historico)"

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

    # Fallback em runtime: OpenAI → Groq → Gemini (async)
    async def _event_gen():
        async for chunk in _stream_with_fallback(system_prompt, user_prompt):
            yield chunk

    return StreamingResponse(
        _event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
