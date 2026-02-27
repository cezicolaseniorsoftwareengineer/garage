"""Test script: diagnoses the AI chat flow end-to-end.

Usage: cd Garage && python scripts/test_ia_flow.py [PORT]
Default port: 8788
"""
import sys, json, time, urllib.request, urllib.error, os

PORT = sys.argv[1] if len(sys.argv) > 1 else "8788"
BASE = f"http://127.0.0.1:{PORT}"


def http(method, path, body=None, token=None, timeout=30):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode() if body else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode()
        try:
            detail = json.loads(resp_body).get("detail", resp_body)
        except Exception:
            detail = resp_body
        raise RuntimeError(f"HTTP {e.code}: {detail[:300]}")


def http_raw(method, path, body, token, timeout=40):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode(),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode()
        try:
            detail = json.loads(resp_body).get("detail", resp_body)
        except Exception:
            detail = resp_body
        raise RuntimeError(f"HTTP {e.code}: {detail[:300]}")


print(f"\n=== DIAGNOSTICO IA - 404 Garage (http://127.0.0.1:{PORT}) ===\n")

# 1. Health
print("[1] Testando servidor...")
try:
    data = http("GET", "/health")
    print(f"    OK: {data}")
except Exception as e:
    print(f"    FALHOU: {e}")
    sys.exit(1)

# 2. Register
ts = int(time.time())
print("\n[2] Registrando usuario de teste...")
try:
    reg = http("POST", "/api/auth/register", body={
        "full_name": f"Teste IA {ts}",
        "username": f"testeIA{ts}",
        "email": f"testeIA{ts}@test.com",
        "whatsapp": "11999998888",
        "profession": "estudante",
        "password": "Teste123!",
    })
    token = reg["access_token"]
    print(f"    OK: usuario criado")
except Exception as e:
    print(f"    FALHOU: {e}")
    sys.exit(1)

# 3. Start game
print("\n[3] Iniciando jogo...")
try:
    game = http("POST", "/api/start", body={
        "player_name": "Dev IA Test",
        "gender": "male",
        "ethnicity": "white",
        "avatar_index": 0,
        "language": "Java",
    }, token=token)
    session_id = game["session_id"]
    print(f"    OK: session_id criado")
except Exception as e:
    print(f"    FALHOU: {e}")
    sys.exit(1)

# 4. Direct Python call
print("\n[4] Testando _call_with_fallback diretamente (sem HTTP)...")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(".env")
from app.api.routes.study_routes import _call_with_fallback, _candidate_models

models = _candidate_models()
print(f"    Modelos a tentar: {models}")
openai_key = os.environ.get("OPENAI_API_KEY", "")
groq_key = os.environ.get("GROQ_API_KEY", "")
gemini_key = os.environ.get("GEMINI_API_KEY", "")
print(f"    OPENAI_API_KEY: {'OK (' + openai_key[:15] + '...)' if openai_key else 'NAO CONFIGURADA'}")
print(f"    GROQ_API_KEY:   {'OK (' + groq_key[:15] + '...)' if groq_key else 'NAO CONFIGURADA'}")
print(f"    GEMINI_API_KEY: {'OK (' + gemini_key[:15] + '...)' if gemini_key else 'NAO CONFIGURADA'}")

try:
    text, rid, model = _call_with_fallback(
        "Voce e um professor de Java.",
        "O que e HashMap? Responda em 1 linha objetiva.",
    )
    print(f"    OK: model={model}, chars={len(text)}")
    print(f"    Resposta: {text[:120]}")
except Exception as e:
    print(f"    FALHOU: {type(e).__name__}: {e}")

# 5. Chat stream via HTTP
print("\n[5] Testando /api/study/chat/stream via HTTP...")
try:
    raw_sse = http_raw("POST", "/api/study/chat/stream", body={
        "session_id": session_id,
        "message": "O que e HashMap em Java? 1 linha.",
        "challenge_id": None,
        "stage": "Intern",
        "region": "Garage",
        "recent_messages": [],
        "books": [],
    }, token=token)

    lines = [l for l in raw_sse.split("\n") if l.startswith("data: ")]
    has_error = False
    has_content = False
    used_model = ""
    full_text = ""
    for line in lines:
        try:
            chunk = json.loads(line[6:])
        except Exception:
            continue
        if "err" in chunk:
            has_error = True
            print(f"    ERRO no SSE: {chunk['err']}")
        if "d" in chunk:
            has_content = True
            full_text += chunk["d"]
        if "token" in chunk:
            print(f"    AVISO: Groq enviando formato antigo 'token'")
        if "done" in chunk:
            used_model = chunk.get("model", "?")

    if not has_error and has_content:
        print(f"    OK: model={used_model}, {len(lines)} eventos SSE")
        print(f"    Resposta: {full_text[:120]}")
    elif not lines:
        print(f"    FALHOU: Nenhum evento SSE. Bruto: {raw_sse[:200]}")
    else:
        print(f"    AVISO: SSE chegou sem conteudo. Linhas: {lines[:3]}")
except Exception as e:
    print(f"    FALHOU: {e}")

print("\n=== FIM DO DIAGNOSTICO ===\n")
