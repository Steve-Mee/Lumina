"""SIM evolution tab backed by shared dashboard views."""

import streamlit as st
from pathlib import Path

from lumina_os.frontend.dashboard_views import DashboardPaths, render_sim_evolution_dashboard_tab


def render_sim_evolution_tab(workspace_root: Path) -> None:
    render_sim_evolution_dashboard_tab(DashboardPaths(workspace_root))
    st.caption("SIM Evolution gebruikt dezelfde kern als de monitoring dashboard views.")
