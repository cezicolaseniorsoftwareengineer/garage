"""Compatibility launcher.

This module used to host a legacy standalone backend.
Now it re-exports the main GARAGE app so old commands still start
the same server used by the current game frontend.
"""
import uvicorn

from app.main import app


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_includes=["*.py", "*.html", "*.css", "*.js"],
        reload_excludes=["__pycache__/*", "data/*", "*.json"],
    )

