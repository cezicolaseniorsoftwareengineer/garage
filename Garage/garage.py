"""GARAGE - Simple launcher."""
import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

PORT = int(os.environ.get("PORT", 8000))
_HEALTH_URL = f"http://localhost:{PORT}/health"


def _wait_and_open():
    """Ping /health up to 20s; open browser only once the server responds."""
    import urllib.request
    for attempt in range(40):          # 40 × 0.5s = 20s max
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(_HEALTH_URL, timeout=1) as resp:
                if resp.status == 200:
                    print(f"[GARAGE] Servidor pronto em http://localhost:{PORT}")
                    webbrowser.open(f"http://localhost:{PORT}")
                    return
        except Exception:
            pass
    # Fallback: server never responded — at least tell user the URL
    print(f"[GARAGE] AVISO: servidor pode nao estar pronto. Acesse manualmente: http://localhost:{PORT}")


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    if _port_in_use(PORT):
        print(f"[GARAGE] ERRO: porta {PORT} ja esta em uso. Encerre o processo anterior ou altere PORT=<outro>.")
        sys.exit(1)

    threading.Thread(target=_wait_and_open, daemon=True).start()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=True,
        reload_includes=["*.py", "*.html", "*.css", "*.js"],
        reload_excludes=["__pycache__/*", "data/*", "*.json"],
    )
