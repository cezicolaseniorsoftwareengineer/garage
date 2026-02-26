"""Tests for study_routes: cache, _build_prompts, _stream_with_fallback."""
import os, sys, json

# Remove all AI keys to test fallback behavior
for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(k, None)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.api.routes.study_routes import (
    _cache_key, _cache_get, _cache_set, _RESPONSE_CACHE,
    _build_prompts, _stream_with_fallback, _call_with_fallback,
    _STAGE_GUIDANCE, _STAGE_CURRICULUM,
)

PASS = "[PASS]"
FAIL = "[FAIL]"

errors = []

# ── 1. Imports ─────────────────────────────────────────────────────────────
print(f"{PASS} Todos os simbolos importados")
print(f"{PASS} Stages configurados: {list(_STAGE_GUIDANCE.keys())}")

# ── 2. Cache miss ──────────────────────────────────────────────────────────
k = _cache_key("ch-001", "o que e HashMap?")
if _cache_get(k) is None:
    print(f"{PASS} Cache miss funciona")
else:
    print(f"{FAIL} Cache miss invalido"); errors.append("cache-miss")

# ── 3. Cache set + hit ─────────────────────────────────────────────────────
_cache_set(k, "HashMap e uma estrutura de dados chave-valor.")
result = _cache_get(k)
if result == "HashMap e uma estrutura de dados chave-valor.":
    print(f"{PASS} Cache hit funciona")
else:
    print(f"{FAIL} Cache hit retornou: {result}"); errors.append("cache-hit")

# ── 4. Normalizacao de chave (case-insensitive + trim) ─────────────────────
k2 = _cache_key("ch-001", "  O QUE E HASHMAP?  ")
if k2 == k:
    print(f"{PASS} Normalizacao de chave (case+trim) funciona")
else:
    print(f"{FAIL} Chaves deveriam ser iguais: {k} x {k2}"); errors.append("cache-normalize")

# ── 5. Isolamento por challenge_id ─────────────────────────────────────────
k3 = _cache_key("ch-002", "o que e HashMap?")
if k3 != k:
    print(f"{PASS} Isolamento por challenge_id funciona")
else:
    print(f"{FAIL} Chaves deveriam ser diferentes"); errors.append("cache-isolamento")

# ── 6. _build_prompts para todos os 6 stages ──────────────────────────────
# Cada stage tem formato de resposta diferente
_FORMAT_MARKERS = {
    "Intern":    "TRACE MANUAL",
    "Junior":    "TRACE MANUAL",
    "Mid":       "INVARIANTE",
    "Senior":    "INVARIANTE",
    "Staff":     "CONTEXTO",
    "Principal": "CONTEXTO",
}
for stage in _STAGE_GUIDANCE.keys():
    sys_p, usr_p = _build_prompts(
        stage, "Garage", "Desafio Teste", "Implemente um HashMap.",
        "- Sem historico.", "(sem livros)", "Como funciona ArrayList?"
    )
    ok = True
    if "Professor CeziCola" not in sys_p:
        print(f"{FAIL} [{stage}] system_prompt sem 'Professor CeziCola'"); errors.append(f"build-{stage}-sys"); ok = False
    if stage not in sys_p:
        print(f"{FAIL} [{stage}] system_prompt sem stage"); errors.append(f"build-{stage}-stage"); ok = False
    if "ArrayList" not in usr_p:
        print(f"{FAIL} [{stage}] user_prompt sem mensagem"); errors.append(f"build-{stage}-msg"); ok = False
    marker = _FORMAT_MARKERS[stage]
    if marker not in usr_p:
        print(f"{FAIL} [{stage}] user_prompt sem marcador '{marker}'"); errors.append(f"build-{stage}-fmt"); ok = False
    if ok:
        diretriz = _STAGE_CURRICULUM[stage]["foco"][:35]
        print(f"{PASS} _build_prompts [{stage}] OK — foco: '{diretriz}...'")

# ── 7. _stream_with_fallback sem nenhuma API key ───────────────────────────
events = list(_stream_with_fallback("system", "user"))
if len(events) == 1:
    try:
        payload = json.loads(events[0].replace("data: ", "").strip())
        if "err" in payload:
            print(f"{PASS} _stream_with_fallback sem keys retorna erro gracioso: '{payload['err'][:50]}'")
        else:
            print(f"{FAIL} Esperava 'err', recebeu: {payload}"); errors.append("fallback-nokey")
    except json.JSONDecodeError as e:
        print(f"{FAIL} SSE event nao e JSON valido: {events[0]} | {e}"); errors.append("fallback-json")
else:
    print(f"{FAIL} Esperava 1 evento, recebeu {len(events)}"); errors.append("fallback-count")

# ── 8. _stream_with_fallback com provider que emite erro ───────────────────
def _fake_error_gen(sys_p, usr_p):
    yield 'data: {"err": "quota esgotada"}\n\n'

def _fake_ok_gen(sys_p, usr_p):
    yield 'data: {"token": "ola"}\n\n'
    yield 'data: {"done": true}\n\n'

# Simula: primeiro provider falha, segundo funciona
os.environ["GEMINI_API_KEY"] = "fake_gemini"
os.environ["GROQ_API_KEY"] = "fake_groq"

from app.api.routes import study_routes as sr
_orig_gemini = sr._stream_gemini_sse
_orig_groq   = sr._stream_groq_sse
sr._stream_gemini_sse = _fake_error_gen
sr._stream_groq_sse   = _fake_ok_gen

events2 = list(sr._stream_with_fallback("sys", "usr"))
sr._stream_gemini_sse = _orig_gemini
sr._stream_groq_sse   = _orig_groq
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)

ok_events = [e for e in events2 if '"token"' in e or '"done"' in e]
err_events = [e for e in events2 if '"err"' in e]
if ok_events and not err_events:
    print(f"{PASS} Fallback Gemini(erro)->Groq(ok): recebeu tokens do Groq corretamente")
else:
    print(f"{FAIL} Fallback nao funcionou. events: {events2}"); errors.append("fallback-runtime")

# ── 9. _call_with_fallback: 403 (key revogada) faz fallback ───────────────
from fastapi import HTTPException as _HTTPException
from app.api.routes import study_routes as sr2

_orig_gemini_call = sr2._call_gemini
_orig_groq_call   = sr2._call_groq

def _fake_gemini_403(*_): raise _HTTPException(status_code=502, detail="Gemini error: HTTP 403")
def _fake_groq_403(*_):   raise _HTTPException(status_code=502, detail="Groq error: HTTP 403")

os.environ["GEMINI_API_KEY"] = "fake_gemini"
os.environ["GROQ_API_KEY"]   = "fake_groq"
sr2._call_gemini = _fake_gemini_403
sr2._call_groq   = _fake_groq_403

try:
    sr2._call_with_fallback("sys", "usr")
    print(f"{FAIL} Deveria ter levantado HTTPException 503"); errors.append("fallback-403")
except _HTTPException as exc:
    if exc.status_code == 503 and "HTTP 502" in exc.detail:
        print(f"{PASS} _call_with_fallback: 403/502 em ambos resulta em 503 gracioso")
    else:
        print(f"{FAIL} status={exc.status_code} detail={exc.detail}"); errors.append("fallback-403-code")
finally:
    sr2._call_gemini = _orig_gemini_call
    sr2._call_groq   = _orig_groq_call
    os.environ.pop("GEMINI_API_KEY", None)
    os.environ.pop("GROQ_API_KEY", None)

# ── Resultado final ────────────────────────────────────────────────────────
print()
total = 8 + len(_STAGE_GUIDANCE)  # 8 tests + 6 stages
if errors:
    print(f"=== {len(errors)} TESTE(S) FALHARAM: {errors} ===")
    sys.exit(1)
else:
    print(f"=== TODOS OS {total} TESTES PASSARAM ===")
