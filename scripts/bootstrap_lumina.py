from __future__ import annotations

import os
import subprocess
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
BACKEND_SCRIPT = ROOT / "lumina_os" / "run_backend.ps1"
TAURI_DIR = ROOT / "tauri-app"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _print_command_deck_instructions() -> None:
    print("")
    print("LUMINA bootstrap complete.")
    print("")
    print("Next steps — Neural Command Deck (Tauri):")
    print("  1. Start backend (new terminal):")
    if os.name == "nt":
        print(r"     .\lumina_os\run_backend.ps1")
    else:
        print("     cd lumina_os && PYTHONPATH=.. python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000")
    print("  2. Start Command Deck (new terminal):")
    print("     cd tauri-app")
    print("     npm install")
    print("     npm run tauri dev")
    print("")
    print("Headless runtime (one-shot, no supervisor loop):")
    print("  python -m lumina_launcher --smoke --mode sim --duration 15m")
    print("")
    print("Autonomous SIM/Paper loop (daemon, prints PID):")
    print("  python -m lumina_launcher --mode sim")
    print("  python -m lumina_launcher --mode paper")
    print("")


def main() -> int:
    if not VENV_DIR.exists():
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)

    python_bin = _venv_python()
    subprocess.run(
        [str(python_bin), "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools>=77.0.3,<82"],
        check=True,
    )
    subprocess.run([str(python_bin), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
    subprocess.run(
        [str(python_bin), "-m", "pip", "install", "pyyaml", "psutil", "ollama"],
        check=True,
    )

    if os.name == "nt" and BACKEND_SCRIPT.exists():
        print("Starting FastAPI backend on http://127.0.0.1:8000 …")
        print("Press Ctrl+C to stop the backend and see Command Deck instructions.")
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BACKEND_SCRIPT)],
                cwd=str(ROOT),
                check=False,
            )
        except KeyboardInterrupt:
            pass
    else:
        _print_command_deck_instructions()
        return 0

    _print_command_deck_instructions()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
