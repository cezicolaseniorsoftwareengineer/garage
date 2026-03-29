#!/usr/bin/env python3
"""
Scan only git-tracked files for common secret patterns and write a safe report.
Non-destructive: does not modify any file, only reads tracked files and writes a report.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "secret_audit_tracked.txt"

PATTERNS = [
    (re.compile(r"\bJWT_SECRET\b", re.I), "JWT secret"),
    (re.compile(r"\bSECRET_KEY\b", re.I), "JWT/SECRET key"),
    (re.compile(r"(?i)api[_-]?key\b"), "API key label"),
    (re.compile(r"OPENAI|OPENROUTER|RESEND|ASAAS|SENTRY|SLACK|TWILIO"), "Provider key"),
    (re.compile(r"PASSWORD\s*=\s*.+"), "Password assignment"),
    (re.compile(r"https?://[^\s@]+@"), "URL with embedded creds"),
]


def get_tracked_files():
    p = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("git ls-files failed: " + p.stderr.strip())
    return [Path(p).resolve() for p in p.stdout.splitlines() if p]


def is_text_file(path: Path):
    try:
        content = path.read_bytes()
        # crude check: if contains NUL byte, treat as binary
        return b"\x00" not in content
    except Exception:
        return False


def scan_file(path: Path):
    findings = []
    try:
        text = path.read_text(errors="replace")
    except Exception:
        return findings
    for rx, label in PATTERNS:
        for m in rx.finditer(text):
            # capture small context without exposing full secret
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 20)
            snippet = text[start:end].replace("\n", " ")
            findings.append((label, snippet.strip()))
    return findings


def main():
    tracked = get_tracked_files()
    out_lines = []
    out_lines.append("Secret audit (tracked files)\n")
    for f in tracked:
        # skip vendored, caches, binaries heuristically
        if "__pycache__" in str(f) or f.suffix in {".pyc", ".pkl", ".db", ".sqlite"}:
            continue
        if not f.exists():
            continue
        if not is_text_file(f):
            continue
        findings = scan_file(f)
        if findings:
            out_lines.append(f"File: {f.relative_to(ROOT)}")
            for label, snippet in findings:
                out_lines.append(f" - {label}: ...{snippet}...")
            out_lines.append("")

    OUT.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"Audit written to: {OUT}")


if __name__ == "__main__":
    main()
