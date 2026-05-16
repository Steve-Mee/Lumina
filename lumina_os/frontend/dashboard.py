"""Legacy Streamlit entry for the LUMINA OS training / monitoring dashboard (port 8502).

Loads `dashboard_views` for all UI; run from repo root with ``PYTHONPATH`` set, or from
``lumina_os`` per `scripts/start_lumina_with_training_dashboard.ps1`.
"""

from __future__ import annotations

import streamlit as st

from dashboard_views import (
    DashboardPaths,
    ensure_frontend_import_path,
    render_full_streamlit_dashboard,
    resolve_workspace_root_from_this_module,
)


def main() -> None:
    ensure_frontend_import_path()
    st.set_page_config(page_title="LUMINA OS", layout="wide")
    p = DashboardPaths(resolve_workspace_root_from_this_module())
    render_full_streamlit_dashboard(p)


main()
