"""
Audit ALL scale-step COLA codes in game.js — compile + run with javac 17.

Strategy:
  1. Find SCALE_MISSIONS block in game.js.
  2. For every step that has helpText with a COLA marker, extract the Java code.
  3. Infer fileName from "public class ClassName" inside the code.
  4. Write to temp file, compile with javac 17, run with java.
  5. Report ALL results: OK / COMPILE_ERR / RUNTIME_ERR.
"""
import re
import os
import subprocess
import tempfile
import shutil

GAME_JS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'game.js')
)

with open(GAME_JS, encoding='utf-8') as f:
    src = f.read()


def unescape_js(s: str) -> str:
    return (s
        .replace("\\'", "'")
        .replace('\\"', '"')
        .replace('\\n', '\n')
        .replace('\\t', '\t')
        .replace('\\r', '\r')
        .replace('\\\\', '\\'))


def read_js_string(text: str, start: int):
    """Read a JS single-quoted or double-quoted string from position start (the opening quote)."""
    quote = text[start]
    i = start + 1
    buf = []
    while i < len(text):
        c = text[i]
        if c == '\\' and i + 1 < len(text):
            buf.append(c)
            buf.append(text[i + 1])
            i += 2
        elif c == quote:
            return ''.join(buf), i + 1
        else:
            buf.append(c)
            i += 1
    return ''.join(buf), i


def extract_cola_from_helptext(help_text: str):
    """Extract Java code from after the COLA marker in a helpText string."""
    for marker in [
        'COLA -- Copie este código na IDE:',
        'COLA -- Copie este codigo na IDE:',
        'COLA -- Copie este codigo COMPLETO na IDE:',
        'COLA -- Copie este código COMPLETO na IDE:',
        'COLA',
    ]:
        idx = help_text.find(marker)
        if idx >= 0:
            after = help_text[idx + len(marker):]
            nl_nl = after.find('\n\n')
            return after[nl_nl + 2:].strip() if nl_nl >= 0 else after.strip()
    return None


def infer_filename(java_code: str) -> str:
    """Get filename from public class declaration."""
    m = re.search(r'public\s+class\s+(\w+)', java_code)
    if m:
        return m.group(1) + '.java'
    m = re.search(r'\bclass\s+(\w+)', java_code)
    if m:
        return m.group(1) + '.java'
    return 'Main.java'


# ---------- Extract all helpText strings that contain COLA from scale steps ----------
# We scan all helpText: occurrences inside the SCALE_MISSIONS block.

# Locate SCALE_MISSIONS block
sm_start = src.find('const SCALE_MISSIONS = {')
sm_end_marker = '\nconst STAGE_ORDER'
sm_end = src.find(sm_end_marker, sm_start)
if sm_end < 0:
    sm_end = src.find('\nconst IDE', sm_start)
if sm_end < 0:
    sm_end = sm_start + 200_000  # fallback: search in large window

scale_block = src[sm_start:sm_end]

# Find all challenge IDs mentioned in the block
challenge_ids = re.findall(r'^\s{4}(\w+)\s*:\s*\{', scale_block, re.MULTILINE)

# Find all helpText strings in the scale block
entries = []
pos = 0
while True:
    ht_m = re.search(r"helpText:\s*(['\"])", scale_block[pos:])
    if not ht_m:
        break
    abs_start = pos + ht_m.end() - 1
    raw, end_pos = read_js_string(scale_block, abs_start)
    help_text = unescape_js(raw)
    cola = extract_cola_from_helptext(help_text)
    if cola:
        fname = infer_filename(cola)
        # Guess challenge ID by looking backwards
        snippet_before = scale_block[max(0, abs_start - 3000):abs_start]
        id_matches = re.findall(r'^\s{4}(\w+)\s*:\s*\{', snippet_before, re.MULTILINE)
        ch_id = id_matches[-1] if id_matches else 'unknown'
        # Guess step name
        step_matches = re.findall(r"name:\s*'([^']+)'", snippet_before[-500:])
        step_name = step_matches[-1] if step_matches else '?'
        entries.append({
            'ch_id': ch_id,
            'step': step_name,
            'fileName': fname,
            'cola': cola,
        })
    pos += ht_m.end()

print(f"Total COLA codes de expansão encontrados: {len(entries)}\n")
print(f"{'Desafio':<18} {'Passo':<30} {'Arquivo':<25} {'Status':<15} {'Detalhe'}")
print("-" * 115)

errors = []
ok_count = 0

for e in entries:
    ch_id    = e['ch_id']
    step     = e['step']
    fname    = e['fileName']
    cola     = e['cola']

    with tempfile.TemporaryDirectory() as tmp:
        java_file = os.path.join(tmp, fname)
        try:
            with open(java_file, 'w', encoding='utf-8') as f:
                f.write(cola)
        except Exception as ex:
            print(f"{ch_id:<18} {step:<30} {fname:<25} {'WRITE_ERR':<15} {ex}")
            errors.append({'ch_id': ch_id, 'step': step, 'status': 'WRITE_ERR', 'detail': str(ex)})
            continue

        # Compile
        try:
            rc = subprocess.run(
                ['javac', '--release', '17', '-encoding', 'UTF-8', fname],
                capture_output=True, text=True, timeout=20, cwd=tmp
            )
        except subprocess.TimeoutExpired:
            print(f"{ch_id:<18} {step:<30} {fname:<25} {'COMPILE_TIMEOUT':<15}")
            errors.append({'ch_id': ch_id, 'step': step, 'status': 'COMPILE_TIMEOUT', 'detail': '', 'code': cola})
            continue
        except FileNotFoundError:
            print("FATAL: javac not found in PATH")
            break

        if rc.returncode != 0:
            err = (rc.stderr or '').strip()
            short_err = ' | '.join(l for l in err.split('\n') if ': error:' in l)[:90]
            print(f"{ch_id:<18} {step:<30} {fname:<25} {'COMPILE_ERR':<15} {short_err}")
            errors.append({'ch_id': ch_id, 'step': step, 'status': 'COMPILE_ERR', 'detail': err, 'code': cola})
            continue

        # Run
        cls = fname.replace('.java', '')
        try:
            rx = subprocess.run(
                ['java', '-cp', '.', cls],
                capture_output=True, text=True, timeout=8,
                stdin=subprocess.DEVNULL, cwd=tmp
            )
        except subprocess.TimeoutExpired:
            print(f"{ch_id:<18} {step:<30} {fname:<25} {'RUN_TIMEOUT':<15} aguardando stdin?")
            errors.append({'ch_id': ch_id, 'step': step, 'status': 'RUN_TIMEOUT', 'detail': '', 'code': cola})
            continue

        if rx.returncode != 0:
            err = (rx.stderr or '').strip()[:100]
            print(f"{ch_id:<18} {step:<30} {fname:<25} {'RUNTIME_ERR':<15} {err}")
            errors.append({'ch_id': ch_id, 'step': step, 'status': 'RUNTIME_ERR', 'detail': rx.stderr, 'code': cola})
        else:
            ok_count += 1
            out = (rx.stdout or '').strip().replace('\n', ' | ')[:55]
            print(f"{ch_id:<18} {step:<30} {fname:<25} {'OK':<15} {out}")

print()
print("=" * 115)
print(f"RESULTADO FINAL: {ok_count}/{len(entries)} OK  |  {len(errors)} com problemas")
print("=" * 115)

if errors:
    print("\n--- ERROS DETALHADOS ---")
    for e in errors:
        print(f"\n[{e['status']}] {e['ch_id']} / {e['step']}")
        print(e.get('detail', '')[:600])
        if 'code' in e:
            print("\nCódigo COLA:")
            print(e['code'][:800])
        print("-" * 60)
