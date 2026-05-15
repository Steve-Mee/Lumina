"""LUMINA OS Streamlit launcher — run from repository root.

``python -m streamlit run streamlit_launcher.py``

For headless / stability-check, use :mod:`lumina_launcher` (``python -m lumina_launcher``).
"""

from __future__ import annotations

from lumina_launcher.streamlit_main import render_streamlit_app

render_streamlit_app()
