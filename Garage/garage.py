"""GARAGE - Simple launcher.

Run from anywhere:
    python Garage/garage.py
    python garage.py          (if already inside Garage/)

Startup sequence:
  1. Load .env from the same directory as this file
  2. chdir into that directory (so app.main:app is resolvable)
  3. Start uvicorn — watch only app/ to avoid spurious reloads
  4. Open browser once /health responds 200
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ── 1. Resolve project root (directory that contains THIS file) ──────────────
_HERE = Path(__file__).resolve().parent

# ── 2. Load .env BEFORE importing anything that reads os.environ ─────────────
try:
    from dotenv import load_dotenv
    _env_file = _HERE / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
        print(f"[GARAGE] .env carregado de {_env_file}")
    else:
        print(f"[GARAGE] AVISO: .env nao encontrado em {_env_file}")
except ImportError:
    print("[GARAGE] AVISO: python-dotenv nao instalado — variaveis de ambiente nao foram carregadas do .env")

# ── 3. chdir so that 'app.main:app' is resolvable regardless of CWD ──────────
os.chdir(_HERE)
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import uvicorn

PORT = int(os.environ.get("PORT", 8000))
_HEALTH_URL = f"http://localhost:{PORT}/health"


def _wait_and_open():
    """Ping /health up to 20s then open browser once the server responds 200."""
    import urllib.request
    for _ in range(40):          # 40 × 0.5s = 20s max
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(_HEALTH_URL, timeout=1) as resp:
                if resp.status == 200:
                    print(f"[GARAGE] Servidor pronto → http://localhost:{PORT}")
                    webbrowser.open(f"http://localhost:{PORT}")
                    return
        except Exception:
            pass
    print(f"[GARAGE] AVISO: servidor nao respondeu em 20s. Acesse manualmente: http://localhost:{PORT}")


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    if _port_in_use(PORT):
        print(
            f"[GARAGE] ERRO: porta {PORT} ja esta em uso.\n"
            f"  • Encerre o processo anterior, ou\n"
            f"  • Execute com outra porta: PORT=8001 python garage.py"
        )
        sys.exit(1)

    threading.Thread(target=_wait_and_open, daemon=True).start()

    # reload_dirs limited to app/ only — evita reloads desnecessarios de scripts/
    _reload = os.environ.get("ENV", "development").lower() != "production"
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=PORT,
            reload=_reload,
            reload_dirs=[str(_HERE / "app")] if _reload else None,
            log_level="info",
        )
    except KeyboardInterrupt:
        # Ctrl+C: saída limpa — evita socket zumbi no Windows
        print("\n[GARAGE] Servidor encerrado (Ctrl+C). Até mais!")
        sys.exit(0)
