"""Testa as chaves de API do OpenAI e Groq configuradas no .env."""
import os, sys, json, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

openai_key = os.environ.get("OPENAI_API_KEY", "")
groq_key   = os.environ.get("GROQ_API_KEY", "")
model      = os.environ.get("OPENAI_MODEL", "gpt-4.1")
groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

def mask(k):
    return (k[:12] + "..." + k[-4:]) if len(k) > 16 else ("(vazio)")

print("=== Configuracao atual ===")
print(f"OPENAI_API_KEY : {mask(openai_key)}")
print(f"OPENAI_MODEL   : {model}")
print(f"GROQ_API_KEY   : {mask(groq_key)}")
print(f"GROQ_MODEL     : {groq_model}")
print()

# --- Testa OpenAI ---
print("== Testando OpenAI ==")
t0 = time.time()
req = urllib.request.Request(
    "https://api.openai.com/v1/responses",
    data=json.dumps({
        "model": model,
        "max_output_tokens": 50,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "Diga apenas: OpenAI OK"}]}],
    }).encode(),
    headers={"Authorization": "Bearer " + openai_key, "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
        text = data["output"][0]["content"][0].get("text", "?")
        used_model = data.get("model", "?")
        print(f"OK em {time.time()-t0:.1f}s | model={used_model} | resposta: {text.strip()[:60]}")
except urllib.error.HTTPError as e:
    err = json.loads(e.read()).get("error", {})
    print(f"ERRO HTTP {e.code}: {err.get('message', '?')}")
except Exception as e:
    print(f"ERRO: {type(e).__name__}: {e}")

print()

# --- Testa Groq ---
print("== Testando Groq ==")
t0 = time.time()
req2 = urllib.request.Request(
    "https://api.groq.com/openai/v1/chat/completions",
    data=json.dumps({
        "model": groq_model,
        "max_tokens": 50,
        "messages": [{"role": "user", "content": "Diga apenas: Groq OK"}],
    }).encode(),
    headers={"Authorization": "Bearer " + groq_key, "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req2, timeout=20) as r:
        data = json.loads(r.read())
        text = data["choices"][0]["message"]["content"]
        used_model = data.get("model", "?")
        print(f"OK em {time.time()-t0:.1f}s | model={used_model} | resposta: {text.strip()[:60]}")
except urllib.error.HTTPError as e:
    raw = e.read().decode()
    try:
        err = json.loads(raw).get("error", {})
        print(f"ERRO HTTP {e.code}: {err.get('message', raw[:200])}")
    except Exception:
        print(f"ERRO HTTP {e.code}: {raw[:300]}")
except Exception as e:
    print(f"ERRO: {type(e).__name__}: {e}")

print()

# --- Testa o fallback do sistema ---
print("== Testando _call_with_fallback (ordem: OpenAI -> Groq) ==")
from app.api.routes.study_routes import _call_with_fallback, _candidate_models
print(f"Modelos OpenAI configurados: {_candidate_models()}")
t0 = time.time()
try:
    text, rid, used_model = _call_with_fallback(
        "Voce e um professor de Java.",
        "O que e HashMap? Responda em 1 linha.",
    )
    print(f"OK em {time.time()-t0:.1f}s | provider={used_model} | chars={len(text)}")
    print(f"Resposta: {text[:120]}")
except Exception as e:
    print(f"ERRO: {type(e).__name__}: {e}")
