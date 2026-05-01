from __future__ import annotations

import os
import subprocess
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
LAUNCHER = ROOT / "lumina_launcher.py"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def main() -> int:
    if not VENV_DIR.exists():
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)

    python_bin = _venv_python()
    # setuptools 82+ breaks torch / vllm pins; keep in [77, 82) per vllm's metadata.
    subprocess.run(
        [str(python_bin), "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools>=77.0.3,<82"],
        check=True,
    )
    subprocess.run([str(python_bin), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
    subprocess.run([str(python_bin), "-m", "pip", "install", "streamlit", "pyyaml", "psutil", "ollama"], check=True)
    subprocess.run([str(python_bin), "-m", "streamlit", "run", str(LAUNCHER)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
