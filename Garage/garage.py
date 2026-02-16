"""GARAGE - Simple launcher."""
import uvicorn
import webbrowser
import threading

def _open_browser():
    """Open the default browser after a short delay to allow server startup."""
    import time
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_includes=["*.py", "*.html", "*.css", "*.js"],
        reload_excludes=["__pycache__/*", "data/*", "*.json"],
    )
