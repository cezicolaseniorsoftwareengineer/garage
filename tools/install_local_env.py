#!/usr/bin/env python3
"""
Instalador local: cria `.local/`, escreve política local, atualiza `.git/info/exclude` para ignorar `.local`,
e instala hooks locais `pre-commit` e `pre-push` chamando os scripts em `tools/`.

Execução: python tools/install_local_env.py
"""
import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / '.local'
GIT = ROOT / '.git'
GIT_HOOKS = GIT / 'hooks'
GIT_INFO_EXCLUDE = GIT / 'info' / 'exclude'
POLICY = LOCAL / 'cezicola_policy.yaml'

DEFAULT_POLICY = '''
model_preferences:
  - GPT-5 mini
  - GPT-4o
  - GPT-4.1
  - Claude Haiku 4.5
  - Raptor mini (Preview)
enable_sanitizer: true
sanitizer_path: tools/sanitize_output.py
usage_log: .local/cezicola_usage.log
'''

PRE_COMMIT = """#!/usr/bin/env sh
# pre-commit hook: run sanitizer on staged files
python "${PWD}/tools/sanitize_output.py"
if [ $? -ne 0 ]; then
  echo "Pre-commit sanitization failed. Commit aborted." >&2
  exit 1
fi
exit 0
"""

PRE_PUSH = """#!/usr/bin/env sh
# pre-push hook: block pushes unless ALLOW_PUSH=1 is set
if [ "${ALLOW_PUSH}" != "1" ]; then
  echo "Push blocked by local policy. To allow, set ALLOW_PUSH=1 in your environment." >&2
  exit 1
fi
exit 0
"""

def ensure_local():
    LOCAL.mkdir(exist_ok=True)
    if not POLICY.exists():
        POLICY.write_text(DEFAULT_POLICY, encoding='utf-8')
        print(f'Wrote local policy to {POLICY}')

def ensure_exclude():
    entry = '\n# local Cezi Cola files\n.local/\n'
    if GIT_INFO_EXCLUDE.exists():
        text = GIT_INFO_EXCLUDE.read_text(encoding='utf-8')
        if '.local/' not in text:
            GIT_INFO_EXCLUDE.write_text(text + entry, encoding='utf-8')
            print('Updated .git/info/exclude to ignore .local/')
    else:
        GIT_INFO_EXCLUDE.parent.mkdir(parents=True, exist_ok=True)
        GIT_INFO_EXCLUDE.write_text(entry, encoding='utf-8')
        print('Created .git/info/exclude and added .local/')

def install_hook(name: str, content: str):
    if not GIT.exists() or not GIT_HOOKS.exists():
        print('No .git/hooks directory found; are you in a git repo?')
        return
    hook_path = GIT_HOOKS / name
    hook_path.write_text(content, encoding='utf-8')
    # try to set executable bit
    try:
        st = os.stat(str(hook_path))
        os.chmod(str(hook_path), st.st_mode | stat.S_IEXEC)
    except Exception:
        pass
    print(f'Installed hook: {hook_path}')

def main():
    ensure_local()
    ensure_exclude()
    install_hook('pre-commit', PRE_COMMIT)
    install_hook('pre-push', PRE_PUSH)
    print('Local environment set up. Hooks installed. .local is ignored locally.')

if __name__ == '__main__':
    main()
