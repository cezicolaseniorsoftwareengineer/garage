from __future__ import annotations

import os
import runpy
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parent
    app_root = project_root / "Garage"
    target = app_root / "garage.py"

    if not target.exists():
        raise FileNotFoundError(f"Missing launcher target: {target}")

    # Match the original script behavior that relies on relative paths.
    os.chdir(app_root)
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
