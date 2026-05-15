"""
UI Tabs - First Boot Wizard
Improved and restored version for Fase 2.
"""

import streamlit as st

from lumina_launcher.core.first_boot import FirstBootManager
from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_TRADES,
    FIRST_BOOT_LAUNCHER_TRADE_STEP,
    FIRST_BOOT_TRAINING_TRADES_MAX,
    FIRST_BOOT_TRAINING_TRADES_MIN,
)


def render_first_boot_tab(first_boot_manager: FirstBootManager) -> None:
    st.subheader("🚀 First Boot Training")

    settings = first_boot_manager.read_settings()
    progress = first_boot_manager.read_progress()

    # Status
    if first_boot_manager.is_completed():
        st.success("✅ First-boot training is voltooid!")
        st.markdown(f"**Policy:** `{first_boot_manager.policy_path}`")
        return

    # Settings
    st.markdown("#### Training Instellingen")
    col1, col2 = st.columns(2)

    with col1:
        training_trades = st.number_input(
            "Aantal training trades",
            min_value=FIRST_BOOT_TRAINING_TRADES_MIN,
            max_value=FIRST_BOOT_TRAINING_TRADES_MAX,
            value=int(settings.get("training_trades", FIRST_BOOT_DEFAULT_TRADES)),
            step=FIRST_BOOT_LAUNCHER_TRADE_STEP,
        )
    with col2:
        st.checkbox(
            "Prefer real data only",
            value=settings.get("prefer_real_data_only", True),
        )

    if st.button("💾 Save Settings", width="stretch"):
        first_boot_manager.save_settings(int(training_trades))
        st.success("Instellingen opgeslagen. Herstart de bot om te beginnen.")

    st.divider()

    # Progress
    st.markdown("#### Training Progress")

    if progress:
        stage = progress.get("stage", "unknown")
        pct = first_boot_manager.get_stage_progress(stage)
        st.progress(pct, text=f"Stage: {stage}")

        if "trades_done" in progress:
            st.metric("Trades Completed", progress["trades_done"])
    else:
        st.info("Nog geen progress gevonden. Start de bot om first-boot te activeren.")

    # Actions
    st.markdown("#### Acties")
    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("⏸️ Pause Training", width="stretch"):
            first_boot_manager.request_pause()
            st.warning("Pause verzoek verstuurd. De training stopt bij de volgende checkpoint.")

    with col_b:
        if st.button("▶️ Resume / Start", width="stretch"):
            first_boot_manager.clear_pause_request()
            st.success("Resume verzoek verstuurd.")

    st.caption("First Boot tab — Fase 2 (Feature Restoration)")
