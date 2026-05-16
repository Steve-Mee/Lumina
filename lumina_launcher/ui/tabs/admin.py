"""
UI Tab - Admin Panel
Volledig functionele admin interface met backend integratie.
"""

import asyncio
import logging
import streamlit as st

from lumina_launcher.observability import log_event, timed_event
from lumina_launcher.services.backend_client import BackendClient

logger = logging.getLogger(__name__)


def render_admin_tab(backend_client: BackendClient | None = None) -> None:
    st.subheader("🛠️ Admin Panel")

    st.warning("⚠️ Deze acties zijn permanent en kunnen niet ongedaan gemaakt worden!")

    client = backend_client or BackendClient()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑️ Verwijder ALLE Trades", type="primary", width="stretch"):
            with st.spinner("Bezig met verwijderen..."):
                with timed_event("launcher.admin.mutation", action="delete_all_trades"):
                    result = asyncio.run(client.delete_all_trades())
                if result.get("error"):
                    log_event("launcher.admin.mutation_result", level=logging.ERROR, action="delete_all_trades", status="error")
                    st.error(f"Fout: {result.get('error')}")
                else:
                    log_event("launcher.admin.mutation_result", action="delete_all_trades", status="ok")
                    st.success("Alle trades succesvol verwijderd!")
                    st.json(result)

    with col2:
        if st.button("🧹 Verwijder DEMO Data", width="stretch"):
            with st.spinner("Bezig met verwijderen..."):
                with timed_event("launcher.admin.mutation", action="delete_demo_data"):
                    result = asyncio.run(client.delete_demo_data())
                if result.get("error"):
                    logger.warning("Admin mutation failed: delete_demo_data")
                    log_event("launcher.admin.mutation_result", level=logging.ERROR, action="delete_demo_data", status="error")
                    st.error(f"Fout: {result.get('error')}")
                else:
                    log_event("launcher.admin.mutation_result", action="delete_demo_data", status="ok")
                    st.success("Demo data succesvol verwijderd!")
                    st.json(result)

    st.divider()
    st.caption("Admin Panel — Volledig geïntegreerd met backend")
