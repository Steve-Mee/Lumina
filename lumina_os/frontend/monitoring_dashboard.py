from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import requests
import streamlit as st
import yaml

from lumina_core.first_boot_progress import (
    resolve_first_boot_completed_trades,
    resolve_first_boot_stage,
    resolve_first_boot_target_trades,
)
from lumina_os.frontend.dashboard_views import (
    DashboardPaths,
    embedded_react_ui_status,
    resolve_workspace_root_from_this_module,
)
from lumina_os.frontend.http_utils import (
    is_backend_unreachable,
    log_fetch_failure,
    resolve_dashboard_api_key,
)

_LOG = logging.getLogger(__name__)

_ACTIVE_TRAINING_STAGES = frozenset(
    {
        "detected",
        "loading_data",
        "training_running",
        "pipeline_boot",
        "parallel_simulation",
        "ppo_training",
    }
)


@dataclass(frozen=True)
class _MonitoringPaths:
    workspace_root: Path
    state_dir: Path
    logs_dir: Path
    journal_sim_dir: Path
    first_boot_progress: Path
    first_boot_legacy_progress: Path
    first_boot_flag: Path
    first_boot_legacy_flag: Path
    policy_zip: Path
    ppo_policy_metadata: Path
    approval_twin_model: Path
    twin_decisions: Path
    twin_training: Path
    shadow_runs: Path
    runtime_metrics: Path
    gate_rejections: Path
    reasoning_latency: Path
    model_load_times: Path
    daily_pnl_history: Path
    debug_training_process: Path
    structured_errors: Path
    full_log: Path
    sim_state: Path
    config_yaml: Path
    embedded_ui_index: Path

    @classmethod
    def resolve(cls, workspace_root: Path | None = None) -> _MonitoringPaths:
        root = (workspace_root or resolve_workspace_root_from_this_module()).resolve()
        dp = DashboardPaths(root)
        state = dp.state_dir
        return cls(
            workspace_root=root,
            state_dir=state,
            logs_dir=root / "logs",
            journal_sim_dir=root / "journal" / "simulator",
            first_boot_progress=state / "lumina_birth_progress.json",
            first_boot_legacy_progress=state / "first_boot_progress.json",
            first_boot_flag=state / "lumina_birth_completed.flag",
            first_boot_legacy_flag=state / "first_boot_completed.flag",
            policy_zip=root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip",
            ppo_policy_metadata=state / "ppo_policy_metadata.json",
            approval_twin_model=state / "approval_twin_model.json",
            twin_decisions=state / "monitoring_twin_decisions.jsonl",
            twin_training=state / "monitoring_twin_training.jsonl",
            shadow_runs=state / "evolution_shadow_runs.json",
            runtime_metrics=state / "monitoring_runtime_metrics.json",
            gate_rejections=state / "monitoring_gate_rejections.jsonl",
            reasoning_latency=state / "monitoring_reasoning_latency.jsonl",
            model_load_times=state / "monitoring_model_load_times.jsonl",
            daily_pnl_history=state / "monitoring_daily_pnl.jsonl",
            debug_training_process=state / "monitoring_debug_training_process.json",
            structured_errors=root / "logs" / "structured_errors.jsonl",
            full_log=root / "logs" / "lumina_full_log.csv",
            sim_state=dp.runtime_state,
            config_yaml=dp.config_yaml,
            embedded_ui_index=dp.embedded_ui_index,
        )


def _render_dark_series_chart(
    values: list[float],
    *,
    y_col: str,
    y_title: str,
    color: str = "#00f0ff",
    height: int = 180,
) -> None:
    if not values:
        return
    frame = pd.DataFrame({"idx": list(range(len(values))), y_col: values})
    chart = (
        alt.Chart(frame)
        .mark_line(color=color, strokeWidth=2.2)
        .encode(
            x=alt.X("idx:Q", axis=alt.Axis(labelColor="#94a3b8", title=None)),
            y=alt.Y(f"{y_col}:Q", title=y_title, axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8")),
            tooltip=["idx", y_col],
        )
        .properties(height=height)
        .configure(background="#0f1118")
        .configure_view(strokeOpacity=0, fill="#0f1118")
        .configure_axis(gridColor="#1f2937")
    )
    st.altair_chart(chart, use_container_width=True)


def _render_dark_log_text(text: str, *, height_px: int = 260) -> None:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"""
<div style="
  background: rgba(11, 14, 20, 0.92);
  border: 1px solid rgba(0, 240, 255, 0.18);
  border-radius: 12px;
  padding: 12px;
  min-height: {height_px}px;
  max-height: {height_px}px;
  overflow: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 0.78rem;
  color: #b6c2d3;
  white-space: pre-wrap;
">{escaped}</div>
""",
        unsafe_allow_html=True,
    )


def _first_boot_completion_display(paths: _MonitoringPaths, progress: dict[str, Any]) -> tuple[str, str]:
    """Show Yes only when first boot truly finished; In progress while training runs.

    progress ``stage`` wins over a stale completion flag
    so the dashboard does not show Yes during detected/loading/training.
    """
    stage = str(progress.get("stage", "")).strip().lower()
    # BIRTH ENGINE 2026-05-17
    if stage in _ACTIVE_TRAINING_STAGES:
        return "In progress", "n/a"
    if stage in {"completed", "completed_waiting_user_action"}:
        ts = (
            paths.first_boot_flag.read_text(encoding="utf-8").strip()
            if paths.first_boot_flag.exists()
            else (
                paths.first_boot_legacy_flag.read_text(encoding="utf-8").strip()
                if paths.first_boot_legacy_flag.exists()
                else str(progress.get("timestamp", "n/a"))
            )
        )
        return "Yes", ts
    if stage == "failed":
        return "Failed", "n/a"
    if stage == "deferred_calendar":
        return "Deferred", "n/a"
    # Idle / normale herstart: alleen Yes als zowel vlag als policy er zijn.
    if (paths.first_boot_flag.exists() or paths.first_boot_legacy_flag.exists()) and paths.policy_zip.exists():
        ts = (
            paths.first_boot_flag.read_text(encoding="utf-8").strip()
            if paths.first_boot_flag.exists()
            else paths.first_boot_legacy_flag.read_text(encoding="utf-8").strip()
        )
        return "Yes", ts
    return "No", "n/a"


def _first_boot_progress_fraction(progress: dict[str, Any]) -> float:
    """Prefer simulator-supplied ``progress_pct`` (40–68 during SIM/PPO); else coarse stage."""
    raw = progress.get("progress_pct")
    if raw is not None:
        try:
            pct = float(raw)
            if 0.0 <= pct <= 100.0:
                return pct / 100.0
        except (TypeError, ValueError):
            pass
    stage = str(progress.get("stage", "unknown"))
    stage_to_progress = {
        "detected": 10,
        "loading_data": 30,
        "pipeline_boot": 40,
        "parallel_simulation": 60,
        "ppo_training": 82,
        "training_running": 70,
        "completed": 100,
        "completed_waiting_user_action": 100,
        "failed": 100,
    }
    return stage_to_progress.get(stage, 0) / 100.0


def _first_boot_historical_days_display(progress: dict[str, Any]) -> int:
    """Prefer measured ``actual_real_days_loaded`` when historical load finished."""
    for key in ("actual_real_days_loaded", "estimated_real_days"):
        if progress.get(key) is not None:
            return _safe_int(progress.get(key))
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    if limit is not None and limit > 0:
        return rows[-limit:]
    return rows


def _parse_iso(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def _tail_warning_error_logs(log_path: Path, *, limit: int = 100) -> list[str]:
    if not log_path.exists():
        return []
    lines: list[str] = []
    for raw in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if ",WARNING," in line or ",ERROR," in line:
            lines.append(line)
    return lines[-limit:]


def _latest_training_reports(journal_sim_dir: Path, *, limit: int = 10) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    if not journal_sim_dir.is_dir():
        return reports
    # BIRTH ENGINE 2026-05-17
    for path in sorted(
        list(journal_sim_dir.glob("lumina_birth_training_*.json"))
        + list(journal_sim_dir.glob("first_boot_training_*.json"))
    ):
        payload = _load_json(path)
        if payload:
            payload["_run_type"] = "Background"
            payload["_path"] = str(path)
            reports.append(payload)
    for path in sorted(journal_sim_dir.glob("nightly_sim_*.json")):
        payload = _load_json(path)
        if payload:
            ts = _parse_iso(payload.get("timestamp"))
            if ts is not None and ts.weekday() >= 5:
                run_type = "Weekend"
            else:
                run_type = "Daily Maintenance"
            payload["_run_type"] = run_type
            payload["_path"] = str(path)
            reports.append(payload)
    reports.sort(key=lambda r: _parse_iso(r.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return reports[:limit]


def weekly_veto_summary(state_dir: Path | None = None) -> tuple[int, list[tuple[str, int]]]:
    """Weekly veto counts; ``state_dir`` defaults to workspace ``state/`` (for tests pass a temp dir)."""
    base = state_dir or _MonitoringPaths.resolve().state_dir
    veto_jsonl = base / "veto_registry.jsonl"
    veto_db = base / "veto_registry.db"
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    reasons: Counter[str] = Counter()
    count = 0

    if veto_jsonl.exists():
        for row in _load_jsonl(veto_jsonl):
            ts = _parse_iso(row.get("veto_timestamp") or row.get("timestamp"))
            if ts is None or ts < cutoff:
                continue
            count += 1
            reasons[str(row.get("reason", "unknown"))] += 1
        return count, reasons.most_common(5)

    if veto_db.exists():
        try:
            with sqlite3.connect(veto_db) as conn:
                q = """
                SELECT reason, COUNT(*) as c
                FROM veto_records
                WHERE veto_timestamp >= ?
                GROUP BY reason
                ORDER BY c DESC
                LIMIT 5
                """
                rows = conn.execute(q, (cutoff.isoformat(),)).fetchall()
                total_q = "SELECT COUNT(*) FROM veto_records WHERE veto_timestamp >= ?"
                total = conn.execute(total_q, (cutoff.isoformat(),)).fetchone()
                count = int(total[0]) if total else 0
                return count, [(str(r[0]), int(r[1])) for r in rows]
        except Exception:
            return 0, []

    return 0, []


def _weekly_veto_summary(state_dir: Path) -> tuple[int, list[tuple[str, int]]]:
    return weekly_veto_summary(state_dir)


def _progress_data_freshness(paths: _MonitoringPaths, progress: dict[str, Any]) -> str:
    for candidate in (paths.first_boot_progress, paths.first_boot_legacy_progress):
        if candidate.exists():
            try:
                mtime = datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc)
                return f"bestand {mtime.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            except OSError:
                pass
    ts = str(progress.get("timestamp", "")).strip()
    return f"timestamp {ts}" if ts else "geen progress-bestand"


def render_backend_observability_subpanel(base_url: str, api_key: str) -> None:
    """Health (no auth) + detailed metrics when ``api_key`` is set (same as legacy Observability tab)."""
    try:
        health_resp = requests.get(f"{base_url}/api/monitoring/health", timeout=3)
        health = health_resp.json() if health_resp.ok else {}
    except Exception as exc:
        log_fetch_failure(_LOG, "monitoring health fetch failed", exc)
        health = {}

    status = health.get("status", "unknown")
    status_color = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(status, "⚪")
    st.markdown(f"**System Status:** {status_color} `{str(status).upper()}`")
    if health.get("issues"):
        st.warning("Active issues: " + ", ".join(health["issues"]))

    c1, c2, c3 = st.columns(3)
    c1.metric("Uptime", f"{health.get('uptime_s', 0):.0f} s")
    c2.metric("Kill Switch", "🚨 ACTIVE" if health.get("kill_switch_active") else "✅ Off")
    c3.metric("WebSocket", "✅ Connected" if health.get("websocket_connected", True) else "🔌 Down")

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
    if not api_key:
        st.info("Enter an API key above to load JSON metrics, regime history, and Prometheus text.")
        return

    headers = {"X-API-Key": api_key}
    try:
        snap_resp = requests.get(f"{base_url}/api/monitoring/metrics/json", headers=headers, timeout=5)
        if not snap_resp.ok:
            st.error(f"Metrics fetch failed: HTTP {snap_resp.status_code}")
            return
        snap: dict[str, Any] = snap_resp.json()
    except Exception as exc:
        log_fetch_failure(_LOG, "monitoring metrics/json failed", exc)
        if is_backend_unreachable(exc):
            st.info("Backend niet bereikbaar — start `lumina_os\\run_backend.ps1` voor live metrics.")
        else:
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
    e3.metric("Acceptance Rate", f"{_val('lumina_evolution_acceptance_rate') * 100:.1f}%")
    st.metric("Last Confidence", f"{_val('lumina_evolution_last_confidence'):.1f}")

    st.markdown("#### Regime Metrics")
    current_regime_key = f'lumina_regime_confidence{{regime="{regime_name}"}}'
    current_fast_path_key = f'lumina_regime_fast_path_weight{{regime="{regime_name}"}}'
    current_override_key = f'lumina_regime_high_risk_overrides_total{{regime="{regime_name}"}}'
    m1, m2, m3 = st.columns(3)
    m1.metric("Regime Confidence", f"{_val(current_regime_key, regime_confidence):.2f}")
    m2.metric("Fast-Path Weight", f"{_val(current_fast_path_key, fast_path_weight):.2f}")
    m3.metric("High-Risk Overrides", f"{int(_val(current_override_key, float(override_count)))}")

    try:
        hist_resp = requests.get(f"{base_url}/api/monitoring/regime/history", headers=headers, timeout=5)
        if hist_resp.ok:
            hist_rows = hist_resp.json()
            active_rows = [r for r in hist_rows if r.get("value") == 1.0]
            if active_rows:
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
                    st.dataframe(flip_df, width="stretch")
    except Exception as exc:
        log_fetch_failure(_LOG, "regime history fetch failed", exc)

    st.markdown("#### Alerts & Chaos Events")
    a1, a2 = st.columns(2)
    alerts_total = sum(float((v or {}).get("value", 0)) for k, v in snap.items() if k.startswith("lumina_alerts_sent_total"))
    chaos_total = sum(float((v or {}).get("value", 0)) for k, v in snap.items() if k.startswith("lumina_chaos_events_total"))
    a1.metric("Alerts Sent (session)", f"{int(alerts_total)}")
    a2.metric("Chaos Events (session)", f"{int(chaos_total)}")

    with st.expander("Raw Prometheus /metrics"):
        try:
            prom_resp = requests.get(f"{base_url}/api/monitoring/metrics", timeout=5)
            if prom_resp.ok:
                _render_dark_log_text(prom_resp.text, height_px=300)
            else:
                st.warning(f"HTTP {prom_resp.status_code}")
        except Exception as exc:
            st.warning(str(exc))


def _fetch_metrics_json(base_url: str, api_key: str) -> dict[str, Any]:
    if not api_key:
        return {}
    try:
        resp = requests.get(
            f"{base_url}/api/monitoring/metrics/json",
            headers={"X-API-Key": api_key},
            timeout=4,
        )
        if not resp.ok:
            return {}
        payload = resp.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _metric_value(snapshot: dict[str, Any], key: str, default: float = 0.0) -> float:
    item = snapshot.get(key)
    if isinstance(item, dict):
        return _safe_float(item.get("value"), default)
    return default


def _load_debug_process_meta(paths: _MonitoringPaths) -> dict[str, Any]:
    return _load_json(paths.debug_training_process)


def _write_debug_process_meta(paths: _MonitoringPaths, payload: dict[str, Any]) -> None:
    paths.debug_training_process.parent.mkdir(parents=True, exist_ok=True)
    paths.debug_training_process.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _start_debug_training_process(
    paths: _MonitoringPaths,
    command: list[str],
    *,
    label: str,
) -> str:
    try:
        proc = subprocess.Popen(command, cwd=str(paths.workspace_root))
    except Exception as exc:
        return f"Start mislukt: {exc}"
    _write_debug_process_meta(
        paths,
        {
            "pid": int(proc.pid),
            "label": str(label),
            "command": command,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        },
    )
    return f"Gestart: {label} (pid={proc.pid})"


def _stop_debug_training_process(paths: _MonitoringPaths) -> str:
    meta = _load_debug_process_meta(paths)
    pid = _safe_int(meta.get("pid"), 0)
    if pid <= 0:
        return "Geen actieve debug training process gevonden."
    try:
        import psutil  # type: ignore[import-untyped]

        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
    except Exception:
        try:
            os.kill(pid, 15)
        except Exception as exc:
            return f"Stop mislukt voor pid={pid}: {exc}"

    meta["status"] = "stopped"
    meta["stopped_at"] = datetime.now(timezone.utc).isoformat()
    _write_debug_process_meta(paths, meta)
    return f"Gestopt: pid={pid}"


def _host_only_from_request_host(header_val: str) -> str:
    """Strip poort uit HTTP Host-header; ondersteun bracketed IPv6."""
    h = header_val.strip()
    if not h:
        return "localhost"
    if h.startswith("["):
        bracket_end = h.find("]:")
        if bracket_end != -1:
            return h[: bracket_end + 1]
        return h
    if ":" in h:
        return h.rsplit(":", 1)[0]
    return h


def _react_dashboard_url_default() -> str:
    """Zelfde host als de browser gebruikt voor Streamlit (LAN/remote); anders localhost."""
    port = (os.getenv("LUMINA_REACT_DASHBOARD_PORT") or "5173").strip() or "5173"
    host = "localhost"
    try:
        hdrs = st.context.headers
        raw = hdrs.get("Host") if hdrs is not None else None
        if raw is None and hdrs is not None:
            raw = hdrs.get("host")
        if isinstance(raw, str) and raw.strip():
            host = _host_only_from_request_host(raw)
    except Exception:
        pass
    return f"http://{host}:{port}"


def _react_dashboard_link(api_base: str, paths: _MonitoringPaths) -> str:
    """Voorkeur: gebouwde SPA onder FastAPI /ui/; anders Vite-dev URL; override via env."""
    status = embedded_react_ui_status(api_base, DashboardPaths(paths.workspace_root))
    react_url = status.get("react_url")
    if isinstance(react_url, str) and react_url.strip():
        return react_url.strip()
    return _react_dashboard_url_default()


def render_monitoring_dashboard_tab(
    base_url: str,
    *,
    workspace_root: Path | None = None,
    title: str = "Monitoring Dashboard",
) -> None:
    paths = _MonitoringPaths.resolve(workspace_root)
    st.subheader(title)
    react_status = embedded_react_ui_status(base_url, DashboardPaths(paths.workspace_root))
    react_dashboard_url = _react_dashboard_link(base_url, paths)

    top_a, top_b = st.columns([3, 2])
    with top_a:
        reason = str(react_status.get("reason") or "missing_dist")
        if reason == "ok":
            st.caption(
                "React-dashboard wordt meegeleverd via de FastAPI-backend op `/ui/`. "
                "Open de knop rechts of gebruik het React dashboard-tabblad in het command center."
            )
        elif reason == "wrong_base_path":
            st.warning(
                "Embedded React build heeft verkeerde asset-paden. "
                "Voer `scripts/build_embedded_ui.ps1` uit (of `npm run build:embedded` in `frontend/`)."
            )
        elif reason == "explicit_override":
            st.caption("React dashboard URL komt uit `LUMINA_REACT_DASHBOARD_URL`.")
        else:
            st.caption(
                "Geen geldige embedded React build gevonden (`frontend/dist`). "
                "Bouw eenmalig met `scripts/build_embedded_ui.ps1`, of start tijdelijk `npm run dev` (poort 5173). "
                "Zet anders `LUMINA_REACT_DASHBOARD_URL`."
            )
    with top_b:
        if react_dashboard_url:
            st.link_button("Open React Dashboard", react_dashboard_url, use_container_width=True)

    if not str(st.session_state.get("monitoring_api_key", "")).strip():
        resolved = resolve_dashboard_api_key()
        if resolved:
            st.session_state["monitoring_api_key"] = resolved
    api_key = st.text_input("API Key (optional, unlocks live metrics API)", type="password", key="monitoring_api_key")
    st.caption(
        "Auto-refresh staat op command-center niveau (boven de subtabs). "
        f"Workspace: `{paths.workspace_root}`"
    )

    tab_debug, tab_a, tab_b, tab_c, tab_d, tab_e, tab_f, tab_g, tab_h = st.tabs(
        [
            "Debug Controls",
            "A. System Overview",
            "B. First Boot Training Status",
            "C. Training History",
            "D. ApprovalTwin Activity",
            "E. Shadow Deployment",
            "F. Live Trading Metrics",
            "G. System Health & Logs",
            "H. Trends",
        ]
    )

    runtime_snapshot = _load_json(paths.runtime_metrics)
    fallback_runtime_state = _load_json(paths.sim_state)
    first_boot_progress = _load_json(paths.first_boot_progress)
    if not first_boot_progress:
        first_boot_progress = _load_json(paths.first_boot_legacy_progress)
    config_payload = _load_yaml(paths.config_yaml)
    ppo_meta = _load_json(paths.ppo_policy_metadata)
    twin_model = _load_json(paths.approval_twin_model)
    st.caption(f"Laatste progress-data: {_progress_data_freshness(paths, first_boot_progress)}")

    metrics_snapshot_cache: dict[str, Any] | None = None
    training_reports_cache: list[dict[str, Any]] | None = None
    twin_decisions_cache: list[dict[str, Any]] | None = None
    twin_training_cache: list[dict[str, Any]] | None = None
    shadow_runs_cache: dict[str, Any] | None = None
    gate_rows_cache: list[dict[str, Any]] | None = None
    latency_rows_cache: list[dict[str, Any]] | None = None
    model_load_rows_cache: list[dict[str, Any]] | None = None
    structured_errors_cache: list[dict[str, Any]] | None = None

    def _metrics_snapshot() -> dict[str, Any]:
        nonlocal metrics_snapshot_cache
        if metrics_snapshot_cache is None:
            metrics_snapshot_cache = _fetch_metrics_json(base_url, api_key=api_key)
        return metrics_snapshot_cache

    def _training_reports() -> list[dict[str, Any]]:
        nonlocal training_reports_cache
        if training_reports_cache is None:
            training_reports_cache = _latest_training_reports(paths.journal_sim_dir, limit=10)
        return training_reports_cache

    def _twin_decisions() -> list[dict[str, Any]]:
        nonlocal twin_decisions_cache
        if twin_decisions_cache is None:
            twin_decisions_cache = _load_jsonl(paths.twin_decisions, limit=20)
        return twin_decisions_cache

    def _twin_training() -> list[dict[str, Any]]:
        nonlocal twin_training_cache
        if twin_training_cache is None:
            twin_training_cache = _load_jsonl(paths.twin_training, limit=20)
        return twin_training_cache

    def _shadow_runs() -> dict[str, Any]:
        nonlocal shadow_runs_cache
        if shadow_runs_cache is None:
            shadow_runs_cache = _load_json(paths.shadow_runs)
        return shadow_runs_cache

    def _gate_rows() -> list[dict[str, Any]]:
        nonlocal gate_rows_cache
        if gate_rows_cache is None:
            gate_rows_cache = _load_jsonl(paths.gate_rejections, limit=300)
        return gate_rows_cache

    def _latency_rows() -> list[dict[str, Any]]:
        nonlocal latency_rows_cache
        if latency_rows_cache is None:
            latency_rows_cache = _load_jsonl(paths.reasoning_latency, limit=200)
        return latency_rows_cache

    def _model_load_rows() -> list[dict[str, Any]]:
        nonlocal model_load_rows_cache
        if model_load_rows_cache is None:
            model_load_rows_cache = _load_jsonl(paths.model_load_times, limit=100)
        return model_load_rows_cache

    def _structured_errors() -> list[dict[str, Any]]:
        nonlocal structured_errors_cache
        if structured_errors_cache is None:
            structured_errors_cache = _load_jsonl(paths.structured_errors, limit=120)
        return structured_errors_cache

    with tab_debug:
        st.markdown("### Debug Controls")
        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            if st.button("Start nightly training", key="monitoring_start_nightly"):
                msg = _start_debug_training_process(
                    paths,
                    [sys.executable, "-m", "lumina_core.engine.runtime_entrypoint", "--mode", "nightly"],
                    label="nightly_training",
                )
                st.info(msg)
        with dc2:
            if st.button("Start headless SIM training", key="monitoring_start_headless_sim"):
                msg = _start_debug_training_process(
                    paths,
                    [
                        sys.executable,
                        "-m",
                        "lumina_core.engine.runtime_entrypoint",
                        "--mode",
                        "sim",
                        "--headless",
                        "--duration",
                        "120m",
                    ],
                    label="headless_sim_training",
                )
                st.info(msg)
        with dc3:
            if st.button("Stop tracked training", key="monitoring_stop_training"):
                st.info(_stop_debug_training_process(paths))
        proc_meta = _load_debug_process_meta(paths)
        if proc_meta:
            st.caption(
                "Tracked process: "
                f"pid={proc_meta.get('pid', 'n/a')} "
                f"label={proc_meta.get('label', 'n/a')} "
                f"status={proc_meta.get('status', 'unknown')}"
            )

    # A. System Overview
    with tab_a:
        st.markdown("### A. System Overview")
        mode = str(runtime_snapshot.get("mode") or fallback_runtime_state.get("mode") or "SIM").upper()
        first_boot_label, first_boot_ts = _first_boot_completion_display(paths, first_boot_progress)
        training_reports = _training_reports()
        twin_training = _twin_training()
        last_training = training_reports[0] if training_reports else {}
        twin_avg_error = _safe_float((twin_training[-1] if twin_training else {}).get("avg_prediction_error"))
        twin_reward = _safe_float((twin_training[-1] if twin_training else {}).get("reward"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current mode", mode)
        c2.metric("First boot completed", first_boot_label)
        c3.metric("PPO policy version", str(ppo_meta.get("policy_version", "unknown")))
        c4.metric("PPO total training steps", _safe_int(ppo_meta.get("total_training_steps")))
        d1, d2, d3 = st.columns(3)
        d1.metric("Training mode", str(last_training.get("_run_type", "Background")))
        d2.metric("Last training duration (s)", _safe_float(last_training.get("elapsed_sec")))
        d3.metric("ApprovalTwin reward", f"{twin_reward:.3f}")
        st.caption(
            f"First boot timestamp: {first_boot_ts} | "
            f"ApprovalTwin last update: {twin_model.get('last_updated', 'n/a')} | "
            f"ApprovalTwin avg error: {twin_avg_error:.4f}"
        )

    # B. First Boot Training Status
    with tab_b:
        st.markdown("### B. First Boot Training Status")
        stage_key = resolve_first_boot_stage(first_boot_progress)
        if stage_key in _ACTIVE_TRAINING_STAGES:
            st.info(
                "Birth/PPO training actief — deze tab ververst via command-center auto-refresh. "
                "Live trading metrics (tab F/G) verschijnen na runtime start."
            )
        training_reports = _training_reports()
        last_training = training_reports[0] if training_reports else {}
        stage = str(first_boot_progress.get("stage", "unknown"))
        st.progress(_first_boot_progress_fraction(first_boot_progress))
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Stage", stage)
        b2.metric("Historical days (loaded / est.)", _first_boot_historical_days_display(first_boot_progress))
        b3.metric("Real vs synthetic %", f"{_safe_float(last_training.get('synthetic_pct', 0.0)):.2f}% synthetic")
        b4.metric("Trades completed", _safe_int(resolve_first_boot_completed_trades(first_boot_progress)))
        phase = str(first_boot_progress.get("phase") or "").strip() or "n/a"
        pct_raw = first_boot_progress.get("progress_pct")
        pct_note = f"{pct_raw}%" if pct_raw is not None else "—"
        target = resolve_first_boot_target_trades(config_payload)
        st.caption(
            f"Phase: {phase} · detail progress: {pct_note} · "
            f"target: {target:,} · {first_boot_progress.get('message', 'No first boot message available.')}"
        )

    # C. Training History
    with tab_c:
        st.markdown("### C. Training History")
        training_reports = _training_reports()
        history_rows: list[dict[str, Any]] = []
        for run in training_reports:
            sharpe = _safe_float(run.get("mean_worker_sharpe"))
            history_rows.append(
                {
                    "timestamp": str(run.get("timestamp", "")),
                    "window": str(run.get("_run_type", "Background")),
                    "trades": _safe_int(run.get("trades")),
                    "real_data_ratio": round(
                        1.0
                        - (_safe_float(run.get("synthetic_ratio"), 0.0))
                        if run.get("synthetic_ratio") is not None
                        else 1.0,
                        4,
                    ),
                    "duration_s": _safe_float(run.get("elapsed_sec")),
                    "sharpe_improvement": sharpe,
                    "new_bible_rules_hint": "See simulation.bible_rules_appended logs",
                }
            )
        if history_rows:
            hist_df = pd.DataFrame(history_rows)
            st.dataframe(hist_df, width="stretch")
            st.download_button(
                "Export training history (JSON)",
                data=json.dumps(history_rows, indent=2),
                file_name="training_history.json",
                mime="application/json",
            )
        else:
            st.info(
                "Nog geen training history in journal/simulator — verschijnt na een voltooide birth-run "
                f"(`{paths.journal_sim_dir}`)."
            )

    # D. ApprovalTwin Activity
    with tab_d:
        st.markdown("### D. ApprovalTwin Activity")
        twin_decisions = _twin_decisions()
        if twin_decisions:
            decision_rows = [
                {
                    "timestamp": str(d.get("timestamp", "")),
                    "dna_hash": str(d.get("dna_hash", ""))[:12],
                    "score": _safe_float(d.get("score")),
                    "recommendation": "Approve" if bool(d.get("recommendation")) else "Veto",
                    "risk_flags": ", ".join(d.get("risk_flags", []) or []),
                }
                for d in twin_decisions[-20:]
            ]
            st.dataframe(pd.DataFrame(decision_rows), width="stretch")
        else:
            st.info("No twin decision telemetry found yet.")
        veto_count, top_reasons = _weekly_veto_summary(paths.state_dir)
        st.metric("Weekly veto count", veto_count)
        if top_reasons:
            st.write("Top veto reasons:", ", ".join(f"{reason} ({count})" for reason, count in top_reasons[:3]))

    # E. Shadow Deployment
    with tab_e:
        st.markdown("### E. Shadow Deployment")
        shadow_runs = _shadow_runs()
        shadow_values = list(shadow_runs.values()) if isinstance(shadow_runs, dict) else []
        active_shadow = [r for r in shadow_values if str(r.get("status", "")).lower() == "running"]
        promoted = [r for r in shadow_values if str(r.get("status", "")).lower() == "promoted"]
        e1, e2 = st.columns(2)
        e1.metric("Active shadow runs", len(active_shadow))
        e2.metric("Promoted strategies", len(promoted))
        if shadow_values:
            view_rows = []
            for row in shadow_values[-25:]:
                sim_hist = row.get("sim_pnl_history", []) or []
                paper_hist = row.get("paper_pnl_history", []) or []
                view_rows.append(
                    {
                        "dna_hash": str(row.get("dna_hash", ""))[:12],
                        "status": str(row.get("status", "")),
                        "trade_count": _safe_int(row.get("trade_count")),
                        "sim_pnl": _safe_float(row.get("total_sim_pnl")),
                        "paper_pnl": _safe_float(row.get("total_paper_pnl")),
                        "statistical_significance_proxy": round(abs(_safe_float(row.get("total_sim_pnl"))) + len(sim_hist) + len(paper_hist), 3),
                    }
                )
            st.dataframe(pd.DataFrame(view_rows), width="stretch")

    # F. Live Trading Metrics
    with tab_f:
        st.markdown("### F. Live Trading Metrics")
        metrics_snapshot = _metrics_snapshot()
        live_exposure = _safe_int(runtime_snapshot.get("live_position_qty", fallback_runtime_state.get("live_position_qty", 0)))
        daily_pnl = _safe_float(runtime_snapshot.get("daily_pnl", _metric_value(metrics_snapshot, "lumina_risk_daily_pnl", 0.0)))
        consecutive_losses = _safe_int(
            runtime_snapshot.get("consecutive_losses", _metric_value(metrics_snapshot, "lumina_risk_consecutive_losses", 0.0))
        )
        f1, f2, f3 = st.columns(3)
        f1.metric("Current exposure (qty)", live_exposure)
        f2.metric("Daily PnL", f"${daily_pnl:,.2f}")
        f3.metric("Consecutive losses", consecutive_losses)
        gate_rows = _gate_rows()
        today_rejections = [r for r in gate_rows if (_parse_iso(r.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)).date() == datetime.now(timezone.utc).date()]
        reason_counter = Counter(str(r.get("reason", "unknown")) for r in today_rejections)
        st.metric("Gate rejections today", len(today_rejections))
        st.caption("Top 3 gate reasons: " + ", ".join(f"{k} ({v})" for k, v in reason_counter.most_common(3)) if reason_counter else "No gate rejections today.")
        recent_trades = runtime_snapshot.get("last_trades", [])
        if not isinstance(recent_trades, list):
            recent_trades = []
        if recent_trades:
            st.dataframe(pd.DataFrame(recent_trades[-10:]), width="stretch")
        else:
            st.info("No executed trades captured yet.")

    # G. System Health & Logs
    with tab_g:
        st.markdown("### G. System Health & Logs")
        try:
            import psutil  # type: ignore[import-untyped]

            vm = psutil.virtual_memory()
            st.caption(f"Host: CPU {psutil.cpu_percent(interval=None):.0f}% | Memory {vm.percent:.0f}% used ({vm.available // (1024**3)} GB free)")
        except Exception:
            pass
        warn_err = _tail_warning_error_logs(paths.full_log, limit=80)
        comp_filter = st.text_input("Filter logs by component/event", value="", key="monitoring_log_filter").strip().lower()
        if comp_filter:
            warn_err = [ln for ln in warn_err if comp_filter in ln.lower()]
        _render_dark_log_text(
            "\n".join(warn_err[-40:]) if warn_err else "No warning/error lines found.",
            height_px=280,
        )
        st.download_button(
            "Export warning/error log tail",
            data="\n".join(warn_err),
            file_name="lumina_warning_error_tail.log",
            mime="text/plain",
        )
        latency_rows = _latency_rows()
        breaches = [r for r in latency_rows if _safe_float(r.get("elapsed_ms")) > _safe_float(r.get("sla_ms"), 0.0)]
        st.metric("Latency SLA breaches", len(breaches))
        model_load_rows = _model_load_rows()
        if model_load_rows:
            model_df = pd.DataFrame(model_load_rows[-20:])
            st.dataframe(model_df, width="stretch")
        else:
            st.info("No model loading telemetry captured yet.")

    # H. Trends
    with tab_h:
        st.markdown("### Trends")
        chart_col1, chart_col2, chart_col3 = st.columns(3)
        with chart_col1:
            twin_training = _twin_training()
            rewards = [_safe_float(x.get("reward")) for x in twin_training if x.get("reward") is not None]
            if rewards:
                _render_dark_series_chart(rewards[-30:], y_col="twin_reward", y_title="Twin Reward", color="#00f0ff")
            else:
                st.caption("No reward trend yet.")
        with chart_col2:
            twin_decisions = _twin_decisions()
            confidence = [_safe_float(x.get("score")) for x in twin_decisions if x.get("score") is not None]
            if confidence:
                _render_dark_series_chart(
                    confidence[-30:],
                    y_col="twin_confidence",
                    y_title="Twin Confidence",
                    color="#00ff9f",
                )
            else:
                st.caption("No twin confidence trend yet.")
        with chart_col3:
            pnl_points = [_safe_float(x.get("daily_pnl")) for x in _load_jsonl(paths.daily_pnl_history, limit=120)]
            if not pnl_points:
                pnl_points = [
                    _safe_float(x.get("daily_pnl"))
                    for x in _load_jsonl(paths.reasoning_latency, limit=60)
                    if x.get("daily_pnl") is not None
                ]
            if pnl_points:
                _render_dark_series_chart(pnl_points[-30:], y_col="daily_pnl", y_title="Daily PnL", color="#38bdf8")
            else:
                st.caption("No daily PnL trend yet.")

    # Structured error feed
    with tab_g:
        structured_errors = _structured_errors()
        if structured_errors:
            st.markdown("#### Structured Errors")
            err_df = pd.DataFrame(structured_errors[-25:])
            st.dataframe(err_df, width="stretch")
        else:
            st.caption("No structured errors recorded.")
        with st.expander("Backend API observability (health + JSON metrics + Prometheus)", expanded=False):
            render_backend_observability_subpanel(base_url, api_key)
