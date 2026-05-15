"""
UI Tabs - Live Trader View
"""

import streamlit as st
from typing import Any


def render_live_trader_tab(state: dict[str, Any], current_dream: dict[str, Any]) -> None:
    st.subheader("Live Dream + Runtime State")

    # === Current Dream ===
    st.markdown("#### Current Dream / Runtime State")

    if current_dream:
        with st.container(border=True):
            st.json(current_dream, expanded=False)
    else:
        st.info("Nog geen active dream / runtime state gevonden.")

    # === Key Metrics ===
    st.markdown("#### Key Trading Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Sim Position Qty",
            value=state.get("sim_position_qty", 0),
            help="Huidige positie in SIM mode"
        )
    with col2:
        st.metric(
            "Live Position Qty",
            value=state.get("live_position_qty", 0),
            help="Huidige positie in REAL / Live mode"
        )
    with col3:
        pending = len(state.get("pending_trade_reconciliations", []) or [])
        st.metric(
            "Pending Reconciliations",
            value=pending,
            delta="needs attention" if pending > 0 else None
        )

    # === Additional Info ===
    if state:
        with st.expander("📋 Volledige Runtime State"):
            st.json(state, expanded=False)

    st.caption("Live Trader tab — Fase 2 (uitgewerkt)")
