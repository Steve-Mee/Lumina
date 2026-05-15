"""
UI Tabs - Trader League Leaderboard
"""

import asyncio
import inspect

import streamlit as st
import pandas as pd

from lumina_launcher.services.backend_client import BackendClient


def render_trader_league_tab(backend_client: BackendClient | None = None) -> None:
    st.subheader("Trader League Leaderboard")

    st.markdown("""
    Globale ranking van alle Lumina traders (zowel SIM als REAL). 
    Hoe beter je performance, hoe hoger je in de league komt.
    """)

    client = backend_client or BackendClient()

    # === Leaderboard ===
    st.markdown("#### Huidige Leaderboard")

    raw = client.get_leaderboard_sync()
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

    leaderboard = payload.get("leaderboard", [])

    if leaderboard and not payload.get("error"):
        st.dataframe(pd.DataFrame(leaderboard), width="stretch")
    elif payload.get("error"):
        st.warning("Kon leaderboard niet laden. Is de backend (lumina_os) draaiende op poort 8000?")
        st.caption(str(payload.get("error")))
    else:
        st.info("Leaderboard is nog leeg. Start een SIM om deel te nemen en punten te verdienen.")

    # === Info ===
    with st.expander("ℹ️ Hoe werkt de Trader League?"):
        st.markdown("""
        - Elke SIM en REAL trader scoort punten op basis van performance.
        - Belangrijkste metrics: **Sharpe Ratio**, **Profit Factor**, en **Drawdown**.
        - De leaderboard wordt dagelijks bijgewerkt.
        - Top traders krijgen extra zichtbaarheid in de community.
        """)

    st.caption("Trader League tab — Volledig geïntegreerd met backend")
