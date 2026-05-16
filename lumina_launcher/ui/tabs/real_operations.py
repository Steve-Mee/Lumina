"""REAL operations tab backed by shared dashboard views."""

import streamlit as st
from pathlib import Path

from lumina_os.frontend.dashboard_views import DashboardPaths, render_real_operations_dashboard_tab


def render_real_operations_tab(workspace_root: Path) -> None:
    render_real_operations_dashboard_tab(DashboardPaths(workspace_root))
    st.caption("REAL operations dashboard draait op gedeelde metrics en protocollen.")
