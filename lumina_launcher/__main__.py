"""``python -m lumina_launcher``: headless CLI or usage hint for Command Deck."""

from __future__ import annotations

import sys


def _print_usage() -> None:
    print(
        "LUMINA launcher — Neural Command Deck is the operator UI.\n"
        "\n"
        "Start the Command Deck:\n"
        "  1. Backend:  .\\lumina_os\\run_backend.ps1   (or uvicorn on :8000)\n"
        "  2. Desktop:    cd tauri-app && npm run tauri dev\n"
        "\n"
        "Headless runtime (no UI):\n"
        "  python -m lumina_launcher --headless\n"
        "\n"
        "First install:\n"
        "  python scripts/bootstrap_lumina.py\n"
    )


def main() -> int:
    argv = list(sys.argv[1:])
    if "--headless" in argv or "--stability-check" in argv:
        from lumina_launcher.headless import run_headless

        return run_headless(argv)

    if argv and argv[0] in {"-h", "--help"}:
        _print_usage()
        return 0

    _print_usage()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
