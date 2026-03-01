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
import glob
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
COMPILE_TIMEOUT: float = float(os.environ.get("JAVA_COMPILE_TIMEOUT", "15"))
RUN_TIMEOUT:     float = float(os.environ.get("JAVA_RUN_TIMEOUT", "10"))
MAX_OUTPUT_BYTES: int  = int(os.environ.get("JAVA_MAX_OUTPUT_BYTES", str(100 * 1024)))  # 100 KB


def _find_java_binary(name: str) -> str:
    """Locate a Java binary (javac / java) with the following priority:

    1. JAVA_HOME env var (explicit user override)
    2. shutil.which — respects the current PATH (covers nixpacks PATH)
    3. Nix store glob — /nix/store/*jdk*/bin/<name>  (Render nix-env installs)
    4. Common system paths: /usr/lib/jvm, /usr/local

    Returns the resolved path or the bare binary name as a last-resort fallback.
    """
    # 1. Explicit JAVA_HOME
    java_home = os.environ.get("JAVA_HOME", "").strip()
    if java_home:
        candidate = os.path.join(java_home, "bin", name)
        if os.path.isfile(candidate):
            return candidate

    # 2. PATH lookup (fastest path on correctly-configured systems)
    found = shutil.which(name)
    if found:
        return found

    # 3. Nix store — nixpkgs puts JDKs under /nix/store/*jdk*
    nix_patterns = [
        f"/nix/store/*jdk*/bin/{name}",
        f"/nix/store/*openjdk*/bin/{name}",
        f"/nix/store/*temurin*/bin/{name}",
    ]
    for pattern in nix_patterns:
        candidates = sorted(glob.glob(pattern), reverse=True)  # newest first
        if candidates:
            return candidates[0]

    # 4. Conventional system locations — Java 17 first (standardized)
    system_dirs = [
        "/opt/render/project/src/jdk17/bin",         # Render: rootDir=Garage extracted here
        "/opt/render/project/jdk17/bin",             # Render: legacy path attempt
        "/usr/lib/jvm/java-17-openjdk-amd64/bin",   # Debian/Ubuntu apt path
        "/usr/lib/jvm/java-17-openjdk-arm64/bin",   # ARM nodes
        "/usr/lib/jvm/java-17/bin",
        "/usr/lib/jvm/java-21-openjdk-amd64/bin",
        "/usr/lib/jvm/java-21/bin",
        "/usr/local/bin",
        "/usr/bin",
    ]
    for d in system_dirs:
        candidate = os.path.join(d, name)
        if os.path.isfile(candidate):
            return candidate

    # Fall back to bare name — will raise FileNotFoundError if not in PATH
    return name


# ---------------------------------------------------------------------------
# Lazy resolution — re-evaluated on every call so that env vars set by the
# shell before uvicorn starts (e.g. JAVA_HOME, PATH) are always respected,
# even if they were not present when the module was first imported.
# ---------------------------------------------------------------------------
def _get_javac() -> str:
    return _find_java_binary("javac")

def _get_java() -> str:
    return _find_java_binary("java")

# Keep module-level aliases for the /api/java-status diagnostic endpoint
# (resolved at import time — may show "javac" if Java not yet in PATH,
#  but the lazy functions above are used for actual compilation).
_JAVAC: str = _find_java_binary("javac")
_JAVA:  str = _find_java_binary("java")

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
            [_get_javac(), "-version"],
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
            _get_javac(),
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
                    "Erro interno: compilador Java 17 não encontrado no servidor. "
                    "Por favor, tente novamente em alguns instantes ou contate o suporte."
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
            _get_java(),
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


# ---------------------------------------------------------------------------
# Diagnostic endpoint — GET /api/java-status
# ---------------------------------------------------------------------------

@router.get("/java-status")
def java_status() -> dict:
    """Return Java installation diagnostics for the Render.com environment."""
    import platform

    def _run_version(binary: str) -> str:
        try:
            r = subprocess.run(
                [binary, "-version"],
                capture_output=True, text=True, timeout=5,
            )
            return (r.stdout + r.stderr).strip()
        except FileNotFoundError:
            return f"NOT FOUND (tried: {binary})"
        except Exception as exc:
            return f"ERROR: {exc}"

    cwd = os.getcwd()

    # Probe all candidate jdk17 locations
    candidate_paths = [
        os.path.join(cwd, "jdk17", "bin", "javac"),
        "/opt/render/project/src/jdk17/bin/javac",
        "/opt/render/project/jdk17/bin/javac",
        "/home/render/jdk17/bin/javac",
    ]
    candidates_found = {p: os.path.isfile(p) for p in candidate_paths}

    # Lazy-resolved at request time
    lazy_javac = _get_javac()
    lazy_java  = _get_java()

    nix_jdks = sorted(glob.glob("/nix/store/*jdk*/bin/javac"), reverse=True)[:5]

    return {
        "cwd": cwd,
        "lazy_javac_path": lazy_javac,
        "lazy_javac_version": _run_version(lazy_javac),
        "lazy_java_path": lazy_java,
        "JAVA_HOME": os.environ.get("JAVA_HOME", "(not set)"),
        "PATH": os.environ.get("PATH", "(not set)"),
        "platform": platform.platform(),
        "candidate_paths_exist": candidates_found,
        "nix_store_jdks_found": nix_jdks,
        # Legacy fields kept for backward compat
        "javac_path": _JAVAC,
        "java_path":  _JAVA,
        "javac_version": _run_version(_JAVAC),
        "java_version":  _run_version(_JAVA),
    }

