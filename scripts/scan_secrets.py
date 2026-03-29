#!/usr/bin/env python3
"""Simple repository secret scanner.

Usage: python scripts/scan_secrets.py

Scans files under the workspace for common secret patterns and prints matches.
This is intended as a local safety tool — run before committing.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE_DIRS = {'.git', '.venv', 'node_modules', '.local'}

PATTERNS = {
    'API Key-like': re.compile(r"(?i)(?:api[_-]?key|openai|openrouter|resend|asaas|groq)[=:\s]*([A-Za-z0-9_\-]{16,})"),
    'JWT secret': re.compile(r"(?i)jwt[_-]?secret|secret[_-]?key|SECRET_KEY"),
    'Password assignment': re.compile(r"(?i)password=.+"),
    'URL with creds': re.compile(r"https?://[^\s:@]+:[^\s:@]+@"),
}


def scan():
    findings = []
    for path in ROOT.rglob('*'):
        if path.is_dir():
            if path.name in IGNORE_DIRS:
                continue
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for name, pattern in PATTERNS.items():
            for m in pattern.finditer(text):
                snippet = m.group(0)
                findings.append((path.relative_to(ROOT), name, snippet.strip()[:200]))
    if findings:
        print('Potential secrets found:')
        for f in findings:
            print(f'{f[0]} :: {f[1]} :: {f[2]}')
        return 1
    print('No obvious secrets found by patterns (run manual review).')
    return 0


if __name__ == '__main__':
    sys.exit(scan())
