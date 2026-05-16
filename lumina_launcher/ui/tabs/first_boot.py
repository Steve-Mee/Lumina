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
    estimate_first_boot_real_days,
    exceeds_max_real_days_window,
)
from lumina_launcher.ui.help_texts import help_for


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
            help=help_for("training_trades"),
        )
    with col2:
        prefer_real_data_only = st.checkbox(
            "Prefer real data only",
            value=settings.get("prefer_real_data_only", True),
            help=help_for("prefer_real_data_only"),
        )

    col3, col4 = st.columns(2)
    with col3:
        max_real_days = st.number_input(
            "Max real days",
            min_value=30,
            max_value=3650,
            value=int(settings.get("max_real_days", 365)),
            step=5,
            help=help_for("max_real_days"),
        )
    with col4:
        allow_fallback = st.checkbox(
            "Allow minimal synthetic fallback",
            value=bool(settings.get("allow_minimal_synthetic_fallback", False)),
            help=help_for("allow_minimal_synthetic_fallback"),
        )

    require_real_sim = st.checkbox(
        "Require real simulator data (fail-closed)",
        value=bool(settings.get("require_real_simulator_data", True)),
        help=help_for("require_real_simulator_data"),
    )

    estimate_days = estimate_first_boot_real_days(int(training_trades))
    st.caption(f"Geschatte benodigde echte historische dagen: {estimate_days}")
    if exceeds_max_real_days_window(estimate_days, int(max_real_days)):
        st.warning(
            "Trade volume overschrijdt vermoedelijk `max_real_days`; verlaag trades of verhoog venster."
        )

    if st.button("💾 Save Settings", width="stretch"):
        first_boot_manager.save_full_settings(
            training_trades=int(training_trades),
            prefer_real_data_only=bool(prefer_real_data_only),
            max_real_days=int(max_real_days),
            allow_minimal_synthetic_fallback=bool(allow_fallback),
            require_real_simulator_data=bool(require_real_sim),
        )
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
