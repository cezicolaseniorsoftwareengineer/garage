#!/usr/bin/env python3
"""
Sanitizador simples para detectar emojis e símbolos expressivos.
Uso: chamado pelo hook de pre-commit para validar arquivos staged.
"""
import re
import sys
from pathlib import Path

# Cobertura razoável de blocos de emoji/símbolos Unicode comuns
EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001F5FF]"  # Misc Symbols and Pictographs
    "|[\U0001F600-\U0001F64F]"  # Emoticons
    "|[\U0001F680-\U0001F6FF]"  # Transport and Map
    "|[\U0001F700-\U0001F77F]"  # Alchemical Symbols
    "|[\U00002600-\U000026FF]"  # Misc symbols
    "|[\U00002700-\U000027BF]"  # Dingbats
    , flags=re.UNICODE)

def check_text(text: str):
    matches = EMOJI_PATTERN.search(text)
    return matches is None

def files_to_check(paths):
    for p in paths:
        path = Path(p)
        if path.is_file():
            try:
                text = path.read_text(encoding='utf-8')
            except Exception:
                continue
            if not check_text(text):
                return False, path
    return True, None

def main():
    # If run without args, check staged files via git
    args = sys.argv[1:]
    if not args:
        # fallback: read list of files from git staged
        try:
            import subprocess
            res = subprocess.run(['git','diff','--name-only','--cached'], capture_output=True, text=True)
            files = [l.strip() for l in res.stdout.splitlines() if l.strip()]
        except Exception:
            files = []
    else:
        files = args

    ok, bad = files_to_check(files)
    if not ok:
        print(f"Sanitization failed: prohibited symbol found in {bad}")
        print("Remove emojis/symbols or run the sanitizer with --force to bypass (not recommended).")
        sys.exit(1)
    print("Sanitization passed: no prohibited symbols detected.")
    sys.exit(0)

if __name__ == '__main__':
    main()
