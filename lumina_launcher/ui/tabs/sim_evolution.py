"""
UI Tabs - SIM Evolution Dashboard
"""

import streamlit as st


def render_sim_evolution_tab() -> None:
    st.subheader("🚀 SIM Evolution Dashboard")

    st.markdown("""
    Volg de evolutie van je trading agents over generaties. 
    Hier zie je de beste performers en kun je nieuwe evolutierondes starten.
    """)

    # === Current Status ===
    st.markdown("#### Huidige SIM Evolutie Status")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active SIM Agents", "—", help="Aantal actieve SIM agents")
    with col2:
        st.metric("Best Sharpe Ratio", "—", help="Beste Sharpe ratio tot nu toe")
    with col3:
        st.metric("Current Generation", "—", help="Huidige generatie")
    with col4:
        st.metric("Total Evolutions", "—", help="Totaal aantal evolutierondes")

    st.info("SIM evolutie data wordt zichtbaar zodra je een SIM draait en data hebt verzameld.")

    # === Top Performers (placeholder) ===
    st.markdown("#### Top Performers (laatste generatie)")
    st.caption("Hier komen de beste agents van de laatste evolutieronde te staan.")

    # === Actions ===
    st.markdown("#### Acties")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🚀 Start Aggressive Overnight SIM", width="stretch"):
            st.success("Overnight SIM zou hier gestart worden via de Process Manager.")

    with col_b:
        if st.button("📈 View Full Evolution History", width="stretch"):
            st.info("Volledige evolutiegeschiedenis viewer komt in een latere iteratie.")

    st.caption("SIM Evolution tab — Fase 2 (op niveau gebracht)")
