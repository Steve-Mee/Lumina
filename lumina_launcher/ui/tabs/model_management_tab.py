"""
UI Tabs - Model Management
"""

import streamlit as st
from lumina_core.engine.setup_service import SetupService

from lumina_launcher.services.hardware_service import HardwareService
from lumina_launcher.services.model_service import ModelService
from lumina_launcher.ui.help_texts import help_for


def render_model_management_tab(
    hardware_service: HardwareService,
    model_service: ModelService,
    snapshot,
    setup_service: SetupService | None = None,
) -> None:
    st.subheader("Model Management")

    catalog = model_service.get_catalog()
    current = model_service.get_current_model() or catalog.models()[0]
    recommended = hardware_service.recommended_model(catalog)
    supports_unsloth = hardware_service.supports_unsloth()

    # === Current vs Recommended ===
    st.markdown("#### Huidig vs Aanbevolen Model")

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Current Model**\n\n{current.display_name}", icon="🧠")
    with col2:
        st.success(f"**Recommended Model**\n\n{recommended.display_name}", icon="✅")

    # === Model Details ===
    st.markdown("#### Model Details")

    with st.container(border=True):
        st.write(f"**{recommended.display_name}**")
        st.write(f"- Min RAM: **{recommended.ram_min_gb} GB**")
        st.write(f"- Min VRAM: **{recommended.vram_min_gb} GB**")
        st.write(f"- Unsloth support: {'✅ Ja' if supports_unsloth else '❌ Nee'}")

    # === Upgrade Targets ===
    st.markdown("#### Mogelijke Upgrades")

    try:
        current_key = getattr(current, "key", "") or ""
        upgrade_targets = model_service.get_upgrade_targets(current_key)
    except Exception:
        upgrade_targets = []

    if upgrade_targets:
        for model in upgrade_targets[:5]:
            st.write(f"• {model.display_name}")
    else:
        st.caption("Geen directe upgrade targets gevonden of al op het hoogste model.")

    # === Actions ===
    st.markdown("#### Acties")

    if st.button(
        "⬇️ Install / Upgrade naar Recommended",
        width="stretch",
        help="Download model en update config naar de gekozen target.",
    ):
        if setup_service is None:
            st.warning("SetupService niet beschikbaar in deze context.")
        else:
            results = setup_service.upgrade_model(recommended)
            success = all(item.success for item in results)
            for item in results:
                if item.success:
                    st.success(f"{item.name}: {item.message}")
                else:
                    st.error(f"{item.name}: {item.message}")
            if success:
                model_service.set_current_model(recommended.key)

    if st.button("🔄 Refresh Model Catalog", width="stretch", help=help_for("dashboard_enabled")):
        refreshed = hardware_service.get_snapshot(refresh=True)
        st.success(f"Hardware snapshot refreshed ({refreshed.profile_tier}).")

    st.caption("Model Management tab — Fase 2 (uitgewerkt)")
