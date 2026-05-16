"""Start the LUMINA Streamlit launcher with warning filters applied before Streamlit loads."""

from __future__ import annotations

import runpy
import sys
import warnings
from pathlib import Path

try:
    from authlib.deprecate import AuthlibDeprecationWarning
except Exception:  # pragma: no cover - only used when authlib is missing
    class AuthlibDeprecationWarning(DeprecationWarning):
        """Fallback warning category when authlib is unavailable."""

warnings.filterwarnings("ignore", category=AuthlibDeprecationWarning)

_REPO_ROOT = Path(__file__).resolve().parent
_LAUNCHER_SCRIPT = _REPO_ROOT / "streamlit_launcher.py"


def main() -> None:
    # Use Streamlit's public module entrypoint instead of internal API imports.
    sys.argv = ["streamlit", "run", str(_LAUNCHER_SCRIPT), *sys.argv[1:]]
    runpy.run_module("streamlit", run_name="__main__")


if __name__ == "__main__":
    main()
