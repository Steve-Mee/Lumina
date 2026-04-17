import subprocess
import sys
import time
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st
import yaml

from lumina_core.engine.sim_stability_checker import format_stability_report, generate_stability_report

from global_wisdom_view import render_global_wisdom_tab
from leaderboard_view import render_leaderboard_tab
from evolution_approval import render_evolution_approval_tab


STATE_DIR = Path("state")
LAST_RUN_SUMMARY_PATH = STATE_DIR / "last_run_summary.json"
EVOLUTION_LOG_PATH = STATE_DIR / "evolution_log.jsonl"
RUNTIME_STATE_PATH = STATE_DIR / "lumina_sim_state.json"
HISTORY_PATH = STATE_DIR / "sim_stability_history.jsonl"
ENV_PATH = Path(".env")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _linear_trend(values: list[float]) -> list[float]:
    if len(values) < 2:
        return values[:]
    n = float(len(values))
    xs = list(range(len(values)))
    sum_x = float(sum(xs))
    sum_y = float(sum(values))
    sum_xx = float(sum(x * x for x in xs))
    sum_xy = float(sum(x * y for x, y in zip(xs, values)))
    denom = (n * sum_xx) - (sum_x * sum_x)
    if abs(denom) <= 1e-9:
        return [float(values[0])] * len(values)
    slope = ((n * sum_xy) - (sum_x * sum_y)) / denom
    intercept = (sum_y - (slope * sum_x)) / n
    return [float((slope * x) + intercept) for x in xs]


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _append_or_replace_env(path: Path, key: str, value: str) -> None:
    merged: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            merged[k.strip()] = v.strip()
    merged[key] = value
    content = "\n".join(f"{k}={v}" for k, v in sorted(merged.items())) + "\n"
    path.write_text(content, encoding="utf-8")


def _parse_ts(raw_value: Any) -> datetime | None:
    if not raw_value:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_evolution_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    rows.sort(key=lambda row: _parse_ts(row.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
    return rows


def _resolve_mode() -> str:
    env_mode = str(os.getenv("LUMINA_MODE", "")).strip().lower()
    if env_mode in {"sim", "paper", "real"}:
        return env_mode
    cfg = _load_yaml_dict(Path("config.yaml"))
    config_mode = str(cfg.get("mode", "sim")).strip().lower()
    return config_mode if config_mode in {"sim", "paper", "real"} else "sim"


def _window_metrics(summary: dict[str, Any], rows: list[dict[str, Any]], window_days: int) -> dict[str, float]:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=window_days)
    filtered = [r for r in rows if (_parse_ts(r.get("timestamp")) or now_utc) >= cutoff]

    pnl = _safe_float(summary.get("pnl_realized"))
    trades = _safe_int(summary.get("total_trades"))
    wins = _safe_int(summary.get("wins"))
    sharpe_values: list[float] = []
    summary_sharpe = _safe_float(summary.get("sharpe_annualized"), default=0.0)
    if summary_sharpe != 0.0:
        sharpe_values.append(summary_sharpe)
    risk_events = _safe_int(summary.get("risk_events"))

    for row in filtered:
        meta = row.get("meta_review") if isinstance(row.get("meta_review"), dict) else {}
        pnl += _safe_float(meta.get("net_pnl"))
        row_trades = _safe_int(meta.get("trades"))
        row_wins = _safe_int(meta.get("wins"))
        trades += row_trades
        wins += row_wins
        row_sharpe = _safe_float(meta.get("sharpe"), default=0.0)
        if row_sharpe != 0.0:
            sharpe_values.append(row_sharpe)
        risk_events += _safe_int(row.get("risk_events"))

    win_rate = (wins / trades) if trades > 0 else 0.0
    sharpe = (sum(sharpe_values) / len(sharpe_values)) if sharpe_values else 0.0
    expectancy = (pnl / trades) if trades > 0 else 0.0
    return {
        "pnl": pnl,
        "win_rate": win_rate,
        "sharpe": sharpe,
        "expectancy": expectancy,
        "risk_events": float(risk_events),
    }


def _compute_daily_expectancy(rows: list[dict[str, Any]], summary: dict[str, Any]) -> list[float]:
    buckets: dict[str, dict[str, float]] = {}
    for row in rows:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        day_key = ts.date().isoformat()
        slot = buckets.setdefault(day_key, {"pnl": 0.0, "trades": 0.0})
        meta = row.get("meta_review") if isinstance(row.get("meta_review"), dict) else {}
        slot["pnl"] += _safe_float(meta.get("net_pnl"))
        slot["trades"] += float(_safe_int(meta.get("trades")))

    summary_day = _parse_ts(summary.get("finished_at") or summary.get("started_at"))
    if summary_day is None:
        summary_day = datetime.now(timezone.utc)
    day_key = summary_day.date().isoformat()
    slot = buckets.setdefault(day_key, {"pnl": 0.0, "trades": 0.0})
    slot["pnl"] += _safe_float(summary.get("pnl_realized"))
    slot["trades"] += float(_safe_int(summary.get("total_trades")))

    sorted_days = sorted(buckets.keys(), reverse=True)
    expectancies: list[float] = []
    for day in sorted_days[:5]:
        trades = buckets[day]["trades"]
        expectancy = (buckets[day]["pnl"] / trades) if trades > 0 else 0.0
        expectancies.append(expectancy)
    return expectancies


def _proposal_table(rows: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    proposals = [row for row in rows if str(row.get("status", "")).lower() == "proposed" or isinstance(row.get("proposal"), dict)]
    latest = list(reversed(proposals))[:5]
    data: list[dict[str, Any]] = []
    for row in latest:
        best_candidate = row.get("best_candidate") if isinstance(row.get("best_candidate"), dict) else {}
        score = _safe_float(best_candidate.get("score"))
        confidence = _safe_float((row.get("proposal") or {}).get("confidence"))
        data.append(
            {
                "timestamp": row.get("timestamp", "n/a"),
                "candidate": best_candidate.get("name", "n/a"),
                "score": round(score, 4),
                "confidence": round(confidence, 2),
            }
        )
    return len(proposals), data


def _load_stability_history() -> list[dict[str, Any]]:
    """Load state/sim_stability_history.jsonl; rows sorted ascending by day."""
    if not HISTORY_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    rows.sort(key=lambda r: str(r.get("day", "")))
    return rows


def _render_sim_evolution_dashboard_tab() -> None:
    st.subheader("🚀 SIM Evolution Dashboard")

    # ── Load data ──────────────────────────────────────────────────────────────
    history_rows = _load_stability_history()
    report = generate_stability_report()
    consecutive = int(report.get("consecutive_green_days", 0))
    days_to_green = int(report.get("days_to_green", 5))
    history_count = int(report.get("history_row_count", len(history_rows)))
    criteria = report.get("criteria") if isinstance(report.get("criteria"), dict) else {}
    failures = report.get("failures", []) if isinstance(report.get("failures"), list) else []
    is_green = bool(report.get("READY_FOR_REAL", False))
    status_label = str(report.get("status", "RED")).strip().upper()
    sharpe_crit = criteria.get("extended_run_sharpe", {}) if isinstance(criteria.get("extended_run_sharpe"), dict) else {}
    latest_sharpe = _safe_float(sharpe_crit.get("latest_sharpe", 0.0))

    # ── Stability summary banner ──────────────────────────────────────────────
    summary_color = "#16a34a" if is_green else "#dc2626"
    summary_failures = "none" if not failures else ", ".join(str(x) for x in failures)
    st.markdown(
        f"<div style='padding:10px 14px;border-radius:10px;border:1px solid {summary_color};"
        f"background:{summary_color}14;'><strong>Latest stability_report:</strong> "
        f"<span style='color:{summary_color};font-weight:700;'>{status_label}</span> "
        f"| failures: {summary_failures}</div>",
        unsafe_allow_html=True,
    )

    # ── Streak banner ──────────────────────────────────────────────────────────
    if is_green:
        st.success(f"✅ READY FOR REAL — {consecutive}/5 consecutive positive-expectancy days achieved!")
    elif consecutive >= 3:
        st.warning(f"🟡 {consecutive} / 5 consecutive positive-expectancy days — {days_to_green} more needed")
    else:
        st.error(f"🔴 {consecutive} / 5 consecutive positive-expectancy days — {days_to_green} more needed")
    st.markdown(f"### {consecutive} / 5 consecutive positive expectancy days")
    st.progress(min(max(consecutive / 5.0, 0.0), 1.0))

    # ── Summary metrics ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "🟢 Streak Days",
        f"{consecutive} / 5",
        delta="✅ READY" if is_green else f"-{days_to_green} to REAL",
    )
    c2.metric("Days to REAL", days_to_green)
    c3.metric(
        "Latest Sharpe",
        f"{latest_sharpe:.4f}",
        delta="✅ > 1.8" if latest_sharpe > 1.8 else "❌ < 1.8",
    )
    c4.metric("History Rows", history_count)

    # ── Charts: rolling Sharpe + evolution proposals ───────────────────────────
    if history_rows:
        tail = history_rows[-7:]
        day_labels = [str(r.get("day", "")) for r in tail]
        sharpes = [_safe_float(r.get("sharpe_annualized")) for r in tail]
        proposals = [float(_safe_int(r.get("evolution_proposals"))) for r in tail]
        proposal_trend = _linear_trend(proposals)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("##### 📈 Rolling Sharpe (last 7 days)")
            df_sharpe = pd.DataFrame(
                {"Sharpe": sharpes, "Threshold 1.8": [1.8] * len(sharpes)},
                index=day_labels,
            )
            st.line_chart(df_sharpe, height=200)

        with chart_col2:
            st.markdown("##### 🧬 Evolution Proposals Trend (last 7 days)")
            df_props = pd.DataFrame(
                {"Proposals": proposals, "Trend": proposal_trend},
                index=day_labels,
            )
            st.line_chart(df_props, height=200)
    else:
        st.info("No history data yet — run a SIM to start accumulating daily records.")

    # ── Criteria scorecard ─────────────────────────────────────────────────────
    st.markdown("#### 🎯 REAL Readiness Criteria")
    exp = criteria.get("positive_expectancy_5d", {}) if isinstance(criteria.get("positive_expectancy_5d"), dict) else {}
    consistent = criteria.get("consistent_sharpe", {}) if isinstance(criteria.get("consistent_sharpe"), dict) else {}
    risk = criteria.get("zero_risk_and_var", {}) if isinstance(criteria.get("zero_risk_and_var"), dict) else {}
    trend = criteria.get("evolution_proposals_trend", {}) if isinstance(criteria.get("evolution_proposals_trend"), dict) else {}

    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    sc1.metric(
        "5d Expectancy",
        "✅ PASS" if exp.get("ok") else "❌ FAIL",
        delta=f"streak {exp.get('streak_days', 0)}/{exp.get('required_days', 5)}",
    )
    sc2.metric(
        "Extended Sharpe",
        "✅ PASS" if sharpe_crit.get("ok") else "❌ FAIL",
        delta=f"{_safe_float(sharpe_crit.get('latest_sharpe')):.3f}",
    )
    sc3.metric(
        "Consistent Sharpe",
        "✅ PASS" if consistent.get("ok") else "❌ FAIL",
        delta=f"avg {_safe_float(consistent.get('average_sharpe')):.3f} ({int(consistent.get('available_runs', 0))}/5 runs)",
    )
    sc4.metric(
        "Zero Risk / VaR",
        "✅ PASS" if risk.get("ok") else "❌ FAIL",
        delta=f"events={risk.get('total_risk_events', 0)}",
    )
    sc5.metric(
        "Proposal Trend",
        "✅ PASS" if trend.get("ok") else "❌ FAIL",
        delta=f"7d={_safe_float(trend.get('slope_7d')):.2f}",
    )

    if failures:
        st.warning("⚠️ Failing criteria: " + ", ".join(failures))
    missing = report.get("missing_days_7d", []) if isinstance(report.get("missing_days_7d"), list) else []
    if missing:
        st.caption("📅 Missing days in rolling 7d window: " + ", ".join(str(d) for d in missing))

    with st.expander("📋 Full Stability Report", expanded=False):
        st.code(format_stability_report(report), language="text")

    # ── Action buttons ─────────────────────────────────────────────────────────
    st.markdown("#### ⚙️ Actions")
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    with btn_col1:
        if st.button(
            "🚀 Run Aggressive Overnight SIM",
            type="primary",
            width='stretch',
            help="Launches: --headless --mode=sim --duration=240 --overnight-sim --stability-check",
        ):
            cmd = [
                sys.executable, "-m", "lumina_launcher",
                "--headless", "--mode=sim", "--duration=240",
                "--overnight-sim", "--stability-check",
            ]
            proc = subprocess.Popen(cmd, cwd=str(Path(".").resolve()), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            st.success(f"✅ Overnight SIM launched (PID {proc.pid}). Results appear in state/test_runs/ on completion.")

    with btn_col2:
        if st.button(
            "🔍 Check Stability Now",
            width='stretch',
            help="Re-generates the stability report from all available SIM summaries",
        ):
            st.rerun()

    with btn_col3:
        confirm = st.checkbox("✅ I confirm switch to REAL mode", key="confirm_real_switch_evo")
        go_live_enabled = is_green and confirm
        if st.button(
            "🔴 Switch to REAL Mode",
            type="primary",
            width='stretch',
            disabled=not go_live_enabled,
            help="Only active when READY_FOR_REAL=True and operator confirmation is ticked above",
        ):
            _append_or_replace_env(ENV_PATH, "LUMINA_MODE", "real")
            st.success("✅ Stability GREEN + confirmed. LUMINA_MODE=real written to .env. Restart Streamlit to activate.")

    if not is_green:
        st.info(f"🔒 REAL mode locked until 5 consecutive positive-expectancy days. Progress: {consecutive}/5.")

    # ── Latest run summary ─────────────────────────────────────────────────────
    with st.expander("📄 Latest SIM Run Summary", expanded=False):
        summary = _load_json_dict(LAST_RUN_SUMMARY_PATH)
        if summary:
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Trades", _safe_int(summary.get("total_trades")))
            s2.metric("PnL", f"${_safe_float(summary.get('pnl_realized')):.2f}")
            s3.metric("Sharpe", f"{_safe_float(summary.get('sharpe_annualized')):.4f}")
            s4.metric("Win Rate", f"{_safe_float(summary.get('win_rate')) * 100:.1f}%")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Duration", f"{_safe_float(summary.get('duration_minutes')):.0f}m")
            d2.metric("Max Drawdown", f"${_safe_float(summary.get('max_drawdown')):.2f}")
            d3.metric("Risk Events", _safe_int(summary.get("risk_events")))
            d4.metric("Evolution Proposals", _safe_int(summary.get("evolution_proposals")))
        else:
            st.info("No run summary found yet.")


def _render_real_operations_dashboard_tab() -> None:
    st.subheader("REAL Operations Dashboard")
    summary = _load_json_dict(LAST_RUN_SUMMARY_PATH)
    rows = _load_evolution_rows(EVOLUTION_LOG_PATH)
    runtime_state = _load_json_dict(RUNTIME_STATE_PATH)

    m24 = _window_metrics(summary, rows, 1)
    m7 = _window_metrics(summary, rows, 7)
    m30 = _window_metrics(summary, rows, 30)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Realized PnL", f"${_safe_float(summary.get('pnl_realized')):.2f}")
    c2.metric("Max Drawdown", f"${_safe_float(summary.get('max_drawdown')):.2f}")
    c3.metric("Risk Events", _safe_int(summary.get("risk_events")))
    c4.metric("VaR Breaches", _safe_int(summary.get("var_breach_count")))

    p1, p2, p3 = st.columns(3)
    p1.metric("24h PnL", f"${m24['pnl']:.2f}")
    p2.metric("7d PnL", f"${m7['pnl']:.2f}")
    p3.metric("30d PnL", f"${m30['pnl']:.2f}")

    s1, s2, s3 = st.columns(3)
    s1.metric("Winrate", f"{_safe_float(summary.get('win_rate')) * 100:.2f}%")
    s2.metric("Sharpe", f"{_safe_float(summary.get('sharpe_annualized')):.2f}")
    s3.metric("Session Guard Blocks", _safe_int(summary.get("session_guard_blocks")))

    st.markdown("#### Exposure")
    e1, e2, e3 = st.columns(3)
    e1.metric("Live Position Qty", _safe_int(runtime_state.get("live_position_qty")))
    e2.metric("Pending Reconciliations", len(runtime_state.get("pending_trade_reconciliations", []) or []))
    e3.metric("Total Trades", _safe_int(summary.get("total_trades")))

    st.markdown("#### Capital Preservation Protocol")
    risk_events_ok = _safe_int(summary.get("risk_events")) == 0
    var_ok = _safe_int(summary.get("var_breach_count")) == 0
    drawdown_ok = _safe_float(summary.get("max_drawdown")) <= 500.0
    sharpe_ok = _safe_float(summary.get("sharpe_annualized")) >= 1.0
    pnl_24h_ok = m24["pnl"] >= 0.0
    protocol_green = risk_events_ok and var_ok and drawdown_ok and sharpe_ok and pnl_24h_ok

    g1, g2, g3, g4, g5 = st.columns(5)
    g1.metric("Risk Events = 0", "PASS" if risk_events_ok else "FAIL")
    g2.metric("VaR Breaches = 0", "PASS" if var_ok else "FAIL")
    g3.metric("Drawdown <= $500", "PASS" if drawdown_ok else "FAIL")
    g4.metric("Sharpe >= 1.0", "PASS" if sharpe_ok else "FAIL")
    g5.metric("24h PnL >= 0", "PASS" if pnl_24h_ok else "FAIL")

    if protocol_green:
        st.success("REAL protocol GREEN: system is within capital-preservation bounds.")
    else:
        st.error("REAL protocol RED: immediate operator review required.")


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
                    st.dataframe(flip_df, width='stretch')
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

runtime_mode = _resolve_mode()

tab_labels = [
    "🏆 Live Leaderboard",
    "📚 Global Community Bibles",
    "📊 Observability",
    "🔄 Evolution Approvals",
]
if runtime_mode == "sim":
    tab_labels.append("🚀 SIM Evolution Dashboard")
if runtime_mode == "real":
    tab_labels.append("🛡️ REAL Operations Dashboard")

tabs = st.tabs(tab_labels)
tab1 = tabs[0]
tab2 = tabs[1]
tab3 = tabs[2]
tab4 = tabs[3]
tab5 = tabs[4] if len(tabs) > 4 else None

with tab1:
    render_leaderboard_tab(api_base_url)

with tab2:
    render_global_wisdom_tab(api_base_url)

with tab3:
    _render_observability_tab(api_base_url)

with tab4:
    render_evolution_approval_tab(api_base_url)

if tab5 is not None:
    with tab5:
        if runtime_mode == "sim":
            _render_sim_evolution_dashboard_tab()
        elif runtime_mode == "real":
            _render_real_operations_dashboard_tab()

st.info("Upload your trades, Bibles or reflections via the bot webhook -> everything appears here instantly.")


