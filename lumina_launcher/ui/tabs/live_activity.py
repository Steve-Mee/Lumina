"""
UI Tabs - Live Activity Panel
Restored and improved version of the original live heartbeat + log tail.
"""

import streamlit as st
from pathlib import Path


def _tail_file(path: Path, max_chars: int = 6000) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]
    except Exception:
        return ""


def render_live_activity_tab(launcher_root: Path, alive: bool = False, pid: int | None = None) -> None:
    st.subheader("📡 Live Activity & Heartbeat")

    LUMINA_LOG_PATH = launcher_root / "logs" / "lumina_full_log.csv"
    STATE_PATH = launcher_root / "state" / "lumina_sim_state.json"

    # === Status Header ===
    col_status, col_pid = st.columns([2, 1])
    with col_status:
        status = "🟢 **Running**" if alive else "🔴 **Stopped**"
        st.markdown(f"**Bot Status:** {status}")
    with col_pid:
        if pid:
            st.markdown(f"**PID:** `{pid}`")
        else:
            st.markdown("**PID:** —")

    # === Heartbeat Cards (more accurate) ===
    st.markdown("#### Heartbeat Status")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Log Heartbeat", "Live" if alive else "Stale")
    with col2:
        state_exists = STATE_PATH.exists()
        st.metric("Runtime State", "Updated" if state_exists else "Missing")
    with col3:
        st.metric("Process Alive", "Yes" if alive else "No")

    # === Log Tail ===
    st.markdown("#### Recent Log Activity (tail)")

    log_tail = _tail_file(LUMINA_LOG_PATH, max_chars=10000)

    if log_tail:
        with st.container(border=True):
            st.code(log_tail, language="text")
            st.caption(f"Showing last ~{len(log_tail)} characters from `{LUMINA_LOG_PATH.name}`")
    else:
        st.info("Nog geen logs gevonden. Start de bot om activiteit te zien in `logs/lumina_full_log.csv`.")

    # === Quick Actions ===
    st.markdown("#### Quick Actions")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("🔄 Refresh Logs", width="stretch"):
            st.rerun()

    with col_b:
        if st.button("📋 Copy Last 50 Lines", width="stretch"):
            if log_tail:
                lines = log_tail.strip().splitlines()[-50:]
                st.code("\n".join(lines))
            else:
                st.warning("Geen logs om te kopiëren.")

    with col_c:
        if st.button("🗑️ Clear View", width="stretch"):
            st.info("Weergave geleegd (logs op schijf blijven bestaan).")
            st.rerun()

    st.caption("Live Activity tab — Fase 2 (Feature Restoration)")
