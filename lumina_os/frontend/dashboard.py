import time

import requests
import streamlit as st

from global_wisdom_view import render_global_wisdom_tab
from leaderboard_view import render_leaderboard_tab
from evolution_approval import render_evolution_approval_tab


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

    st.markdown("#### Adaptive Regime")
    regime_name = str(health.get("current_regime", "UNKNOWN") or "UNKNOWN")
    regime_risk_state = str(health.get("regime_risk_state", "UNKNOWN") or "UNKNOWN")
    regime_confidence = float(health.get("regime_confidence", 0.0) or 0.0)
    fast_path_weight = float(health.get("fast_path_weight", 0.0) or 0.0)
    override_count = int(health.get("high_risk_override_count", 0) or 0)
    regime_badge = "🔴" if regime_risk_state == "HIGH_RISK" else "🟢"
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Current Regime", f"{regime_badge} {regime_name}")
    g2.metric("Risk State", regime_risk_state)
    g3.metric("Confidence", f"{regime_confidence:.2f}")
    g4.metric("Fast-Path Weight", f"{fast_path_weight:.2f}")
    st.caption(f"High-risk overrides applied for active regime: {override_count}")

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

    st.markdown("#### Regime Metrics")
    current_regime_key = f'lumina_regime_confidence{{regime="{regime_name}"}}'
    current_fast_path_key = f'lumina_regime_fast_path_weight{{regime="{regime_name}"}}'
    current_override_key = f'lumina_regime_high_risk_overrides_total{{regime="{regime_name}"}}'
    m1, m2, m3 = st.columns(3)
    m1.metric("Regime Confidence", f"{_val(current_regime_key, regime_confidence):.2f}")
    m2.metric("Fast-Path Weight", f"{_val(current_fast_path_key, fast_path_weight):.2f}")
    m3.metric("High-Risk Overrides", f"{int(_val(current_override_key, float(override_count)))}")

    # Regime flip history timeline
    try:
        hist_resp = requests.get(
            f"{base_url}/api/monitoring/regime/history",
            headers=headers,
            timeout=5,
        )
        if hist_resp.ok:
            hist_rows = hist_resp.json()
            # Keep only active-transition rows (value == 1.0)
            active_rows = [r for r in hist_rows if r.get("value") == 1.0]
            if active_rows:
                import pandas as pd  # noqa: PLC0415

                flip_df = pd.DataFrame(
                    [
                        {
                            "Time (UTC)": pd.to_datetime(r["ts"], unit="s", utc=True),
                            "Regime": (r.get("labels") or {}).get("regime", "?"),
                            "Risk State": (r.get("labels") or {}).get("risk_state", "?"),
                        }
                        for r in active_rows
                    ]
                ).sort_values("Time (UTC)", ascending=False)

                with st.expander(f"Regime Flip History ({len(flip_df)} events)", expanded=False):
                    st.dataframe(flip_df, use_container_width=True)
    except Exception:
        pass  # history is best-effort; never crash the dashboard

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

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🏆 Live Leaderboard",
        "📚 Global Community Bibles",
        "📊 Observability",
        "🔄 Evolution Approvals",
    ]
)

with tab1:
    render_leaderboard_tab(api_base_url)

with tab2:
    render_global_wisdom_tab(api_base_url)

with tab3:
    _render_observability_tab(api_base_url)

with tab4:
    render_evolution_approval_tab(api_base_url)

st.info("Upload your trades, Bibles or reflections via the bot webhook -> everything appears here instantly.")


