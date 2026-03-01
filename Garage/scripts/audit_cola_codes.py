"""
Audit ALL COLA codes in game.js — compile + run with javac 17 real.
Reports compilation errors and runtime errors for every challenge.

Strategy:
  1. Scan for every "id: 'code_'" marker.
  2. For each block (up to next id marker) extract fileName and helpText using
     a quote-aware parser (handles escaped quotes inside the string).
  3. Extract the Java code that follows the COLA marker.
  4. Write to temp file, compile with javac 17, run with java.
"""
import re
import os
import subprocess
import tempfile
import shutil

GAME_JS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'game.js'))

with open(GAME_JS, encoding='utf-8') as f:
    src = f.read()


def unescape_js(s: str) -> str:
    """Convert JS string escape sequences to real characters."""
    return (s
        .replace("\\'", "'")
        .replace('\\"', '"')
        .replace('\\n', '\n')
        .replace('\\t', '\t')
        .replace('\\r', '\r')
        .replace('\\\\', '\\'))


def read_js_string(text: str, start: int):
    """
    Given text and the index of the opening quote (' or "),
    return (raw_content, end_pos).  Handles backslash escapes.
    """
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


# Locate every challenge block boundary
id_positions = [(m.start(), m.group(1))
                for m in re.finditer(r"id:\s*'(code_[^']+)'", src)]

challenges = []

for idx, (pos, ch_id) in enumerate(id_positions):
    block_end = id_positions[idx + 1][0] if idx + 1 < len(id_positions) else len(src)
    block = src[pos:block_end]

    # --- fileName ---
    fn_m = re.search(r"fileName:\s*(['\"])", block)
    if not fn_m:
        continue
    quote_start = fn_m.start() + fn_m.end() - fn_m.start() - 1
    file_name_raw, _ = read_js_string(block, fn_m.end() - 1)
    file_name = unescape_js(file_name_raw)

    # --- helpText ---
    ht_m = re.search(r"helpText:\s*(['\"])", block)
    if not ht_m:
        continue
    help_raw, _ = read_js_string(block, ht_m.end() - 1)
    help_text = unescape_js(help_raw)

    # --- Find COLA section ---
    cola_idx = -1
    for marker in ['COLA -- Copie este código na IDE:',
                   'COLA -- Copie este codigo na IDE:',
                   'COLA']:
        cola_idx = help_text.find(marker)
        if cola_idx >= 0:
            cola_len = len(marker)
            break

    if cola_idx < 0:
        continue

    after = help_text[cola_idx + cola_len:]
    nl_nl = after.find('\n\n')
    cola_code = after[nl_nl + 2:].strip() if nl_nl >= 0 else after.strip()

    if not cola_code:
        continue

    challenges.append({'id': ch_id, 'fileName': file_name, 'cola': cola_code})

# ─────────────────────────────────────────────────────────────────────────────
print(f"Total COLA codes encontrados: {len(challenges)}\n")
print(f"{'ID':<25} {'Arquivo':<22} {'Status':<15} {'Detalhe'}")
print("-" * 100)

errors   = []
ok_count = 0

for ch in challenges:
    tmp = tempfile.mkdtemp(prefix='garage_audit_')
    try:
        fname = ch['fileName']
        fp    = os.path.join(tmp, fname)
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(ch['cola'])

        # --- Compilar ---
        rc = subprocess.run(
            ['javac', '--release', '17', '-encoding', 'UTF-8', fname],
            capture_output=True, text=True, timeout=30, cwd=tmp
        )
        if rc.returncode != 0:
            err = (rc.stdout + rc.stderr).replace(tmp + os.sep, '').replace(tmp + '/', '').strip()
            errors.append({'id': ch['id'], 'stage': 'compile', 'err': err})
            print(f"  {ch['id']:<25} {fname:<22} {'COMPILE_ERR':<15} {err[:80]}")
            continue

        # --- Executar ---
        cls = fname.replace('.java', '')
        rx = subprocess.run(
            ['java', '-cp', '.', cls],
            capture_output=True, text=True, timeout=8,
            stdin=subprocess.DEVNULL,   # prevents hanging on Scanner/BufferedReader
            cwd=tmp
        )
        if rx.returncode != 0:
            err = (rx.stdout + rx.stderr).strip()
            errors.append({'id': ch['id'], 'stage': 'runtime', 'err': err})
            print(f"  {ch['id']:<25} {fname:<22} {'RUNTIME_ERR':<15} {err[:80]}")
        else:
            ok_count += 1
            stdout_preview = (rx.stdout or '').strip().replace('\n', ' | ')[:50]
            print(f"  {ch['id']:<25} {fname:<22} {'OK':<15} output: {stdout_preview}")
    except subprocess.TimeoutExpired:
        errors.append({'id': ch['id'], 'stage': 'timeout', 'err': 'Timeout'})
        print(f"  {ch['id']:<25} {ch['fileName']:<22} {'TIMEOUT':<15}")
    except Exception as e:
        errors.append({'id': ch['id'], 'stage': 'exception', 'err': str(e)})
        print(f"  {ch['id']:<25} {ch['fileName']:<22} {'EXCEPTION':<15} {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

print()
print("=" * 100)
print(f"RESULTADO FINAL: {ok_count}/{len(challenges)} OK  |  {len(errors)} com problemas")
print("=" * 100)

if errors:
    print("\nERROS DETALHADOS:")
    for e in errors:
        print(f"\n  [{e['stage'].upper()}] {e['id']}")
        print(f"  {e['err'][:600]}")
