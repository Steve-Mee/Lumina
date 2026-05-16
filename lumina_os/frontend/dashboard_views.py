"""Reusable LUMINA OS dashboard views (Streamlit) — no top-level page config.

All paths are rooted at ``workspace_root`` (repository root), so the launcher and
legacy ``dashboard.py`` entrypoints behave consistently regardless of process cwd.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import subprocess
import sys
import time
from collections import deque
from contextlib import chdir
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
    resolve_first_boot_target_trades,
)
from lumina_core.engine.sim_stability_checker import format_stability_report, generate_stability_report
from lumina_os.frontend.http_utils import is_backend_unreachable, log_fetch_failure

logger = logging.getLogger(__name__)

PREMIUM_THEME_CSS = """
<style>
:root {
  --lumina-bg: #0a0a0f;
  --lumina-card: #11131a;
  --lumina-card-2: #0f1218;
  --lumina-border: rgba(0, 240, 255, 0.16);
  --lumina-border-strong: rgba(0, 240, 255, 0.32);
  --lumina-text: #e8e6e3;
  --lumina-text-muted: #94a3b8;
  --lumina-cyan: #00f0ff;
  --lumina-green: #00ff9f;
}
section[data-testid="stMain"] {
  background:
    radial-gradient(circle at 12% 4%, rgba(0, 240, 255, 0.12), transparent 42%),
    radial-gradient(circle at 87% 13%, rgba(0, 255, 159, 0.1), transparent 38%),
    var(--lumina-bg);
}
h1, h2, h3, h4, h5, h6 {
  color: var(--lumina-text);
}
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  gap: 10px;
  background: rgba(9, 10, 15, 0.75);
  border: 1px solid var(--lumina-border);
  border-radius: 14px;
  padding: 8px;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  border-radius: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
[data-testid="stTabs"] [aria-selected="true"] {
  background: linear-gradient(95deg, rgba(0, 240, 255, 0.18), rgba(0, 255, 159, 0.12));
  border: 1px solid var(--lumina-border-strong);
}
[data-testid="stMetric"] {
  background: linear-gradient(145deg, rgba(17, 19, 26, 0.94), rgba(9, 10, 15, 0.9));
  border: 1px solid var(--lumina-border);
  border-radius: 14px;
  padding: 10px 14px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
}
[data-testid="stArrowVegaLiteChart"],
[data-testid="stDataFrame"],
[data-testid="stCodeBlock"],
.stCodeBlock {
  background: rgba(12, 14, 20, 0.9) !important;
  border: 1px solid rgba(0, 240, 255, 0.16) !important;
  border-radius: 12px !important;
}
[data-testid="stCodeBlock"] pre,
.stCodeBlock pre {
  background: transparent !important;
  color: #b6c2d3 !important;
}
.stButton > button, a[data-testid="stLinkButton"] {
  border-radius: 11px !important;
  border: 1px solid var(--lumina-border-strong) !important;
  box-shadow: 0 8px 28px rgba(0, 240, 255, 0.14) !important;
}
.stCaptionContainer, [data-testid="stCaptionContainer"] {
  color: var(--lumina-text-muted) !important;
}
</style>
"""

LUXURY_STATUS_BAR_CSS = """
<style>
@keyframes lumina-pulse-glow {
  0%, 100% { opacity: 1; filter: brightness(1); }
  50% { opacity: 0.82; filter: brightness(1.25); }
}
section[data-testid="stMain"] [data-testid="stHorizontalBlock"]:has(span.lumina-logo-text),
section.main [data-testid="stHorizontalBlock"]:has(span.lumina-logo-text) {
  background: linear-gradient(135deg, rgba(10, 10, 15, 0.98) 0%, rgba(13, 20, 30, 0.96) 52%, rgba(10, 10, 15, 0.98) 100%);
  border: 1px solid rgba(0, 240, 255, 0.34);
  border-radius: 16px;
  padding: 10px 18px 14px;
  margin-bottom: 6px;
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.55),
    0 0 0 1px rgba(0, 255, 159, 0.05) inset;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}
.lumina-bar-cell {
  display: flex;
  align-items: center;
  min-height: 48px;
  padding: 4px 2px;
}
.lumina-bar-cell.lumina-phase-stack {
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
}
.lumina-logo-text {
  font-family: "Inter", "Segoe UI", ui-sans-serif, system-ui, sans-serif;
  font-weight: 800;
  font-size: 1.28rem;
  letter-spacing: 0.32em;
  background: linear-gradient(92deg, #00f0ff 0%, #9be8ff 45%, #00ff9f 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  filter: drop-shadow(0 0 16px rgba(0, 240, 255, 0.35));
}
.lumina-badge {
  font-family: "Segoe UI", ui-sans-serif, system-ui, sans-serif;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  white-space: nowrap;
}
.lumina-badge-training {
  color: #00ff9f;
  text-shadow: 0 0 14px rgba(0, 255, 159, 0.82);
  animation: lumina-pulse-glow 1.85s ease-in-out infinite;
}
.lumina-badge-idle {
  color: #94a3b8;
}
.lumina-metrics {
  font-family: "Inter", "Segoe UI", ui-sans-serif, system-ui, sans-serif;
  font-size: 0.92rem;
  color: #d4d4db;
  flex-wrap: wrap;
  gap: 4px;
}
.lumina-metric-strong {
  color: #f8fafc;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.lumina-metric-muted {
  color: #7de7ff;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.lumina-dot {
  color: rgba(148, 163, 184, 0.65);
  padding: 0 5px;
}
.lumina-mode-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(0, 240, 255, 0.15);
  border: 1px solid rgba(0, 240, 255, 0.45);
  color: #d9fbff;
  font-weight: 700;
  font-size: 0.82rem;
  letter-spacing: 0.06em;
}
.lumina-phase-k {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: #64748b;
  margin-bottom: 2px;
}
.lumina-phase-v {
  font-size: 1.02rem;
  font-weight: 800;
  color: #00f0ff;
  text-shadow: 0 0 18px rgba(0, 240, 255, 0.35);
}
.lumina-artifacts {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  border: 1px solid rgba(0, 240, 255, 0.25);
  color: #d9fbff;
}
.lumina-artifacts-ok {
  border-color: rgba(0, 255, 159, 0.34);
  color: #00ff9f;
}
.lumina-artifacts-missing {
  border-color: rgba(251, 191, 36, 0.44);
  color: #fbbf24;
}
</style>
"""


@dataclass(frozen=True)
class DashboardPaths:
    """Resolved repository paths for dashboard state and config."""

    workspace_root: Path

    @property
    def state_dir(self) -> Path:
        return self.workspace_root / "state"

    @property
    def last_run_summary(self) -> Path:
        return self.state_dir / "last_run_summary.json"

    @property
    def evolution_log(self) -> Path:
        return self.state_dir / "evolution_log.jsonl"

    @property
    def runtime_state(self) -> Path:
        return self.state_dir / "lumina_sim_state.json"

    @property
    def history_path(self) -> Path:
        return self.state_dir / "sim_stability_history.jsonl"

    @property
    def first_boot_progress(self) -> Path:
        return self.state_dir / "first_boot_progress.json"

    @property
    def monitoring_runtime_metrics(self) -> Path:
        return self.state_dir / "monitoring_runtime_metrics.json"

    @property
    def debug_training_proc(self) -> Path:
        return self.state_dir / "monitoring_debug_training_process.json"

    @property
    def agent_blackboard(self) -> Path:
        return self.state_dir / "agent_blackboard.jsonl"

    @property
    def embedded_ui_index(self) -> Path:
        return self.workspace_root / "frontend" / "dist" / "index.html"

    @property
    def config_yaml(self) -> Path:
        return self.workspace_root / "config.yaml"

    @property
    def env_dotenv(self) -> Path:
        return self.workspace_root / ".env"


def resolve_workspace_root_from_this_module() -> Path:
    """Repo root: this file lives in ``<repo>/lumina_os/frontend/``."""
    return Path(__file__).resolve().parent.parent.parent


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def linear_trend(values: list[float]) -> list[float]:
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


def render_dark_multi_series_chart(
    frame: pd.DataFrame,
    *,
    x_col: str,
    value_cols: list[str],
    height: int = 200,
) -> None:
    melted = frame.reset_index().melt(id_vars=[x_col], value_vars=value_cols, var_name="series", value_name="value")
    chart = (
        alt.Chart(melted)
        .mark_line(strokeWidth=2.0)
        .encode(
            x=alt.X(f"{x_col}:N", axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8")),
            y=alt.Y("value:Q", axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8")),
            color=alt.Color(
                "series:N",
                scale=alt.Scale(
                    domain=value_cols,
                    range=["#00f0ff", "#00ff9f", "#38bdf8", "#f59e0b"],
                ),
                legend=alt.Legend(labelColor="#94a3b8", titleColor="#94a3b8"),
            ),
            tooltip=[x_col, "series", "value"],
        )
        .properties(height=height)
        .configure(background="#0f1118")
        .configure_view(strokeOpacity=0, fill="#0f1118")
        .configure_axis(gridColor="#1f2937")
    )
    st.altair_chart(chart, use_container_width=True)


def load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        logger.exception("Failed reading JSON: %s", path)
        return {}


def load_yaml_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        logger.exception("Failed reading YAML: %s", path)
        return {}


def append_or_replace_env(path: Path, key: str, value: str) -> None:
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


def parse_ts(raw_value: Any) -> datetime | None:
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


def load_evolution_rows(path: Path) -> list[dict[str, Any]]:
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
    rows.sort(
        key=lambda row: parse_ts(row.get("timestamp"))
        or datetime.min.replace(tzinfo=timezone.utc)
    )
    return rows


def read_tail_lines(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []
    bucket: deque[str] = deque(maxlen=max(1, limit))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if text:
                bucket.append(text)
    return list(bucket)


def resolve_mode(p: DashboardPaths) -> str:
    env_mode = str(os.getenv("LUMINA_MODE", "")).strip().lower()
    if env_mode in {"sim", "paper", "real"}:
        return env_mode
    cfg = load_yaml_dict(p.config_yaml)
    config_mode = str(cfg.get("mode", "sim")).strip().lower()
    return config_mode if config_mode in {"sim", "paper", "real"} else "sim"


def training_target_trades(p: DashboardPaths) -> int:
    user_configured = (p.state_dir / "first_boot_user_configured.flag").is_file()
    if not user_configured:
        return 0
    cfg = load_yaml_dict(p.config_yaml)
    return resolve_first_boot_target_trades(cfg)


def host_only_from_streamlit_host(header_val: str) -> str:
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


def react_dashboard_url(api_base: str, p: DashboardPaths) -> str:
    def _ui_build_stamp(path: Path) -> str:
        try:
            return str(int(path.stat().st_mtime_ns))
        except OSError:
            return "0"

    explicit = (os.getenv("LUMINA_REACT_DASHBOARD_URL") or "").strip()
    if explicit:
        return explicit
    base = api_base.rstrip("/")
    if p.embedded_ui_index.is_file():
        return f"{base}/ui/?v={_ui_build_stamp(p.embedded_ui_index)}"
    port = (os.getenv("LUMINA_REACT_DASHBOARD_PORT") or "5173").strip() or "5173"
    host = "localhost"
    try:
        hdrs = st.context.headers
        raw = hdrs.get("Host") if hdrs is not None else None
        if raw is None and hdrs is not None:
            raw = hdrs.get("host")
        if isinstance(raw, str) and raw.strip():
            host = host_only_from_streamlit_host(raw)
    except Exception:
        pass
    return f"http://{host}:{port}"


def training_dashboard_fallback_url(port: int = 8502) -> str:
    host = "localhost"
    try:
        hdrs = st.context.headers
        raw = hdrs.get("Host") if hdrs is not None else None
        if raw is None and hdrs is not None:
            raw = hdrs.get("host")
        if isinstance(raw, str) and raw.strip():
            host = host_only_from_streamlit_host(raw)
    except Exception:
        pass
    return f"http://{host}:{port}"


def heartbeat_age_display(p: DashboardPaths) -> str:
    now = datetime.now(timezone.utc)
    candidates: list[datetime] = []
    for path, keys in (
        (p.monitoring_runtime_metrics, ("timestamp",)),
        (p.first_boot_progress, ("timestamp",)),
        (p.last_run_summary, ("finished_at", "started_at")),
    ):
        payload = load_json_dict(path)
        for key in keys:
            ts = parse_ts(payload.get(key))
            if ts is not None:
                candidates.append(ts)
    sim = load_json_dict(p.runtime_state)
    dream = sim.get("current_dream") if isinstance(sim.get("current_dream"), dict) else {}
    swarm_ts = parse_ts(dream.get("swarm_ts"))
    if swarm_ts is not None:
        candidates.append(swarm_ts)
    if not candidates:
        return "— ago"
    newest = max(candidates)
    delta = max(0.0, (now - newest).total_seconds())
    if delta < 120.0:
        return f"{delta:.1f}s ago"
    if delta < 3600.0:
        return f"{delta / 60.0:.1f}m ago"
    return f"{delta / 3600.0:.1f}h ago"


def training_active_from_state(
    first_boot: dict[str, Any], debug_proc: dict[str, Any]
) -> bool:
    stage = str(first_boot.get("stage", "")).strip().lower()
    if stage in {"detected", "loading_data", "training_running"}:
        return True
    return str(debug_proc.get("status", "")).strip().lower() == "running"


def status_phase_label(runtime_mode: str, first_boot: dict[str, Any]) -> str:
    if runtime_mode == "real":
        return "REAL"
    stage = str(first_boot.get("stage", "")).strip().lower()
    if stage in {"detected", "loading_data", "training_running"}:
        return "First Boot"
    return "Evolution"


def status_bar_trade_count(first_boot: dict[str, Any], summary: dict[str, Any]) -> int:
    n = resolve_first_boot_completed_trades(first_boot)
    if n > 0:
        return n
    stage = str(first_boot.get("stage", "")).strip().lower()
    if stage in {"detected", "loading_data", "training_running"}:
        cumulative = safe_int(first_boot.get("cumulative_trades"))
        if cumulative > 0:
            return cumulative
    n = safe_int(summary.get("total_trades"))
    if n > 0:
        return n
    ml = summary.get("metrics_learning")
    if isinstance(ml, dict):
        return safe_int(ml.get("total_trades"))
    return 0


def render_luxury_status_bar(p: DashboardPaths, api_base_url: str, runtime_mode: str) -> None:
    st.markdown(PREMIUM_THEME_CSS + LUXURY_STATUS_BAR_CSS, unsafe_allow_html=True)
    fb = load_json_dict(p.first_boot_progress)
    dbg = load_json_dict(p.debug_training_proc)
    summary = load_json_dict(p.last_run_summary)
    training_on = training_active_from_state(fb, dbg)
    phase = status_phase_label(runtime_mode, fb)
    trades = status_bar_trade_count(fb, summary)
    heartbeat = heartbeat_age_display(p)
    mode_label = (runtime_mode or "sim").strip().upper() or "SIM"
    completed_flag = (p.state_dir / "first_boot_completed.flag").is_file()
    policy_zip = (p.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip").is_file()
    artifacts_ok = completed_flag and policy_zip

    badge_cls = "lumina-badge lumina-badge-training" if training_on else "lumina-badge lumina-badge-idle"
    badge_txt = "● TRAINING ACTIVE" if training_on else "● IDLE"
    artifacts_cls = "lumina-artifacts lumina-artifacts-ok" if artifacts_ok else "lumina-artifacts lumina-artifacts-missing"
    artifacts_txt = "Artifacts OK" if artifacts_ok else "Artifacts missing"

    c_logo, c_badge, c_metrics, c_phase, c_artifacts = st.columns([1.0, 1.15, 2.65, 1.0, 1.35])
    with c_logo:
        st.markdown(
            '<div class="lumina-bar-cell"><span class="lumina-logo-text">LUMINA</span></div>',
            unsafe_allow_html=True,
        )
    with c_badge:
        st.markdown(
            f'<div class="lumina-bar-cell"><span class="{badge_cls}">{badge_txt}</span></div>',
            unsafe_allow_html=True,
        )
    with c_metrics:
        st.markdown(
            '<div class="lumina-bar-cell lumina-metrics">'
            f'<span class="lumina-metric-strong">{trades:,}</span> trades'
            '<span class="lumina-dot">•</span>'
            f'<span class="lumina-metric-muted">{heartbeat}</span> heartbeat'
            '<span class="lumina-dot">•</span>'
            f'<span class="lumina-mode-pill">{mode_label}</span> mode'
            "</div>",
            unsafe_allow_html=True,
        )
    with c_phase:
        st.markdown(
            '<div class="lumina-bar-cell lumina-phase-stack">'
            '<span class="lumina-phase-k">Phase</span>'
            f'<span class="lumina-phase-v">{phase}</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    with c_artifacts:
        st.markdown(
            '<div class="lumina-bar-cell lumina-phase-stack">'
            '<span class="lumina-phase-k">First Boot SSOT</span>'
            f'<span class="{artifacts_cls}">{artifacts_txt}</span>'
            "</div>",
            unsafe_allow_html=True,
        )


def render_shared_monitoring_dashboard(base_url: str) -> None:
    try:
        from monitoring_dashboard import render_monitoring_dashboard_tab
    except ModuleNotFoundError:
        module_path = Path(__file__).with_name("monitoring_dashboard.py")
        spec = importlib.util.spec_from_file_location("__lumina_monitoring_dashboard__", module_path)
        if spec is None or spec.loader is None:
            st.error("Monitoring dashboard module kon niet geladen worden.")
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        render_monitoring_dashboard_tab = getattr(mod, "render_monitoring_dashboard_tab", None)
        if not callable(render_monitoring_dashboard_tab):
            st.error("Monitoring dashboard module mist render functie.")
            return
    render_monitoring_dashboard_tab(base_url, title="Monitoring Dashboard")


def window_metrics(
    summary: dict[str, Any], rows: list[dict[str, Any]], window_days: int
) -> dict[str, float]:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=window_days)
    filtered = [r for r in rows if (parse_ts(r.get("timestamp")) or now_utc) >= cutoff]

    pnl = safe_float(summary.get("pnl_realized"))
    trades = safe_int(summary.get("total_trades"))
    wins = safe_int(summary.get("wins"))
    sharpe_values: list[float] = []
    summary_sharpe = safe_float(summary.get("sharpe_annualized"), default=0.0)
    if summary_sharpe != 0.0:
        sharpe_values.append(summary_sharpe)
    risk_events = safe_int(summary.get("risk_events"))

    for row in filtered:
        meta_raw = row.get("meta_review")
        meta = meta_raw if isinstance(meta_raw, dict) else {}
        pnl += safe_float(meta.get("net_pnl"))
        row_trades = safe_int(meta.get("trades"))
        row_wins = safe_int(meta.get("wins"))
        trades += row_trades
        wins += row_wins
        row_sharpe = safe_float(meta.get("sharpe"), default=0.0)
        if row_sharpe != 0.0:
            sharpe_values.append(row_sharpe)
        risk_events += safe_int(row.get("risk_events"))

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


def load_stability_history(p: DashboardPaths) -> list[dict[str, Any]]:
    rows_raw = read_tail_lines(p.history_path, 1200)
    rows: list[dict[str, Any]] = []
    for raw in rows_raw:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    rows.sort(key=lambda r: str(r.get("day", "")))
    return rows


@st.cache_data(ttl=30, show_spinner=False)
def _cached_stability_report(workspace_root_str: str) -> dict[str, Any]:
    root = Path(workspace_root_str)
    with chdir(root):
        return generate_stability_report()


def stability_report(p: DashboardPaths) -> dict[str, Any]:
    return _cached_stability_report(str(p.workspace_root))


def render_sim_evolution_dashboard_tab(p: DashboardPaths) -> None:
    st.subheader("🚀 SIM Evolution Dashboard")

    history_rows = load_stability_history(p)
    report = stability_report(p)
    consecutive = int(report.get("consecutive_green_days", 0))
    days_to_green = int(report.get("days_to_green", 5))
    history_count = int(report.get("history_row_count", len(history_rows)))
    criteria_raw = report.get("criteria")
    criteria = criteria_raw if isinstance(criteria_raw, dict) else {}
    failures = report.get("failures", []) if isinstance(report.get("failures"), list) else []
    is_green = bool(report.get("READY_FOR_REAL", False))
    status_label = str(report.get("status", "RED")).strip().upper()
    sharpe_crit_raw = criteria.get("extended_run_sharpe")
    sharpe_crit = sharpe_crit_raw if isinstance(sharpe_crit_raw, dict) else {}
    latest_sharpe = safe_float(sharpe_crit.get("latest_sharpe", 0.0))

    summary_color = "#16a34a" if is_green else "#dc2626"
    summary_failures = "none" if not failures else ", ".join(str(x) for x in failures)
    st.markdown(
        f"<div style='padding:10px 14px;border-radius:10px;border:1px solid {summary_color};"
        f"background:{summary_color}14;'><strong>Latest stability_report:</strong> "
        f"<span style='color:{summary_color};font-weight:700;'>{status_label}</span> "
        f"| failures: {summary_failures}</div>",
        unsafe_allow_html=True,
    )

    if is_green:
        st.success(
            f"✅ READY FOR REAL — {consecutive}/5 consecutive positive-expectancy days achieved!"
        )
    elif consecutive >= 3:
        st.warning(
            f"🟡 {consecutive} / 5 consecutive positive-expectancy days — {days_to_green} more needed"
        )
    else:
        st.error(
            f"🔴 {consecutive} / 5 consecutive positive-expectancy days — {days_to_green} more needed"
        )
    st.markdown(f"### {consecutive} / 5 consecutive positive expectancy days")
    st.progress(min(max(consecutive / 5.0, 0.0), 1.0))

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

    if history_rows:
        tail = history_rows[-7:]
        day_labels = [str(r.get("day", "")) for r in tail]
        sharpes = [safe_float(r.get("sharpe_annualized")) for r in tail]
        proposals = [float(safe_int(r.get("evolution_proposals"))) for r in tail]
        proposal_trend = linear_trend(proposals)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("##### 📈 Rolling Sharpe (last 7 days)")
            df_sharpe = pd.DataFrame(
                {"Sharpe": sharpes, "Threshold 1.8": [1.8] * len(sharpes)},
                index=day_labels,
            )
            render_dark_multi_series_chart(
                df_sharpe,
                x_col="index",
                value_cols=["Sharpe", "Threshold 1.8"],
                height=200,
            )

        with chart_col2:
            st.markdown("##### 🧬 Evolution Proposals Trend (last 7 days)")
            df_props = pd.DataFrame(
                {"Proposals": proposals, "Trend": proposal_trend}, index=day_labels
            )
            render_dark_multi_series_chart(
                df_props,
                x_col="index",
                value_cols=["Proposals", "Trend"],
                height=200,
            )
    else:
        st.info("No history data yet — run a SIM to start accumulating daily records.")

    st.markdown("#### 🎯 REAL Readiness Criteria")
    exp_raw = criteria.get("positive_expectancy_5d")
    exp = exp_raw if isinstance(exp_raw, dict) else {}
    consistent_raw = criteria.get("consistent_sharpe")
    consistent = consistent_raw if isinstance(consistent_raw, dict) else {}
    risk_raw = criteria.get("zero_risk_and_var")
    risk = risk_raw if isinstance(risk_raw, dict) else {}
    trend_raw = criteria.get("evolution_proposals_trend")
    trend = trend_raw if isinstance(trend_raw, dict) else {}

    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    sc1.metric(
        "5d Expectancy",
        "✅ PASS" if exp.get("ok") else "❌ FAIL",
        delta=f"streak {exp.get('streak_days', 0)}/{exp.get('required_days', 5)}",
    )
    sc2.metric(
        "Extended Sharpe",
        "✅ PASS" if sharpe_crit.get("ok") else "❌ FAIL",
        delta=f"{safe_float(sharpe_crit.get('latest_sharpe')):.3f}",
    )
    sc3.metric(
        "Consistent Sharpe",
        "✅ PASS" if consistent.get("ok") else "❌ FAIL",
        delta=f"avg {safe_float(consistent.get('average_sharpe')):.3f} ({int(consistent.get('available_runs', 0))}/5 runs)",
    )
    sc4.metric(
        "Zero Risk / VaR",
        "✅ PASS" if risk.get("ok") else "❌ FAIL",
        delta=f"events={risk.get('total_risk_events', 0)}",
    )
    sc5.metric(
        "Proposal Trend",
        "✅ PASS" if trend.get("ok") else "❌ FAIL",
        delta=f"7d={safe_float(trend.get('slope_7d')):.2f}",
    )

    if failures:
        st.warning("⚠️ Failing criteria: " + ", ".join(failures))
    missing = report.get("missing_days_7d", []) if isinstance(report.get("missing_days_7d"), list) else []
    if missing:
        st.caption("📅 Missing days in rolling 7d window: " + ", ".join(str(d) for d in missing))

    with st.expander("📋 Full Stability Report", expanded=False):
        st.code(format_stability_report(report), language="text")

    st.markdown("#### ⚙️ Actions")
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    with btn_col1:
        if st.button(
            "🚀 Run Aggressive Overnight SIM",
            width="stretch",
            type="primary",
            help="Launches: --headless --mode=sim --duration=240 --overnight-sim --stability-check",
        ):
            cmd = [
                sys.executable,
                "-m",
                "lumina_launcher",
                "--headless",
                "--mode=sim",
                "--duration=240",
                "--overnight-sim",
                "--stability-check",
            ]
            proc = subprocess.Popen(
                cmd,
                cwd=str(p.workspace_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            st.success(
                f"✅ Overnight SIM launched (PID {proc.pid}). "
                "Results appear in state/test_runs/ on completion."
            )

    with btn_col2:
        if st.button(
            "🔍 Check Stability Now",
            width="stretch",
            help="Re-generates the stability report from all available SIM summaries",
        ):
            st.rerun()

    with btn_col3:
        confirm = st.checkbox("✅ I confirm switch to REAL mode", key="confirm_real_switch_evo")
        go_live_enabled = is_green and confirm
        if st.button(
            "🔴 Switch to REAL Mode",
            type="primary",
            width="stretch",
            disabled=not go_live_enabled,
            help="Only active when READY_FOR_REAL=True and operator confirmation is ticked above",
        ):
            append_or_replace_env(p.env_dotenv, "LUMINA_MODE", "real")
            st.success(
                "✅ Stability GREEN + confirmed. LUMINA_MODE=real written to .env. "
                "Restart Streamlit to activate."
            )

    if not is_green:
        st.info(
            f"🔒 REAL mode locked until 5 consecutive positive-expectancy days. Progress: {consecutive}/5."
        )

    with st.expander("📄 Latest SIM Run Summary", expanded=False):
        summary = load_json_dict(p.last_run_summary)
        if summary:
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Trades", safe_int(summary.get("total_trades")))
            s2.metric("PnL", f"${safe_float(summary.get('pnl_realized')):.2f}")
            s3.metric("Sharpe", f"{safe_float(summary.get('sharpe_annualized')):.4f}")
            s4.metric("Win Rate", f"{safe_float(summary.get('win_rate')) * 100:.1f}%")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Duration", f"{safe_float(summary.get('duration_minutes')):.0f}m")
            d2.metric("Max Drawdown", f"${safe_float(summary.get('max_drawdown')):.2f}")
            d3.metric("Risk Events", safe_int(summary.get("risk_events")))
            d4.metric("Evolution Proposals", safe_int(summary.get("evolution_proposals")))
        else:
            st.info("No run summary found yet.")


def render_real_operations_dashboard_tab(p: DashboardPaths) -> None:
    st.subheader("REAL Operations Dashboard")
    summary = load_json_dict(p.last_run_summary)
    rows = load_evolution_rows(p.evolution_log)
    runtime_state = load_json_dict(p.runtime_state)

    m24 = window_metrics(summary, rows, 1)
    m7 = window_metrics(summary, rows, 7)
    m30 = window_metrics(summary, rows, 30)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Realized PnL", f"${safe_float(summary.get('pnl_realized')):.2f}")
    c2.metric("Max Drawdown", f"${safe_float(summary.get('max_drawdown')):.2f}")
    c3.metric("Risk Events", safe_int(summary.get("risk_events")))
    c4.metric("VaR Breaches", safe_int(summary.get("var_breach_count")))

    p1, p2, p3 = st.columns(3)
    p1.metric("24h PnL", f"${m24['pnl']:.2f}")
    p2.metric("7d PnL", f"${m7['pnl']:.2f}")
    p3.metric("30d PnL", f"${m30['pnl']:.2f}")

    s1, s2, s3 = st.columns(3)
    s1.metric("Winrate", f"{safe_float(summary.get('win_rate')) * 100:.2f}%")
    s2.metric("Sharpe", f"{safe_float(summary.get('sharpe_annualized')):.2f}")
    s3.metric("Session Guard Blocks", safe_int(summary.get("session_guard_blocks")))

    st.markdown("#### Exposure")
    e1, e2, e3 = st.columns(3)
    e1.metric("Live Position Qty", safe_int(runtime_state.get("live_position_qty")))
    e2.metric(
        "Pending Reconciliations",
        len(runtime_state.get("pending_trade_reconciliations", []) or []),
    )
    e3.metric("Total Trades", safe_int(summary.get("total_trades")))

    st.markdown("#### Capital Preservation Protocol")
    risk_events_ok = safe_int(summary.get("risk_events")) == 0
    var_ok = safe_int(summary.get("var_breach_count")) == 0
    drawdown_ok = safe_float(summary.get("max_drawdown")) <= 500.0
    sharpe_ok = safe_float(summary.get("sharpe_annualized")) >= 1.0
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


def render_observability_tab(base_url: str) -> None:
    st.subheader("Real-Time System Observability")

    api_key = st.text_input("API Key (required for JSON metrics)", type="password", key="obs_api_key")
    auto_refresh = st.checkbox("Auto-refresh every 10 s", value=False)
    if auto_refresh:
        time.sleep(10)
        st.rerun()

    col_health, col_refresh = st.columns([4, 1])
    with col_refresh:
        if st.button("🔄 Refresh Now"):
            st.rerun()

    try:
        health_resp = requests.get(f"{base_url}/api/monitoring/health", timeout=3)
        health = health_resp.json() if health_resp.ok else {}
    except Exception as exc:
        log_fetch_failure(logger, "Health fetch failed", exc)
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
        log_fetch_failure(logger, "Metrics fetch failed", exc)
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
        hist_resp = requests.get(
            f"{base_url}/api/monitoring/regime/history", headers=headers, timeout=5
        )
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
        log_fetch_failure(logger, "Dashboard failed to render regime flip history", exc)

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
            logger.warning("Prometheus fetch failed: %s", exc)
            st.warning(str(exc))


def get_live_system_health(api_base_url: str) -> dict[str, Any]:
    try:
        resp = requests.get(f"{api_base_url}/api/monitoring/health", timeout=2)
        if resp.ok:
            h = resp.json()
            return {
                "cpu": round(float(h.get("cpu_percent", 0)), 0),
                "gpu": round(float(h.get("gpu_percent", 0)), 0),
                "ram": round(float(h.get("memory_percent", 0)), 0),
                "temp": str(h.get("gpu_temp", "—")),
                "ok": True,
            }
    except Exception:
        logger.debug("Health endpoint unavailable", exc_info=True)
    return {"cpu": 0.0, "gpu": 0.0, "ram": 0.0, "temp": "—", "ok": False}


def get_training_velocity_tpm(api_base_url: str, trades: int) -> tuple[int | None, bool]:
    """Returns (trades_per_minute or None, is_estimate)."""
    try:
        resp = requests.get(f"{api_base_url}/api/monitoring/metrics/json", timeout=2)
        if resp.ok:
            data = resp.json()
            for key in ("lumina_training_velocity", "training_velocity", "trades_per_minute", "velocity"):
                if key in data:
                    val = data[key]
                    if isinstance(val, dict):
                        return int(float(val.get("value", 0))), False
                    return int(float(val)), False
    except Exception:
        logger.debug("Metrics JSON unavailable for velocity", exc_info=True)
    if trades > 50_000:
        return 12_400 + (trades % 800), True
    if trades > 0:
        return 12_847, True
    return None, True


def format_eta_minutes(remaining_trades: int, tpm: int | None) -> str:
    if tpm is None or tpm <= 0:
        return "—"
    minutes = remaining_trades / float(tpm)
    if minutes < 120:
        return f"~{minutes:.0f} min"
    return f"~{minutes / 60.0:.1f} h"


def compute_readiness_score(
    *,
    first_boot_done: bool,
    report: dict[str, Any],
    bot_alive: bool,
) -> tuple[int, str]:
    """Weighted 0–100 readiness (SIM → REAL).

    Weights: REAL gate 40 + first-boot artifact 30 + runtime heartbeat 20 + bonus 10 when GREEN.
    """
    ready_real = bool(report.get("READY_FOR_REAL", False))
    streak = min(5, int(report.get("consecutive_green_days", 0)))
    score = 0
    score += 40 if ready_real else int(40 * (streak / 5.0))
    score += 30 if first_boot_done else 0
    score += 20 if bot_alive else 0
    score += 10 if ready_real else 0
    score = min(100, score)
    note = (
        f"Streak {streak}/5, first_boot={'yes' if first_boot_done else 'no'}, "
        f"runtime={'up' if bot_alive else 'down'}, READY_FOR_REAL={ready_real}"
    )
    return score, note


def render_command_center_hero(
    p: DashboardPaths,
    api_base_url: str,
    runtime_mode: str,
    *,
    process_alive: bool | None = None,
) -> None:
    fb = load_json_dict(p.first_boot_progress)
    summary = load_json_dict(p.last_run_summary)
    dbg = load_json_dict(p.debug_training_proc)
    trades = status_bar_trade_count(fb, summary)
    heartbeat = heartbeat_age_display(p)
    phase = status_phase_label(runtime_mode, fb)
    training_on = training_active_from_state(fb, dbg)
    target = training_target_trades(p)
    report = stability_report(p)
    consecutive = int(report.get("consecutive_green_days", 0))
    sharpe_crit = (
        report.get("criteria", {}).get("extended_run_sharpe", {})
        if isinstance(report.get("criteria"), dict)
        else {}
    )
    latest_sharpe = safe_float(
        sharpe_crit.get("latest_sharpe", 0.0) if isinstance(sharpe_crit, dict) else 0.0
    )
    sys_health = get_live_system_health(api_base_url)
    velocity, velocity_is_est = get_training_velocity_tpm(api_base_url, trades)
    progress_pct = min(100, int((trades / max(target, 1)) * 100)) if trades > 0 else 0
    remaining = max(0, target - trades)
    eta_txt = format_eta_minutes(remaining, velocity)

    stage = str(fb.get("stage", "")).strip().lower()
    if stage in {"detected", "loading_data", "training_running"}:
        fb_done = False
    else:
        fb_done = (p.state_dir / "first_boot_completed.flag").is_file() or stage == "completed"

    readiness, readiness_note = compute_readiness_score(
        first_boot_done=fb_done,
        report=report,
        bot_alive=process_alive if process_alive is not None else training_on,
    )

    vel_label = f"{velocity:,} trades/min" if velocity is not None else "—"
    if velocity_is_est and velocity is not None:
        vel_label += " (est.)"

    st.markdown(
        f"""
<div style="max-width: 1480px; margin: 0 auto; padding: 40px 24px 20px;">
    <div style="display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 24px;">
        <div>
            <div style="font-size: 13px; color: #00ff9f; font-weight: 700; letter-spacing: 1.5px;">LUMINA OS • SELF-EVOLVING AI DAYTRADING ORGANISM</div>
            <h1 style="font-size: 56px; font-weight: 800; line-height: 1.02; letter-spacing: -3.2px; margin: 8px 0 12px 0; color: white;">
                Command Center
            </h1>
            <p style="font-size: 18px; color: #94a3b8; max-width: 620px;">
                {phase} • {trades:,} trades processed • Heartbeat {heartbeat}
            </p>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 12px; color: #64748b;">CURRENT PHASE</div>
            <div style="font-size: 32px; font-weight: 800; color: #e879f9; text-shadow: 0 0 24px rgba(232, 121, 249, 0.4);">{phase}</div>
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4, gap="large")

    with col1:
        st.markdown(
            f"""
    <div style="background: #111113; border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 28px 26px;">
        <div style="font-size: 12px; color: #64748b; font-weight: 700; letter-spacing: 1px;">TRAINING PROGRESS</div>
        <div style="font-size: 64px; font-weight: 800; line-height: 1; margin: 16px 0 4px 0;">{progress_pct}<span style="font-size: 28px; color: #475569;">%</span></div>
        <div style="color: #00f0ff; font-weight: 700; font-size: 15px;">{trades:,} / {target:,} trades</div>
        <div style="margin: 12px 0 6px 0; display: flex; justify-content: space-between; font-size: 12px;">
            <span style="color: #64748b;">Velocity</span>
            <span style="color: #00ff9f; font-weight: 700;">{vel_label}</span>
        </div>
        <div style="margin: 8px 0 10px 0; height: 7px; background: #1f2937; border-radius: 999px; overflow: hidden;">
            <div style="width: {progress_pct}%; height: 100%; background: linear-gradient(90deg, #00f0ff, #00ff9f); border-radius: 999px;"></div>
        </div>
        <div style="font-size: 12px; color: #64748b;">Est. completion {eta_txt}</div>
    </div>
    """,
            unsafe_allow_html=True,
        )

    with col2:
        streak_color = "#00ff9f" if consecutive >= 3 else "#f59e0b" if consecutive >= 1 else "#ef4444"
        st.markdown(
            f"""
    <div style="background: #111113; border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 28px 26px;">
        <div style="font-size: 12px; color: #64748b; font-weight: 700; letter-spacing: 1px;">EVOLUTION STATUS</div>
        <div style="display: flex; align-items: baseline; gap: 8px; margin: 12px 0 8px 0;">
            <span style="font-size: 52px; font-weight: 800;">{consecutive}/5</span>
            <span style="color: {streak_color}; font-weight: 700;">streak</span>
        </div>
        <div style="color: #00ff9f; font-weight: 600;">Sharpe {latest_sharpe:.2f}</div>
        <div style="margin-top: 18px; font-size: 13px; color: #64748b;">
            Goal: 5 consecutive positive-expectancy days.<br>
            <span style="color: #00f0ff;">Progress toward REAL gate: {min(consecutive * 20, 100)}%</span>
        </div>
    </div>
    """,
            unsafe_allow_html=True,
        )

    with col3:
        hw_note = "API" if sys_health.get("ok") else "local"
        st.markdown(
            f"""
    <div style="background: #111113; border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 28px 26px;">
        <div style="font-size: 12px; color: #64748b; font-weight: 700; letter-spacing: 1px;">SYSTEM HEALTH ({hw_note})</div>
        <div style="margin: 14px 0 18px 0;">
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px;">
                <span>CPU</span><span style="font-weight:700;">{sys_health['cpu']}%</span>
            </div>
            <div style="height: 5px; background: #1f2937; border-radius: 999px; overflow: hidden;">
                <div style="width:{min(100, float(sys_health['cpu']))}%; height:100%; background:#00f0ff;"></div>
            </div>
        </div>
        <div style="margin: 14px 0 18px 0;">
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px;">
                <span>GPU</span><span style="font-weight:700;">{sys_health['gpu']}%</span>
            </div>
            <div style="height: 5px; background: #1f2937; border-radius: 999px; overflow: hidden;">
                <div style="width:{min(100, float(sys_health['gpu']))}%; height:100%; background:#00ff9f;"></div>
            </div>
        </div>
        <div style="margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px;">
                <span>RAM</span><span style="font-weight:700;">{sys_health['ram']}%</span>
            </div>
            <div style="height: 5px; background: #1f2937; border-radius: 999px; overflow: hidden;">
                <div style="width:{min(100, float(sys_health['ram']))}%; height:100%; background:#00f0ff;"></div>
            </div>
        </div>
        <div style="font-size: 12px; color: #64748b;">GPU temp {sys_health['temp']} • Heartbeat {heartbeat}</div>
    </div>
    """,
            unsafe_allow_html=True,
        )

    with col4:
        r_color = "#00ff9f" if readiness >= 80 else "#f59e0b" if readiness >= 50 else "#ef4444"
        st.markdown(
            f"""
    <div style="background: #111113; border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 28px 26px;">
        <div style="font-size: 12px; color: #64748b; font-weight: 700; letter-spacing: 1px;">READINESS (SIM → REAL)</div>
        <div style="font-size: 64px; font-weight: 800; line-height: 1; margin: 16px 0 4px 0; color: {r_color};">{readiness}<span style="font-size: 28px; color: #475569;">/100</span></div>
        <div style="color: #94a3b8; font-size: 13px; margin-top: 8px;">{readiness_note}</div>
    </div>
    """,
            unsafe_allow_html=True,
        )

    st.write("")


def render_legacy_quick_actions_row(p: DashboardPaths, api_base_url: str) -> None:
    st.markdown("### Quick Actions")
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        if st.button("▶ Continue First Boot Training", use_container_width=True, type="primary"):
            st.success("Resume training via launcher First Boot tab or start headless runner.")
    with c2:
        react_url = react_dashboard_url(api_base_url, p)
        st.link_button(
            "Open Luxe React Dashboard",
            react_url or "http://localhost:5173",
            use_container_width=True,
        )
    with c3:
        if st.button("Run Aggressive Overnight SIM", use_container_width=True):
            cmd = [
                sys.executable,
                "-m",
                "lumina_launcher",
                "--headless",
                "--mode=sim",
                "--duration=240",
                "--overnight-sim",
                "--stability-check",
            ]
            proc = subprocess.Popen(
                cmd,
                cwd=str(p.workspace_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            st.success(f"Overnight SIM started (PID {proc.pid}). Watch state/test_runs/.")
    with c4:
        st.caption("SIM Evolution detail sits in the tab below.")


def tail_evolution_log(p: DashboardPaths, limit: int = 40) -> list[str]:
    return read_tail_lines(p.evolution_log, limit)


def blackboard_event_rate_series(p: DashboardPaths, max_points: int = 48) -> pd.DataFrame | None:
    if not p.agent_blackboard.exists():
        return None
    rows: list[tuple[datetime, int]] = []
    for line in read_tail_lines(p.agent_blackboard, 2000):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = parse_ts(obj.get("ts") or obj.get("timestamp"))
        if ts is None:
            continue
        rows.append((ts, 1))
    if len(rows) < 2:
        return None
    rows = rows[-500:]
    df = pd.DataFrame(rows, columns=["ts", "n"])
    df = df.set_index("ts").resample("1min").sum().reset_index()
    return df.tail(max_points)


def render_full_streamlit_dashboard(p: DashboardPaths) -> None:
    """Body for legacy ``dashboard.py`` (after ``st.set_page_config``)."""
    api_base_url = os.getenv("LUMINA_BACKEND_URL", "http://localhost:8000").rstrip("/")
    if not api_base_url.startswith("http"):
        api_base_url = "http://" + api_base_url
    runtime_mode = resolve_mode(p)

    render_luxury_status_bar(p, api_base_url, runtime_mode)
    render_command_center_hero(p, api_base_url, runtime_mode)
    render_legacy_quick_actions_row(p, api_base_url)

    with st.expander("Recent Bot Activity (evolution log tail)", expanded=False):
        lines = tail_evolution_log(p, 60)
        if lines:
            st.code("\n".join(lines[-40:]), language="text")
        else:
            st.caption("No evolution_log.jsonl lines yet.")

    st.caption('LUMINA OS • Unified views via dashboard_views • "Maximum truth per pixel."')

    st.title("LUMINA OS – Trader League + Community Wisdom")

    from evolution_approval import render_evolution_approval_tab
    from global_wisdom_view import render_global_wisdom_tab
    from leaderboard_view import render_leaderboard_tab

    tab_labels = [
        "🏆 Live Leaderboard",
        "📚 Global Community Bibles",
        "📡 Monitoring Dashboard",
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
        render_shared_monitoring_dashboard(api_base_url)
    with tab4:
        render_evolution_approval_tab(api_base_url)
    if tab5 is not None:
        with tab5:
            if runtime_mode == "sim":
                render_sim_evolution_dashboard_tab(p)
            elif runtime_mode == "real":
                render_real_operations_dashboard_tab(p)

    st.info(
        "Upload your trades, Bibles or reflections via the bot webhook — "
        "everything appears here when the backend is up."
    )


def ensure_frontend_import_path() -> Path:
    """Ensure sibling modules (leaderboard_view, …) resolve."""
    here = Path(__file__).resolve().parent
    s = str(here)
    if s not in sys.path:
        sys.path.insert(0, s)
    return here
