"""
UI Tabs - Model Management
"""

import streamlit as st

from lumina_launcher.services.hardware_service import HardwareService
from lumina_launcher.services.model_service import ModelService


def render_model_management_tab(hardware_service: HardwareService, model_service: ModelService, snapshot) -> None:
    st.subheader("Model Management")

    catalog = model_service.get_catalog()
    current = model_service.get_current_model() or catalog.models()[0]
    recommended = hardware_service.recommended_model(catalog)
    supports_unsloth = hardware_service.supports_unsloth()

    # === Current vs Recommended ===
    st.markdown("#### Huidig vs Aanbevolen Model")

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Current Model**\n\n{current.display_name}")
    with col2:
        st.success(f"**Recommended Model**\n\n{recommended.display_name}")

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

    if st.button("⬇️ Install / Upgrade naar Recommended", width="stretch"):
        st.info("Model installatie/upgrade zou hier starten (SetupService integratie volgt).")

    if st.button("🔄 Refresh Model Catalog", width="stretch"):
        st.success("Model catalog zou hier herladen worden.")

    st.caption("Model Management tab — Fase 2 (uitgewerkt)")
