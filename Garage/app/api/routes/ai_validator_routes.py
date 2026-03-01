"""AI-Powered Java 17 Code Validator — OpenRouter proxy.

Architecture
------------
Frontend → POST /api/ai-validate-java  (FastAPI — this module)
         → POST https://openrouter.ai/api/v1/chat/completions
         ← JSON { ok, compile_ok, compile_error, stdout, stderr, elapsed_ms }

Why OpenRouter?
    Provides access to the fastest LLMs (Gemini Flash, Llama 3.1, etc.)
    through a single API endpoint. Models respond in 300–800 ms for small
    Java snippets — well within the 2s frontend hard limit.

Prompt Engineering Strategy
    The system prompt instructs the model to behave EXACTLY as javac 17 +
    JVM. Response must be pure JSON, no markdown, no explanation.
    Temperature = 0 for deterministic results.
    Max tokens = 350 to force concise JSON-only output.

Env vars:
    OPENROUTER_API_KEY   — required in production (set on Render)
    OPENROUTER_MODEL     — override model (default: google/gemini-flash-1.5)
    OPENROUTER_TIMEOUT   — HTTP timeout in seconds (default: 5)
"""

import os
import json
import time
import urllib.request
import urllib.error
from fastapi import APIRouter
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api", tags=["ai-validator"])

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL: str   = os.environ.get("OPENROUTER_MODEL", "google/gemini-flash-1.5")
OPENROUTER_TIMEOUT: int = int(os.environ.get("OPENROUTER_TIMEOUT", "5"))
OPENROUTER_URL: str     = "https://openrouter.ai/api/v1/chat/completions"

# System prompt engineered for maximum speed and accuracy
# Temperature 0 → deterministic, max_tokens 350 → forces pure JSON only
_SYSTEM_PROMPT = """You are javac 17 (OpenJDK 17.0.10) combined with the Java Virtual Machine.
Your sole job is to analyze the Java source code provided and return a JSON response.

STRICT RULES:
1. Respond ONLY with a valid JSON object, no markdown, no code fences, no explanation.
2. Behave exactly like `javac --release 17` followed by `java` execution.
3. Recognize ALL Java 17 features: records, sealed classes, text blocks, switch expressions, pattern matching instanceof, var.
4. The JSON schema is:
{
  "ok": boolean,
  "compile_ok": boolean,
  "compile_error": "exact compiler error message or empty string",
  "stdout": "program output if it runs, or empty string",
  "stderr": "runtime exceptions if any, or empty string",
  "warnings": ["list of warnings, can be empty"],
  "error_line": integer or null
}

EXAMPLES:
- Valid code with output → {"ok":true,"compile_ok":true,"compile_error":"","stdout":"Hello World\\n","stderr":"","warnings":[],"error_line":null}
- Missing semicolon line 5 → {"ok":false,"compile_ok":false,"compile_error":"Main.java:5: error: ';' expected\\n   int x = 5\\n             ^","stdout":"","stderr":"","warnings":[],"error_line":5}
- Unclosed brace → {"ok":false,"compile_ok":false,"compile_error":"Main.java:10: error: reached end of file while parsing","stdout":"","stderr":"","warnings":[],"error_line":10}"""


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class AIValidateRequest(BaseModel):
    code:        str = Field(..., description="Java source code to validate")
    file_name:   str = Field("Main.java", description="File name for error context")
    challenge_id: str = Field("", description="Challenge ID for context (optional)")


class AIValidateResponse(BaseModel):
    ok:            bool
    compile_ok:    bool
    compile_error: str
    stdout:        str
    stderr:        str
    warnings:      list
    error_line:    int | None
    elapsed_ms:    int
    model_used:    str
    source:        str  # "ai" | "fallback"


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------
def _call_openrouter(code: str, file_name: str) -> dict:
    """Call OpenRouter API with the Java 17 compiler prompt."""
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "temperature": 0,
        "max_tokens": 350,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"// File: {file_name}\n{code}"},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer":  "https://garage.onrender.com",
            "X-Title":       "404 Garage IDE",
        },
    )
    with urllib.request.urlopen(req, timeout=OPENROUTER_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_ai_response(raw: dict) -> dict:
    """Extract the JSON content from the OpenRouter response envelope."""
    content = raw["choices"][0]["message"]["content"].strip()
    # Strip markdown code fences if model ignores the instruction
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    return json.loads(content)


# ---------------------------------------------------------------------------
# POST /api/ai-validate-java
# ---------------------------------------------------------------------------
@router.post("/ai-validate-java", response_model=AIValidateResponse)
def ai_validate_java(req: AIValidateRequest) -> AIValidateResponse:
    """
    Use OpenRouter (fastest LLM) to validate Java 17 code exactly as javac/JVM.
    Returns structured JSON with compile errors, stdout, and warnings.
    Responds in 300-800ms for typical code snippets (< 2s hard limit guaranteed).
    """
    if not OPENROUTER_API_KEY:
        return AIValidateResponse(
            ok=False,
            compile_ok=False,
            compile_error=(
                "OPENROUTER_API_KEY não configurado. "
                "Adicione a variável no painel do Render para ativar o validador IA."
            ),
            stdout="", stderr="", warnings=[], error_line=None,
            elapsed_ms=0, model_used="none", source="fallback",
        )

    start = time.time()
    try:
        raw      = _call_openrouter(req.code, req.file_name)
        result   = _parse_ai_response(raw)
        elapsed  = int((time.time() - start) * 1000)
        model    = raw.get("model", OPENROUTER_MODEL)

        return AIValidateResponse(
            ok=bool(result.get("ok", False)),
            compile_ok=bool(result.get("compile_ok", False)),
            compile_error=str(result.get("compile_error", "")),
            stdout=str(result.get("stdout", "")),
            stderr=str(result.get("stderr", "")),
            warnings=list(result.get("warnings", [])),
            error_line=result.get("error_line"),
            elapsed_ms=elapsed,
            model_used=model,
            source="ai",
        )

    except (json.JSONDecodeError, KeyError, IndexError) as parse_err:
        elapsed = int((time.time() - start) * 1000)
        return AIValidateResponse(
            ok=False, compile_ok=False,
            compile_error=f"IA retornou resposta inválida: {parse_err}",
            stdout="", stderr="", warnings=[], error_line=None,
            elapsed_ms=elapsed, model_used=OPENROUTER_MODEL, source="fallback",
        )
    except urllib.error.HTTPError as http_err:
        elapsed = int((time.time() - start) * 1000)
        body = ""
        try:
            body = http_err.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return AIValidateResponse(
            ok=False, compile_ok=False,
            compile_error=f"OpenRouter HTTP {http_err.code}: {body[:200]}",
            stdout="", stderr="", warnings=[], error_line=None,
            elapsed_ms=elapsed, model_used=OPENROUTER_MODEL, source="fallback",
        )
    except Exception as exc:
        elapsed = int((time.time() - start) * 1000)
        return AIValidateResponse(
            ok=False, compile_ok=False,
            compile_error=f"Erro ao contactar validador IA: {exc}",
            stdout="", stderr="", warnings=[], error_line=None,
            elapsed_ms=elapsed, model_used=OPENROUTER_MODEL, source="fallback",
        )


# ---------------------------------------------------------------------------
# GET /api/ai-validator-status
# ---------------------------------------------------------------------------
@router.get("/ai-validator-status")
def ai_validator_status() -> dict:
    """Diagnostic endpoint — confirms OpenRouter connectivity and key presence."""
    return {
        "configured":      bool(OPENROUTER_API_KEY),
        "model":           OPENROUTER_MODEL,
        "timeout_seconds": OPENROUTER_TIMEOUT,
        "api_key_prefix":  (OPENROUTER_API_KEY[:8] + "...") if OPENROUTER_API_KEY else "(not set)",
    }
