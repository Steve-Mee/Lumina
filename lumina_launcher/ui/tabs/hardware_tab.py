"""
UI Tabs - Hardware & Install
"""

import streamlit as st

from services.hardware_service import HardwareService
from services.model_service import ModelService


def render_hardware_tab(hardware_service: HardwareService, model_service: ModelService, snapshot) -> None:
    st.subheader("Hardware & Model Alignment")

    recommended = hardware_service.recommended_model(model_service.get_catalog())
    supports_unsloth = hardware_service.supports_unsloth()
    tier_reqs = hardware_service.get_tier_requirements()

    # === Hardware Snapshot ===
    st.markdown("#### Hardware Snapshot")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Hardware Tier", snapshot.profile_tier.upper())
    with col2:
        st.metric("RAM", f"{snapshot.ram_gb:.1f} GB")
    with col3:
        st.metric("GPU VRAM", f"{snapshot.gpu_vram_gb:.1f} GB")

    # === Recommendations ===
    st.markdown("#### Model Recommendation")

    st.success(f"**Recommended Model:** {recommended.display_name}")
    st.caption(f"Min RAM: {recommended.ram_min_gb} GB | Min VRAM: {recommended.vram_min_gb} GB")

    # === Unsloth Support ===
    st.markdown("#### Unsloth Fine-tuning Support")

    if supports_unsloth:
        st.success("✅ Unsloth supported on this hardware")
    else:
        st.warning("⚠️ Unsloth not fully supported (check OS, GPU compute capability ≥ 7.0 and ≥ 8GB VRAM)")

    # === Tier Requirements ===
    with st.expander("📋 Tier Requirements"):
        st.json(tier_reqs)

    # === Actions ===
    if st.button("🔄 Refresh Hardware Scan", width="stretch"):
        refreshed = hardware_service.refresh()
        st.success(f"Hardware refreshed → Tier: {refreshed.profile_tier.upper()}")
        st.rerun()

    st.caption("Hardware tab — Fase 2 (Feature Restoration)")
