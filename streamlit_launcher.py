"""LUMINA OS Streamlit launcher — run from repository root.

``python -m streamlit run streamlit_launcher.py``

For headless / stability-check, use :mod:`lumina_launcher` (``python -m lumina_launcher``).
"""

from __future__ import annotations

from pathlib import Path

import warnings
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(_REPO_ROOT / ".env")

# Third-party (authlib via Streamlit). Optional dependency in some environments.
try:
    from authlib.deprecate import AuthlibDeprecationWarning
except Exception:  # pragma: no cover - only used when authlib is missing
    class AuthlibDeprecationWarning(DeprecationWarning):
        """Fallback warning category when authlib is unavailable."""

warnings.filterwarnings("ignore", category=AuthlibDeprecationWarning)

from lumina_launcher.streamlit_main import render_streamlit_app  # noqa: E402

render_streamlit_app()
