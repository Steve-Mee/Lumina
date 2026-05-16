from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

from lumina_os.frontend.http_utils import is_backend_unreachable, log_fetch_failure

_LOG = logging.getLogger(__name__)

_STATE_DIR = Path("state")
_LOGS_DIR = Path("logs")
_JOURNAL_SIM_DIR = Path("journal/simulator")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EMBEDDED_UI_INDEX = _REPO_ROOT / "frontend" / "dist" / "index.html"

_FIRST_BOOT_PROGRESS_PATH = _STATE_DIR / "first_boot_progress.json"
_FIRST_BOOT_FLAG_PATH = _STATE_DIR / "first_boot_completed.flag"
_FIRST_BOOT_POLICY_ZIP_PATH = Path("lumina_agents/ppo/lumina_ppo_policy.zip")
_PPO_POLICY_METADATA_PATH = _STATE_DIR / "ppo_policy_metadata.json"
_APPROVAL_TWIN_MODEL_PATH = _STATE_DIR / "approval_twin_model.json"
_APPROVAL_TWIN_DECISIONS_PATH = _STATE_DIR / "monitoring_twin_decisions.jsonl"
_APPROVAL_TWIN_TRAINING_PATH = _STATE_DIR / "monitoring_twin_training.jsonl"
_SHADOW_RUNS_PATH = _STATE_DIR / "evolution_shadow_runs.json"
_RUNTIME_MONITORING_PATH = _STATE_DIR / "monitoring_runtime_metrics.json"
_GATE_REJECTION_PATH = _STATE_DIR / "monitoring_gate_rejections.jsonl"
_REASONING_LATENCY_PATH = _STATE_DIR / "monitoring_reasoning_latency.jsonl"
_MODEL_LOAD_TIMES_PATH = _STATE_DIR / "monitoring_model_load_times.jsonl"
_DAILY_PNL_HISTORY_PATH = _STATE_DIR / "monitoring_daily_pnl.jsonl"
_DEBUG_TRAINING_PROCESS_PATH = _STATE_DIR / "monitoring_debug_training_process.json"
_VETO_REGISTRY_JSONL = _STATE_DIR / "veto_registry.jsonl"
_VETO_REGISTRY_DB = _STATE_DIR / "veto_registry.db"
_STRUCTURED_ERRORS_PATH = _LOGS_DIR / "structured_errors.jsonl"
_FULL_LOG_PATH = _LOGS_DIR / "lumina_full_log.csv"
_LUMINA_SIM_STATE_PATH = _STATE_DIR / "lumina_sim_state.json"


def _first_boot_completion_display(progress: dict[str, Any]) -> tuple[str, str]:
    """Show Yes only when first boot truly finished; In progress while training runs.

    ``first_boot_progress.json`` ``stage`` wins over a stale ``first_boot_completed.flag`` file
    so the dashboard does not show Yes during detected/loading/training.
    """
    stage = str(progress.get("stage", "")).strip().lower()
    if stage in {"detected", "loading_data", "training_running"}:
        return "In progress", "n/a"
    if stage == "completed":
        ts = (
            _FIRST_BOOT_FLAG_PATH.read_text(encoding="utf-8").strip()
            if _FIRST_BOOT_FLAG_PATH.exists()
            else str(progress.get("timestamp", "n/a"))
        )
        return "Yes", ts
    if stage == "failed":
        return "Failed", "n/a"
    if stage == "deferred_calendar":
        return "Deferred", "n/a"
    # Idle / normale herstart: alleen Yes als zowel vlag als policy er zijn.
    if _FIRST_BOOT_FLAG_PATH.exists() and _FIRST_BOOT_POLICY_ZIP_PATH.exists():
        return "Yes", _FIRST_BOOT_FLAG_PATH.read_text(encoding="utf-8").strip()
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
    stage_to_progress = {"detected": 10, "loading_data": 35, "training_running": 70, "completed": 100, "failed": 100}
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


def _tail_warning_error_logs(limit: int = 100) -> list[str]:
    if not _FULL_LOG_PATH.exists():
        return []
    lines: list[str] = []
    for raw in _FULL_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if ",WARNING," in line or ",ERROR," in line:
            lines.append(line)
    return lines[-limit:]


def _latest_training_reports(limit: int = 10) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(_JOURNAL_SIM_DIR.glob("first_boot_training_*.json")):
        payload = _load_json(path)
        if payload:
            payload["_run_type"] = "Background"
            payload["_path"] = str(path)
            reports.append(payload)
    for path in sorted(_JOURNAL_SIM_DIR.glob("nightly_sim_*.json")):
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
    """Weekly veto counts; ``state_dir`` defaults to ``state/`` (for tests pass a temp dir)."""
    base = state_dir or _STATE_DIR
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


def _weekly_veto_summary() -> tuple[int, list[tuple[str, int]]]:
    return weekly_veto_summary()


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
                st.code(prom_resp.text, language="text")
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


def _load_debug_process_meta() -> dict[str, Any]:
    return _load_json(_DEBUG_TRAINING_PROCESS_PATH)


def _write_debug_process_meta(payload: dict[str, Any]) -> None:
    _DEBUG_TRAINING_PROCESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DEBUG_TRAINING_PROCESS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _start_debug_training_process(command: list[str], *, label: str) -> str:
    try:
        proc = subprocess.Popen(command, cwd=str(Path(".").resolve()))
    except Exception as exc:
        return f"Start mislukt: {exc}"
    _write_debug_process_meta(
        {
            "pid": int(proc.pid),
            "label": str(label),
            "command": command,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }
    )
    return f"Gestart: {label} (pid={proc.pid})"


def _stop_debug_training_process() -> str:
    meta = _load_debug_process_meta()
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
    _write_debug_process_meta(meta)
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


def _react_dashboard_link(api_base: str) -> str:
    """Voorkeur: gebouwde SPA onder FastAPI /ui/; anders Vite-dev URL; override via env."""
    explicit = (os.getenv("LUMINA_REACT_DASHBOARD_URL") or "").strip()
    if explicit:
        return explicit
    base = api_base.rstrip("/")
    if _EMBEDDED_UI_INDEX.is_file():
        return f"{base}/ui/"
    return _react_dashboard_url_default()


def render_monitoring_dashboard_tab(base_url: str, *, title: str = "Monitoring Dashboard") -> None:
    st.subheader(title)
    react_dashboard_url = _react_dashboard_link(base_url)

    top_a, top_b = st.columns([3, 2])
    with top_a:
        if _EMBEDDED_UI_INDEX.is_file():
            st.caption(
                "React-dashboard wordt meegeleverd via de FastAPI-backend (geen aparte terminal). "
                "Open de knop rechts. Ontbreekt `frontend/dist`, bouw eenmalig: `cd frontend && npm ci && npm run build:embedded` "
                "of voer `scripts/build_embedded_ui.ps1` uit."
            )
        else:
            st.caption(
                "Geen productie-build van het React-dashboard aangetroffen (`frontend/dist`). "
                "Eenmalig bouwen met `npm run build:embedded` in map `frontend`, of tijdelijk: `npm run dev` (poort 5173). "
                "Zet anders `LUMINA_REACT_DASHBOARD_URL`."
            )
    with top_b:
        if react_dashboard_url:
            st.link_button("Open React Dashboard", react_dashboard_url, use_container_width=True)

    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        api_key = st.text_input("API Key (optional, unlocks live metrics API)", type="password", key="monitoring_api_key")
    with col_b:
        refresh_seconds = st.slider("Auto-refresh (sec)", min_value=15, max_value=30, value=20, step=5)
    with col_c:
        auto_refresh = st.checkbox("Auto refresh", value=False)

    section_choice_raw = st.sidebar.selectbox(
        "Monitoring section",
        options=[
            "All",
            "A. System Overview",
            "B. First Boot Training Status",
            "C. Training History",
            "D. ApprovalTwin Activity",
            "E. Shadow Deployment",
            "F. Live Trading Metrics",
            "G. System Health & Logs",
            "Debug Controls",
        ],
        index=0,
        key="monitoring_section_choice",
    )
    section_choice = section_choice_raw if isinstance(section_choice_raw, str) else "All"

    def _show(section_name: str) -> bool:
        return section_choice in {"All", section_name}

    if auto_refresh:
        time.sleep(int(refresh_seconds))
        st.rerun()

    metrics_snapshot = _fetch_metrics_json(base_url, api_key=api_key)
    runtime_snapshot = _load_json(_RUNTIME_MONITORING_PATH)
    fallback_runtime_state = _load_json(_LUMINA_SIM_STATE_PATH)
    first_boot_progress = _load_json(_FIRST_BOOT_PROGRESS_PATH)
    ppo_meta = _load_json(_PPO_POLICY_METADATA_PATH)
    twin_model = _load_json(_APPROVAL_TWIN_MODEL_PATH)
    twin_decisions = _load_jsonl(_APPROVAL_TWIN_DECISIONS_PATH, limit=20)
    twin_training = _load_jsonl(_APPROVAL_TWIN_TRAINING_PATH, limit=20)
    shadow_runs = _load_json(_SHADOW_RUNS_PATH)
    gate_rows = _load_jsonl(_GATE_REJECTION_PATH, limit=300)
    latency_rows = _load_jsonl(_REASONING_LATENCY_PATH, limit=200)
    model_load_rows = _load_jsonl(_MODEL_LOAD_TIMES_PATH, limit=100)
    training_reports = _latest_training_reports(limit=10)
    structured_errors = _load_jsonl(_STRUCTURED_ERRORS_PATH, limit=120)

    if _show("Debug Controls"):
        st.markdown("### Debug Controls")
        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            if st.button("Start nightly training", key="monitoring_start_nightly"):
                msg = _start_debug_training_process(
                    [sys.executable, "-m", "lumina_core.engine.runtime_entrypoint", "--mode", "nightly"],
                    label="nightly_training",
                )
                st.info(msg)
        with dc2:
            if st.button("Start headless SIM training", key="monitoring_start_headless_sim"):
                msg = _start_debug_training_process(
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
                st.info(_stop_debug_training_process())
        proc_meta = _load_debug_process_meta()
        if proc_meta:
            st.caption(
                "Tracked process: "
                f"pid={proc_meta.get('pid', 'n/a')} "
                f"label={proc_meta.get('label', 'n/a')} "
                f"status={proc_meta.get('status', 'unknown')}"
            )

    # A. System Overview
    if _show("A. System Overview"):
        st.markdown("### A. System Overview")
    mode = str(runtime_snapshot.get("mode") or fallback_runtime_state.get("mode") or "SIM").upper()
    first_boot_label, first_boot_ts = _first_boot_completion_display(first_boot_progress)
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
    if _show("B. First Boot Training Status"):
        st.markdown("### B. First Boot Training Status")
    stage = str(first_boot_progress.get("stage", "unknown"))
    st.progress(_first_boot_progress_fraction(first_boot_progress))
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Stage", stage)
    b2.metric("Historical days (loaded / est.)", _first_boot_historical_days_display(first_boot_progress))
    b3.metric("Real vs synthetic %", f"{_safe_float(last_training.get('synthetic_pct', 0.0)):.2f}% synthetic")
    b4.metric("Trades completed", _safe_int(last_training.get("trades")))
    phase = str(first_boot_progress.get("phase") or "").strip() or "n/a"
    pct_raw = first_boot_progress.get("progress_pct")
    pct_note = f"{pct_raw}%" if pct_raw is not None else "—"
    st.caption(
        f"Phase: {phase} · detail progress: {pct_note} · "
        f"{first_boot_progress.get('message', 'No first boot message available.')}"
    )

    # C. Training History
    if _show("C. Training History"):
        st.markdown("### C. Training History")
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
    if _show("C. Training History") and history_rows:
        hist_df = pd.DataFrame(history_rows)
        st.dataframe(hist_df, width="stretch")
        st.download_button(
            "Export training history (JSON)",
            data=json.dumps(history_rows, indent=2),
            file_name="training_history.json",
            mime="application/json",
        )
    elif _show("C. Training History"):
        st.info("No training history found in journal/simulator.")

    # D. ApprovalTwin Activity
    if _show("D. ApprovalTwin Activity"):
        st.markdown("### D. ApprovalTwin Activity")
    if _show("D. ApprovalTwin Activity") and twin_decisions:
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
    elif _show("D. ApprovalTwin Activity"):
        st.info("No twin decision telemetry found yet.")
    if _show("D. ApprovalTwin Activity"):
        veto_count, top_reasons = _weekly_veto_summary()
        st.metric("Weekly veto count", veto_count)
        if top_reasons:
            st.write("Top veto reasons:", ", ".join(f"{reason} ({count})" for reason, count in top_reasons[:3]))

    # E. Shadow Deployment
    if _show("E. Shadow Deployment"):
        st.markdown("### E. Shadow Deployment")
    shadow_values = list(shadow_runs.values()) if isinstance(shadow_runs, dict) else []
    active_shadow = [r for r in shadow_values if str(r.get("status", "")).lower() == "running"]
    promoted = [r for r in shadow_values if str(r.get("status", "")).lower() == "promoted"]
    if _show("E. Shadow Deployment"):
        e1, e2 = st.columns(2)
        e1.metric("Active shadow runs", len(active_shadow))
        e2.metric("Promoted strategies", len(promoted))
    if _show("E. Shadow Deployment") and shadow_values:
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
    if _show("F. Live Trading Metrics"):
        st.markdown("### F. Live Trading Metrics")
    live_exposure = _safe_int(runtime_snapshot.get("live_position_qty", fallback_runtime_state.get("live_position_qty", 0)))
    daily_pnl = _safe_float(runtime_snapshot.get("daily_pnl", _metric_value(metrics_snapshot, "lumina_risk_daily_pnl", 0.0)))
    consecutive_losses = _safe_int(
        runtime_snapshot.get("consecutive_losses", _metric_value(metrics_snapshot, "lumina_risk_consecutive_losses", 0.0))
    )
    if _show("F. Live Trading Metrics"):
        f1, f2, f3 = st.columns(3)
        f1.metric("Current exposure (qty)", live_exposure)
        f2.metric("Daily PnL", f"${daily_pnl:,.2f}")
        f3.metric("Consecutive losses", consecutive_losses)
    today_rejections = [r for r in gate_rows if (_parse_iso(r.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)).date() == datetime.now(timezone.utc).date()]
    reason_counter = Counter(str(r.get("reason", "unknown")) for r in today_rejections)
    if _show("F. Live Trading Metrics"):
        st.metric("Gate rejections today", len(today_rejections))
        st.caption("Top 3 gate reasons: " + ", ".join(f"{k} ({v})" for k, v in reason_counter.most_common(3)) if reason_counter else "No gate rejections today.")
    recent_trades = runtime_snapshot.get("last_trades", [])
    if not isinstance(recent_trades, list):
        recent_trades = []
    if _show("F. Live Trading Metrics") and recent_trades:
        st.dataframe(pd.DataFrame(recent_trades[-10:]), width="stretch")
    elif _show("F. Live Trading Metrics"):
        st.info("No executed trades captured yet.")

    # G. System Health & Logs
    if _show("G. System Health & Logs"):
        st.markdown("### G. System Health & Logs")
        try:
            import psutil  # type: ignore[import-untyped]

            vm = psutil.virtual_memory()
            st.caption(f"Host: CPU {psutil.cpu_percent(interval=None):.0f}% | Memory {vm.percent:.0f}% used ({vm.available // (1024**3)} GB free)")
        except Exception:
            pass
    warn_err = _tail_warning_error_logs(limit=80)
    comp_filter = st.text_input("Filter logs by component/event", value="", key="monitoring_log_filter").strip().lower()
    if comp_filter:
        warn_err = [ln for ln in warn_err if comp_filter in ln.lower()]
    if _show("G. System Health & Logs"):
        st.code("\n".join(warn_err[-40:]) if warn_err else "No warning/error lines found.", language="text")
        st.download_button(
            "Export warning/error log tail",
            data="\n".join(warn_err),
            file_name="lumina_warning_error_tail.log",
            mime="text/plain",
        )
    breaches = [r for r in latency_rows if _safe_float(r.get("elapsed_ms")) > _safe_float(r.get("sla_ms"), 0.0)]
    if _show("G. System Health & Logs"):
        st.metric("Latency SLA breaches", len(breaches))
        if model_load_rows:
            model_df = pd.DataFrame(model_load_rows[-20:])
            st.dataframe(model_df, width="stretch")
        else:
            st.info("No model loading telemetry captured yet.")

    # Nice-to-have charts
    if _show("All"):
        st.markdown("### Trends")
    chart_col1, chart_col2, chart_col3 = st.columns(3)
    with chart_col1:
        rewards = [_safe_float(x.get("reward")) for x in twin_training if x.get("reward") is not None]
        if rewards:
            st.line_chart(pd.DataFrame({"twin_reward": rewards[-30:]}), height=180)
        else:
            st.caption("No reward trend yet.")
    with chart_col2:
        confidence = [_safe_float(x.get("score")) for x in twin_decisions if x.get("score") is not None]
        if confidence:
            st.line_chart(pd.DataFrame({"twin_confidence": confidence[-30:]}), height=180)
        else:
            st.caption("No twin confidence trend yet.")
    with chart_col3:
        pnl_points = [_safe_float(x.get("daily_pnl")) for x in _load_jsonl(_DAILY_PNL_HISTORY_PATH, limit=120)]
        if not pnl_points:
            pnl_points = [_safe_float(x.get("daily_pnl")) for x in _load_jsonl(_REASONING_LATENCY_PATH, limit=60) if x.get("daily_pnl") is not None]
        if not pnl_points and daily_pnl:
            pnl_points = [daily_pnl]
        if pnl_points:
            st.line_chart(pd.DataFrame({"daily_pnl": pnl_points[-30:]}), height=180)
        else:
            st.caption("No daily PnL trend yet.")

    # Structured error feed
    if _show("G. System Health & Logs") and structured_errors:
        st.markdown("#### Structured Errors")
        err_df = pd.DataFrame(structured_errors[-25:])
        st.dataframe(err_df, width="stretch")
    elif _show("G. System Health & Logs"):
        st.caption("No structured errors recorded.")

    if _show("G. System Health & Logs"):
        with st.expander("Backend API observability (health + JSON metrics + Prometheus)", expanded=False):
            render_backend_observability_subpanel(base_url, api_key)
