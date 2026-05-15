"""
UI Components - Presence Strip
Live heartbeat / status strip.
"""

import streamlit as st
from typing import Any


def render_presence_strip(bundle: dict[str, Any]) -> None:
    dot_cls = "lumina-presence-dot-live" if bundle.get("pulse_live") else "lumina-presence-dot-idle"
    label_txt = "LUMINA LIVE" if bundle.get("pulse_live") else "STANDBY"
    mid = bundle.get("last_activity_verbose", "")
    tpm = bundle.get("tpm_label", "—")

    st.markdown(
        f"""
<style>
.lumina-presence-dot-live {{
  display: inline-block; width: 11px; height: 11px; border-radius: 999px;
  margin-right: 10px; vertical-align: middle;
  background: #34d399; animation: luminaPresencePulse 2.1s ease-in-out infinite;
}}
.lumina-presence-dot-idle {{
  display: inline-block; width: 11px; height: 11px; border-radius: 999px;
  margin-right: 10px; vertical-align: middle;
  background: #64748b; opacity: 0.9;
}}
@keyframes luminaPresencePulse {{
  0%, 100% {{ opacity: 0.82; transform: scale(0.94); box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.5); }}
  50% {{ opacity: 1; transform: scale(1); box-shadow: 0 0 0 10px rgba(52, 211, 153, 0); }}
}}
</style>
<div style="display:flex; align-items:center; gap:12px; padding:8px 14px; border-radius:12px; background:#0f172a; border:1px solid #334155;">
  <span class="{dot_cls}"></span>
  <strong style="color:#f8fafc; font-size:1.05rem;">{label_txt}</strong>
  <div style="flex:1; color:#94a3b8; font-size:0.9rem;">{mid}</div>
  <div style="text-align:right; min-width:160px;">
    <div style="color:#64748b; font-size:0.75rem;">Training velocity</div>
    <div style="color:#e0f2fe; font-weight:700;">{tpm}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
