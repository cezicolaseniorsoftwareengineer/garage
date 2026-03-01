"""Java 17 code-runner proxy.

Architecture (new)
------------------
Python is the game engine. Java compilation runs on a dedicated Spring Boot
microservice (garage-java-runner).  This module is a THIN HTTP PROXY:

    Frontend → POST /api/run-java (Python FastAPI)
             → POST <JAVA_RUNNER_URL>/run-java (Spring Boot / Java 17)
             ← JSON response forwarded transparently

Why a separate Java service?
    Render.com Python services use Heroku buildpacks — no way to install
    a persistent JDK. The Spring Boot service uses runtime:docker with
    eclipse-temurin:17-jdk, so javac is ALWAYS present.

Env vars consumed by this module:
    JAVA_RUNNER_URL    URL of the garage-java-runner service (required in prod).
    JAVA_RUNNER_SECRET Shared secret forwarded as X-Runner-Secret header.
    JAVA_RUNNER_TIMEOUT_SECONDS  HTTP timeout for calls to the Java service (default 30).
"""

import os
import urllib.request
import urllib.error
import json
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api", tags=["code-runner"])

# ---------------------------------------------------------------------------
# Configuration — set via Render environment variables
# ---------------------------------------------------------------------------
JAVA_RUNNER_URL: str     = os.environ.get("JAVA_RUNNER_URL", "").rstrip("/")
JAVA_RUNNER_SECRET: str  = os.environ.get("JAVA_RUNNER_SECRET", "")
JAVA_RUNNER_TIMEOUT: int = int(os.environ.get("JAVA_RUNNER_TIMEOUT_SECONDS", "30"))

# ---------------------------------------------------------------------------
# Request / Response schemas (unchanged — frontend contract preserved)
# ---------------------------------------------------------------------------

class RunJavaRequest(BaseModel):
    code:        str           = Field(..., description="Java source code to compile and run")
    stdin_input: Optional[str] = Field(None, description="Optional stdin to pipe to the program")


class RunJavaResponse(BaseModel):
    ok:            bool
    compile_ok:    bool
    stdout:        str
    stderr:        str
    compile_error: str
    exit_code:     int
    elapsed_ms:    int
    javac_version: str


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _call_java_runner(code: str, stdin_input: Optional[str]) -> dict:
    """Forward a compile+run request to the garage-java-runner Spring Boot service."""
    url = JAVA_RUNNER_URL + "/run-java"
    payload = json.dumps({
        "code": code,
        "stdinInput": stdin_input or "",
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Runner-Secret": JAVA_RUNNER_SECRET,
        },
    )
    with urllib.request.urlopen(req, timeout=JAVA_RUNNER_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# POST /api/run-java
# ---------------------------------------------------------------------------

@router.post("/run-java", response_model=RunJavaResponse)
def run_java(req: RunJavaRequest) -> RunJavaResponse:
    """Proxy to the garage-java-runner Spring Boot microservice.

    All compilation and execution happens inside an eclipse-temurin:17-jdk
    Docker container — javac is always available there.
    """
    if not JAVA_RUNNER_URL:
        return RunJavaResponse(
            ok=False,
            compile_ok=False,
            stdout="",
            stderr="",
            compile_error=(
                "Serviço de compilação Java não configurado. "
                "Configure a variável de ambiente JAVA_RUNNER_URL no painel do Render."
            ),
            exit_code=1,
            elapsed_ms=0,
            javac_version="",
        )

    try:
        data = _call_java_runner(req.code, req.stdin_input)
        # Spring Boot returns camelCase → normalize to snake_case for Pydantic
        return RunJavaResponse(
            ok=data.get("ok", False),
            compile_ok=data.get("compileOk", False),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            compile_error=data.get("compileError", ""),
            exit_code=data.get("exitCode", 1),
            elapsed_ms=int(data.get("elapsedMs", 0)),
            javac_version=data.get("javacVersion", ""),
        )
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return RunJavaResponse(
            ok=False, compile_ok=False, stdout="", stderr="",
            compile_error=f"Erro HTTP {exc.code} ao contactar o compilador Java: {body}",
            exit_code=1, elapsed_ms=0, javac_version="",
        )
    except Exception as exc:
        return RunJavaResponse(
            ok=False, compile_ok=False, stdout="", stderr="",
            compile_error=f"Erro ao contactar o serviço de compilação Java: {exc}",
            exit_code=1, elapsed_ms=0, javac_version="",
        )


# ---------------------------------------------------------------------------
# GET /api/java-status
# ---------------------------------------------------------------------------

@router.get("/java-status")
def java_status() -> dict:
    """Diagnostic endpoint — checks connectivity to the Java runner service."""
    if not JAVA_RUNNER_URL:
        return {
            "configured": False,
            "JAVA_RUNNER_URL": "(not set)",
            "error": "JAVA_RUNNER_URL environment variable is not set",
        }
    try:
        req = urllib.request.Request(
            JAVA_RUNNER_URL + "/health",
            method="GET",
            headers={"X-Runner-Secret": JAVA_RUNNER_SECRET},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {
            "configured": True,
            "JAVA_RUNNER_URL": JAVA_RUNNER_URL,
            "service_status": data.get("status"),
            "javac_version": data.get("javac_version"),
            "java_home": data.get("java_home"),
        }
    except Exception as exc:
        return {
            "configured": True,
            "JAVA_RUNNER_URL": JAVA_RUNNER_URL,
            "error": str(exc),
        }

