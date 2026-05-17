"""Start the LUMINA Streamlit launcher with warning filters applied before Streamlit loads."""

from __future__ import annotations

import runpy
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

try:
    from authlib.deprecate import AuthlibDeprecationWarning
except Exception:  # pragma: no cover - only used when authlib is missing
    class AuthlibDeprecationWarning(DeprecationWarning):
        """Fallback warning category when authlib is unavailable."""

warnings.filterwarnings("ignore", category=AuthlibDeprecationWarning)

_REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(_REPO_ROOT / ".env")
_LAUNCHER_SCRIPT = _REPO_ROOT / "streamlit_launcher.py"
_FILE_WATCHER_FLAG = ("--server.fileWatcherType", "none")


def _argv_with_file_watcher_disabled(extra: list[str]) -> list[str]:
    """Prevent Streamlit from importing PyPI ``watchdog`` (shadowed by repo ``watchdog.py``)."""
    if any(arg.startswith("--server.fileWatcherType") for arg in extra):
        return ["streamlit", "run", str(_LAUNCHER_SCRIPT), *extra]
    return ["streamlit", "run", str(_LAUNCHER_SCRIPT), *_FILE_WATCHER_FLAG, *extra]


def main() -> None:
    # Use Streamlit's public module entrypoint instead of internal API imports.
    sys.argv = _argv_with_file_watcher_disabled(sys.argv[1:])
    runpy.run_module("streamlit", run_name="__main__")


if __name__ == "__main__":
    main()
