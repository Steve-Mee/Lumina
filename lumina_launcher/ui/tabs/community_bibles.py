"""
UI Tab - Community Bibles (Global Wisdom)
Gebruikt de echte /global_wisdom endpoint van de backend.
"""

import asyncio
import inspect

import streamlit as st

from lumina_launcher.services.backend_client import BackendClient


def render_community_bibles_tab(backend_client: BackendClient | None = None) -> None:
    st.subheader("📖 Community Bibles & Global Wisdom")

    st.markdown("""
    Hier zie je de top Community Bibles van de Lumina community, 
    gerangschikt op performance (Sharpe ratio).
    """)

    client = backend_client or BackendClient()
    raw = client.get_global_wisdom_sync()
    if inspect.isawaitable(raw):
        loop = asyncio.new_event_loop()
        try:
            payload = loop.run_until_complete(raw)
        finally:
            loop.close()
    else:
        payload = raw
    if not isinstance(payload, dict):
        st.error(f"Onverwacht antwoord van de backend client: {type(payload).__name__}")
        return

    if payload.get("error"):
        st.warning("Kon global wisdom niet laden. Is de backend draaiende?")
        st.caption(str(payload.get("error")))
        return

    bibles = payload.get("top_bibles", [])
    avg_score = payload.get("average_global_wisdom_score")

    if not bibles:
        st.info("Nog geen Community Bibles gevonden.")
        return

    # Toon gemiddelde score
    if avg_score is not None:
        st.metric("Gemiddelde Global Wisdom Score", f"{avg_score:.3f}")

    st.markdown("#### Top Community Bibles")

    for bible in bibles:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{bible.get('trader_name', 'Onbekend')}**")
                st.caption(f"Reflecties: {bible.get('reflection_count', 0)}")
            with col2:
                score = bible.get("performance_score", 0)
                st.metric("Sharpe", f"{score:.3f}")

    st.caption("Community Bibles tab — Geïntegreerd met /global_wisdom")
