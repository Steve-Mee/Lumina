import time

import requests
import streamlit as st

from global_wisdom_view import render_global_wisdom_tab
from leaderboard_view import render_leaderboard_tab


# ── Observability tab ─────────────────────────────────────────────────────────


def _render_observability_tab(base_url: str) -> None:
    st.subheader("Real-Time System Observability")

    api_key = st.text_input(
        "API Key (required for JSON metrics)",
        type="password",
        key="obs_api_key",
    )
    auto_refresh = st.checkbox("Auto-refresh every 10 s", value=False)
    if auto_refresh:
        time.sleep(10)
        st.rerun()

    col_health, col_refresh = st.columns([4, 1])
    with col_refresh:
        if st.button("🔄 Refresh Now"):
            st.rerun()

    # Health check (no auth required)
    try:
        health_resp = requests.get(f"{base_url}/api/monitoring/health", timeout=3)
        health = health_resp.json() if health_resp.ok else {}
    except Exception:
        health = {}

    status = health.get("status", "unknown")
    status_color = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(status, "⚪")
    with col_health:
        st.markdown(f"**System Status:** {status_color} `{status.upper()}`")

    if health.get("issues"):
        st.warning("Active issues: " + ", ".join(health["issues"]))

    c1, c2, c3 = st.columns(3)
    c1.metric("Uptime", f"{health.get('uptime_s', 0):.0f} s")
    c2.metric("Kill Switch", "🚨 ACTIVE" if health.get("kill_switch_active") else "✅ Off")
    c3.metric(
        "WebSocket",
        "✅ Connected" if health.get("websocket_connected", True) else "🔌 Down",
    )

    st.divider()

    # JSON metrics snapshot (requires API key)
    if not api_key:
        st.info("Enter your API key above to view detailed metrics.")
        return

    headers = {"X-API-Key": api_key}
    try:
        snap_resp = requests.get(
            f"{base_url}/api/monitoring/metrics/json", headers=headers, timeout=5
        )
        if not snap_resp.ok:
            st.error(f"Metrics fetch failed: HTTP {snap_resp.status_code}")
            return
        snap: dict = snap_resp.json()
    except Exception as exc:
        st.error(f"Cannot reach observability endpoint: {exc}")
        return

    snap.pop("_meta", None)

    def _val(key: str, default: float = 0.0) -> float:
        entry = snap.get(key) or {}
        return float(entry.get("value", default))

    st.markdown("#### PnL")
    p1, p2, p3 = st.columns(3)
    p1.metric("Daily PnL", f"${_val('lumina_pnl_daily'):.2f}")
    p2.metric("Unrealized PnL", f"${_val('lumina_pnl_unrealized'):.2f}")
    p3.metric("Total PnL", f"${_val('lumina_pnl_total'):.2f}")

    st.markdown("#### Risk Controller")
    r1, r2 = st.columns(2)
    r1.metric("Daily PnL (risk)", f"${_val('lumina_risk_daily_pnl'):.2f}")
    r2.metric("Consecutive Losses", f"{int(_val('lumina_risk_consecutive_losses'))}")

    st.markdown("#### Self-Evolution")
    e1, e2, e3 = st.columns(3)
    e1.metric("Proposals", f"{int(_val('lumina_evolution_proposals_total'))}")
    e2.metric("Acceptances", f"{int(_val('lumina_evolution_acceptances_total'))}")
    e3.metric(
        "Acceptance Rate",
        f"{_val('lumina_evolution_acceptance_rate') * 100:.1f}%",
    )
    st.metric("Last Confidence", f"{_val('lumina_evolution_last_confidence'):.1f}")

    st.markdown("#### Alerts & Chaos Events")
    a1, a2 = st.columns(2)
    alerts_total = sum(
        float((v or {}).get("value", 0))
        for k, v in snap.items()
        if k.startswith("lumina_alerts_sent_total")
    )
    chaos_total = sum(
        float((v or {}).get("value", 0))
        for k, v in snap.items()
        if k.startswith("lumina_chaos_events_total")
    )
    a1.metric("Alerts Sent (session)", f"{int(alerts_total)}")
    a2.metric("Chaos Events (session)", f"{int(chaos_total)}")

    with st.expander("Raw Prometheus /metrics"):
        try:
            prom_resp = requests.get(f"{base_url}/api/monitoring/metrics", timeout=5)
            if prom_resp.ok:
                st.code(prom_resp.text, language="text")
            else:
                st.warning(f"HTTP {prom_resp.status_code}")
        except Exception as exc:
            st.warning(str(exc))


# ── Page layout ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="LUMINA OS", layout="wide")
st.title("LUMINA OS – Trader League + Community Wisdom")

api_base_url = "http://localhost:8000"

tab1, tab2, tab3 = st.tabs(
    ["🏆 Live Leaderboard", "📚 Global Community Bibles", "📊 Observability"]
)

with tab1:
    render_leaderboard_tab(api_base_url)

with tab2:
    render_global_wisdom_tab(api_base_url)

with tab3:
    _render_observability_tab(api_base_url)

st.info("Upload your trades, Bibles or reflections via the bot webhook -> everything appears here instantly.")


