"""
UI Tab - Admin Panel
Volledig functionele admin interface met backend integratie.
"""

import asyncio
import streamlit as st

from services.backend_client import BackendClient


def render_admin_tab(backend_client: BackendClient | None = None) -> None:
    st.subheader("🛠️ Admin Panel")

    st.warning("⚠️ Deze acties zijn permanent en kunnen niet ongedaan gemaakt worden!")

    client = backend_client or BackendClient()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑️ Verwijder ALLE Trades", type="primary", width="stretch"):
            with st.spinner("Bezig met verwijderen..."):
                result = asyncio.run(client.delete_all_trades())
                if result.get("error"):
                    st.error(f"Fout: {result.get('error')}")
                else:
                    st.success("Alle trades succesvol verwijderd!")
                    st.json(result)

    with col2:
        if st.button("🧹 Verwijder DEMO Data", width="stretch"):
            with st.spinner("Bezig met verwijderen..."):
                result = asyncio.run(client.delete_demo_data())
                if result.get("error"):
                    st.error(f"Fout: {result.get('error')}")
                else:
                    st.success("Demo data succesvol verwijderd!")
                    st.json(result)

    st.divider()
    st.caption("Admin Panel — Volledig geïntegreerd met backend")
