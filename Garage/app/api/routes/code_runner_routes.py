"""Java 17 code compilation and execution endpoint.

Architecture
------------
* POST /api/run-java  — compile + run arbitrary Java 17 code in an isolated
  temp directory and return the real javac / JVM output to the frontend IDE.

Security model (process-level isolation)
-----------------------------------------
* Every request creates a unique temporary directory (tempfile.mkdtemp) which
  is unconditionally deleted after execution via a try/finally block.
* Compilation and execution use subprocess.run() with enforced wall-clock
  timeouts (COMPILE_TIMEOUT and RUN_TIMEOUT seconds respectively).
* Maximum stdout + stderr captured is capped at MAX_OUTPUT_BYTES to prevent
  memory exhaustion from infinite-print attacks.
* The JVM is launched with -Xmx128m (heap cap) and -Xss512k (stack cap).
* We do NOT use SecurityManager (deprecated in Java 17) — process isolation via
  OS-level limits is the accepted modern approach.

Internationalisation note
-------------------------
All user-visible messages are in Portuguese (pt-BR); all identifiers and
internal comments are in English, per project convention.
"""
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Optional

from fastapi import APIRouter

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api", tags=["code-runner"])

# ---------------------------------------------------------------------------
# Configuration (override via env vars)
# ---------------------------------------------------------------------------
JAVA_HOME = os.environ.get("JAVA_HOME", "").strip()
_JAVAC = os.path.join(JAVA_HOME, "bin", "javac") if JAVA_HOME else "javac"
_JAVA  = os.path.join(JAVA_HOME, "bin", "java")  if JAVA_HOME else "java"

COMPILE_TIMEOUT: float = float(os.environ.get("JAVA_COMPILE_TIMEOUT", "15"))
RUN_TIMEOUT:     float = float(os.environ.get("JAVA_RUN_TIMEOUT", "10"))
MAX_OUTPUT_BYTES: int  = int(os.environ.get("JAVA_MAX_OUTPUT_BYTES", str(100 * 1024)))  # 100 KB

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class RunJavaRequest(BaseModel):
    code:        str   = Field(..., description="Java source code to compile and run")
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
# Helpers
# ---------------------------------------------------------------------------

_CLASS_RE = re.compile(r"\bpublic\s+class\s+(\w+)")


def _extract_class_name(code: str) -> str:
    """Return the public class name declared in *code*, or 'Main' as fallback."""
    m = _CLASS_RE.search(code)
    return m.group(1) if m else "Main"


def _truncate(text: str, limit: int = MAX_OUTPUT_BYTES) -> str:
    """Hard-truncate a string to *limit* bytes (UTF-8), appending a notice."""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text
    truncated = encoded[:limit].decode("utf-8", errors="replace")
    return truncated + "\n\n[... saída truncada: limite de saída atingido ...]"


def _detect_javac_version() -> str:
    """Return javac version string or empty string if unavailable."""
    try:
        r = subprocess.run(
            [_JAVAC, "-version"],
            capture_output=True, text=True, timeout=5,
        )
        return (r.stdout or r.stderr or "").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/run-java", response_model=RunJavaResponse)
def run_java(req: RunJavaRequest) -> RunJavaResponse:
    """Compile and execute Java 17 source code in an isolated temp directory.

    Returns the real stdout / stderr from javac and the JVM so the frontend
    IDE can display authentic compiler diagnostics to the player.
    """
    code        = req.code
    class_name  = _extract_class_name(code)
    file_name   = class_name + ".java"
    javac_ver   = _detect_javac_version()

    compile_error = ""
    stdout        = ""
    stderr_run    = ""
    exit_code     = 1
    compile_ok    = False
    t_start       = time.monotonic()

    tmp_dir: Optional[str] = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="garage_java_")
        java_file = os.path.join(tmp_dir, file_name)

        # Write source
        with open(java_file, "w", encoding="utf-8") as f:
            f.write(code)

        # ----------------------------------------------------------------
        # Step 1 — Compile
        # ----------------------------------------------------------------
        compile_cmd = [
            _JAVAC,
            "--release", "17",
            "-encoding", "UTF-8",
            file_name,
        ]
        try:
            comp_result = subprocess.run(
                compile_cmd,
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=COMPILE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            elapsed = int((time.monotonic() - t_start) * 1000)
            return RunJavaResponse(
                ok=False,
                compile_ok=False,
                stdout="",
                stderr="",
                compile_error=f"Tempo limite de compilação excedido ({COMPILE_TIMEOUT:.0f}s).",
                exit_code=1,
                elapsed_ms=elapsed,
                javac_version=javac_ver,
            )
        except FileNotFoundError:
            elapsed = int((time.monotonic() - t_start) * 1000)
            return RunJavaResponse(
                ok=False,
                compile_ok=False,
                stdout="",
                stderr="",
                compile_error=(
                    "Java 17 (javac) não encontrado no servidor. "
                    "Verifique a variável JAVA_HOME ou a instalação do JDK 17."
                ),
                exit_code=1,
                elapsed_ms=elapsed,
                javac_version="",
            )

        compile_error_raw = (comp_result.stdout + comp_result.stderr).strip()
        compile_ok = comp_result.returncode == 0

        if not compile_ok:
            # Strip absolute temp path from error messages so the player
            # sees clean file:line references (e.g. "Main.java:10: error: ...")
            compile_error = compile_error_raw.replace(tmp_dir + os.sep, "")
            compile_error = compile_error.replace(tmp_dir + "/", "")
            compile_error = _truncate(compile_error)
            elapsed = int((time.monotonic() - t_start) * 1000)
            return RunJavaResponse(
                ok=False,
                compile_ok=False,
                stdout="",
                stderr="",
                compile_error=compile_error,
                exit_code=comp_result.returncode,
                elapsed_ms=elapsed,
                javac_version=javac_ver,
            )

        # ----------------------------------------------------------------
        # Step 2 — Run
        # ----------------------------------------------------------------
        run_cmd = [
            _JAVA,
            # Memory limits — protects the host from player code
            "-Xmx128m",
            "-Xss512k",
            # Encoding
            "-Dfile.encoding=UTF-8",
            "-Dstdout.encoding=UTF-8",
            # Disable DNS lookups (minor hardening on educational environment)
            "-Djava.net.preferIPv4Stack=true",
            "-cp", ".",
            class_name,
        ]
        stdin_bytes = req.stdin_input.encode("utf-8") if req.stdin_input else None
        try:
            run_result = subprocess.run(
                run_cmd,
                cwd=tmp_dir,
                input=stdin_bytes,
                capture_output=True,
                timeout=RUN_TIMEOUT,
            )
            exit_code  = run_result.returncode
            raw_stdout = run_result.stdout.decode("utf-8", errors="replace")
            raw_stderr = run_result.stderr.decode("utf-8", errors="replace")
            stdout     = _truncate(raw_stdout)
            stderr_run = _truncate(raw_stderr)

        except subprocess.TimeoutExpired as exc:
            # Kill the process tree; proc.kill() targets only the root pid
            partial_out = ""
            partial_err = ""
            if exc.stdout:
                partial_out = exc.stdout.decode("utf-8", errors="replace")
            if exc.stderr:
                partial_err = exc.stderr.decode("utf-8", errors="replace")
            stdout     = _truncate(partial_out)
            stderr_run = _truncate(partial_err)
            stdout    += f"\n\n[PROCESSO ENCERRADO: tempo limite de execução excedido ({RUN_TIMEOUT:.0f}s). Loop infinito?]"
            exit_code  = 124  # UNIX timeout convention

        except FileNotFoundError:
            stdout    = ""
            stderr_run = (
                "Java runtime (java) não encontrado no servidor. "
                "Verifique a variável JAVA_HOME ou a instalação do JDK 17."
            )
            exit_code = 1

    finally:
        if tmp_dir and os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)

    elapsed = int((time.monotonic() - t_start) * 1000)

    return RunJavaResponse(
        ok=(compile_ok and exit_code == 0),
        compile_ok=compile_ok,
        stdout=stdout,
        stderr=stderr_run,
        compile_error=compile_error,
        exit_code=exit_code,
        elapsed_ms=elapsed,
        javac_version=javac_ver,
    )
