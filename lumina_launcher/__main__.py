"""``python -m lumina_launcher``: headless CLI or Streamlit UI (default)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    argv = list(sys.argv[1:])
    if "--headless" in argv or "--stability-check" in argv:
        from lumina_launcher.headless import run_headless

        return run_headless(argv)

    streamlit_entry = _repo_root() / "streamlit_launcher.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(streamlit_entry), *argv]
    return int(subprocess.call(cmd))


if __name__ == "__main__":
    raise SystemExit(main())
