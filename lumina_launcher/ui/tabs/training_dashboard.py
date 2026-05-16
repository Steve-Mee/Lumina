"""LUMINA OS «Training Dashboard» tab inside the unified Streamlit launcher.

Surfaces the same state files and API endpoints as ``dashboard_views`` plus launcher
services (first-boot, process manager, hardware snapshot) for SIM→REAL clarity.
"""

from __future__ import annotations

import importlib.util
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from lumina_core.first_boot_progress import (
    resolve_ppo_training_progress,
    resolve_first_boot_completed_trades,
    resolve_first_boot_target_from_progress,
    resolve_first_boot_stage,
)
from lumina_core.runtime_session import resolve_runtime_session_state
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.observability import log_event, timed_event
from lumina_launcher.core.process_manager import ProcessManager
from lumina_launcher.ui.auto_refresh import run_with_autorefresh
from lumina_launcher.services.hardware_service import HardwareService
from lumina_os.frontend.dashboard_views import (
    DashboardPaths,
    blackboard_event_rate_series,
    load_json_dict,
    load_stability_history,
    render_command_center_hero,
    render_luxury_status_bar,
    render_shared_monitoring_dashboard,
    render_sim_evolution_dashboard_tab,
    react_dashboard_url,
    resolve_mode,
    stability_report,
    tail_evolution_log,
)

logger = logging.getLogger(__name__)


def _progress_age_seconds(progress: dict[str, object]) -> float | None:
    raw = str(progress.get("timestamp") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
    except Exception:
        return None


def _render_dark_line_chart(df: pd.DataFrame, x_col: str, y_col: str, y_title: str, height: int = 220) -> None:
    chart = (
        alt.Chart(df)
        .mark_line(color="#00f0ff", strokeWidth=2.2)
        .encode(
            x=alt.X(f"{x_col}:N", axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8")),
            y=alt.Y(f"{y_col}:Q", title=y_title, axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8")),
            tooltip=[x_col, y_col],
        )
        .properties(height=height)
        .configure(background="#0f1118")
        .configure_view(strokeOpacity=0, fill="#0f1118")
        .configure_axis(gridColor="#1f2937")
    )
    st.altair_chart(chart, use_container_width=True)


def _render_dark_area_chart(df: pd.DataFrame, x_col: str, y_col: str, y_title: str, height: int = 200) -> None:
    chart = (
        alt.Chart(df)
        .mark_area(color="#00a8ff", opacity=0.42, line={"color": "#00f0ff", "strokeWidth": 2.0})
        .encode(
            x=alt.X(f"{x_col}:T", axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8")),
            y=alt.Y(f"{y_col}:Q", title=y_title, axis=alt.Axis(labelColor="#94a3b8", titleColor="#94a3b8")),
            tooltip=[x_col, y_col],
        )
        .properties(height=height)
        .configure(background="#0f1118")
        .configure_view(strokeOpacity=0, fill="#0f1118")
        .configure_axis(gridColor="#1f2937")
    )
    st.altair_chart(chart, use_container_width=True)


def _render_dark_log_block(lines: list[str], *, height_px: int = 220) -> None:
    payload = "\n".join(lines) if lines else "No evolution lines yet."
    escaped = payload.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
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
  white-space: pre;
">{escaped}</div>
""",
        unsafe_allow_html=True,
    )


def _import_evolution_approval():
    repo = Path(__file__).resolve().parents[3]
    path = repo / "lumina_os" / "frontend" / "evolution_approval.py"
    spec = importlib.util.spec_from_file_location("_lumina_evolution_approval_", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "render_evolution_approval_tab", None)


def render_training_dashboard_tab(
    workspace_root: Path,
    *,
    first_boot_manager: FirstBootManager,
    hardware_service: HardwareService,
    process_manager: ProcessManager,
    backend_base_url: str,
) -> None:
    p = DashboardPaths(workspace_root)
    api_base = backend_base_url.rstrip("/")
    if not api_base.startswith("http"):
        api_base = "http://" + api_base

    runtime_mode = resolve_mode(p)
    if not p.state_dir.exists():
        st.warning("State directory missing — create via runtime or First Boot.")
        st.info("Use **🚀 First Boot** when you are ready to train.")
    elif not any(p.state_dir.iterdir()):
        st.info("State directory is empty — training idle or First Boot not started.")

    auto = st.checkbox("Auto-refresh (10s)", value=False, key="lumina_training_autorefresh")

    def _dashboard_body() -> None:
        render_luxury_status_bar(p, api_base, runtime_mode)

        overview_tab, monitor_tab, evo_tab, sim_tab, react_tab = st.tabs(
            ["Overview", "Monitoring", "Evolution approvals", "SIM evolution", "React dashboard"]
        )

        with overview_tab:
            process_alive = process_manager.is_process_alive()
            render_command_center_hero(p, api_base, runtime_mode, process_alive=process_alive)

            try:
                snap = hardware_service.get_snapshot(refresh=False)
                h1, h2, h3, h4 = st.columns(4)
                h1.metric("Host CPU (logical)", snap.cpu_cores_logical)
                h2.metric("Host RAM (GB)", f"{snap.ram_gb:.1f}")
                h3.metric("GPU VRAM (GB)", f"{snap.gpu_vram_gb:.1f}")
                h4.metric("Runtime process", "alive" if process_alive else "down")
            except Exception:
                logger.exception("Hardware snapshot unavailable")

            st.subheader("First Boot Result")
            first_boot_progress = first_boot_manager.read_progress()
            first_boot_stage = resolve_first_boot_stage(first_boot_progress) or "unknown"
            first_boot_completed = first_boot_manager.is_completed()
            ppo_phase = first_boot_manager.is_ppo_training_phase(first_boot_progress)
            ppo_interrupted = first_boot_manager.is_ppo_interrupted(
                progress=first_boot_progress,
                process_alive=process_alive,
                policy_exists=first_boot_manager.policy_path.exists(),
            )
            completed_trades = resolve_first_boot_completed_trades(first_boot_progress)
            first_boot_settings = first_boot_manager.read_settings()
            runtime_session = resolve_runtime_session_state(
                first_boot_stage=first_boot_stage,
                process_alive=process_alive,
                current_mode=runtime_mode,
                first_boot_timestamp=str(first_boot_progress.get("timestamp") or ""),
            )
            target_trades = int(
                resolve_first_boot_target_from_progress(first_boot_progress)
                or first_boot_settings.get("training_trades", 0)
                or 0
            )
            show_target = (
                first_boot_manager.is_user_configured()
                and runtime_session.training_target_applicable
                and target_trades > 0
            )
            ppo_meta = load_json_dict(p.state_dir / "ppo_policy_metadata.json")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric(
                "Completion",
                "Completed" if first_boot_completed else ("PPO training" if ppo_phase else "In progress"),
            )
            r2.metric("Stage", first_boot_stage)
            r3.metric("Trades", f"{completed_trades:,}/{target_trades:,}" if show_target else "Not configured")
            r4.metric("Policy version", str(ppo_meta.get("policy_version", "unknown")))
            if ppo_phase and not first_boot_completed:
                st.info(
                    "SIM-deel is voltooid (alle trades gesimuleerd). PPO policy-training loopt nog; "
                    "het samenvattingsscherm in **First Boot** verschijnt na voltooiing."
                )
                ppo_steps, ppo_total, ppo_pct = resolve_ppo_training_progress(first_boot_progress)
                st.progress(
                    max(0.0, min(1.0, float(ppo_steps) / float(max(1, ppo_total)))),
                    text=f"PPO progress: {ppo_steps:,}/{ppo_total:,} timesteps ({(ppo_pct or 0.0):.1f}%)",
                )
                ppo_c1, ppo_c2, ppo_c3 = st.columns(3)
                ppo_c1.metric("PPO steps", f"{ppo_steps:,}")
                ppo_c2.metric("PPO total", f"{ppo_total:,}")
                ppo_c3.metric("PPO progress", f"{(ppo_pct or 0.0):.1f}%")
                age_sec = _progress_age_seconds(first_boot_progress)
                if process_alive and age_sec is not None and age_sec > 120:
                    st.warning("PPO lijkt vastgelopen: geen nieuwe progress-update in > 2 minuten.")
                elif process_alive:
                    st.caption("PPO actief — live progress wordt bijgewerkt.")
                elif ppo_interrupted:
                    st.error("PPO-training onderbroken: runtime is niet actief en policy ontbreekt nog.")
            st.caption(
                "Strict completion rule active: requires both first_boot_completed.flag and "
                "lumina_ppo_policy.zip."
            )

            st.subheader("Quick actions")
            q1, q2, q3, q4 = st.columns(4)
            with q1:
                if st.button("⏸ Pause training", key="td_pause", use_container_width=True):
                    first_boot_manager.request_pause()
                    st.warning("Pause requested — training stops at next checkpoint.")
            with q2:
                if st.button("▶ Resume training", key="td_resume", use_container_width=True):
                    first_boot_manager.clear_pause_request()
                    st.success("Resume signal cleared.")
            with q3:
                if st.button("🌙 Overnight SIM", key="td_overnight", use_container_width=True):
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
                    with timed_event("launcher.training.overnight_sim"):
                        proc = subprocess.Popen(
                            cmd,
                            cwd=str(workspace_root),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    log_event("launcher.training.overnight_sim_started", pid=proc.pid)
                    st.success(f"Overnight SIM PID {proc.pid}")
            with q4:
                if st.button("🔍 Stability refresh", key="td_stab", use_container_width=True):
                    stability_report(p)
                    st.rerun()
            st.subheader("Trends")
            t1, t2 = st.columns(2)
            with t1:
                hist = load_stability_history(p)
                if len(hist) >= 2:
                    tail = hist[-14:]
                    dfh = pd.DataFrame(
                        {
                            "sharpe": [float(x.get("sharpe_annualized") or 0) for x in tail],
                            "day": [str(x.get("day", "")) for x in tail],
                        }
                    )
                    st.markdown("##### Rolling Sharpe (history)")
                    _render_dark_line_chart(dfh, "day", "sharpe", "Sharpe")
                else:
                    st.caption("Not enough `sim_stability_history` rows yet.")
            with t2:
                summary = load_json_dict(p.last_run_summary)
                st.markdown("##### Last run snapshot")
                if summary:
                    st.metric("Sharpe (last)", f"{float(summary.get('sharpe_annualized') or 0):.3f}")
                    st.metric("Max DD", f"${float(summary.get('max_drawdown') or 0):.2f}")
                    st.metric("Win rate", f"{float(summary.get('win_rate') or 0) * 100:.1f}%")
                else:
                    st.caption("No `last_run_summary.json` yet.")

            t3, t4 = st.columns(2)
            with t3:
                bb = blackboard_event_rate_series(p)
                st.markdown("##### Blackboard events / minute")
                if bb is not None and not bb.empty:
                    bb_chart = bb.copy()
                    bb_chart["ts"] = pd.to_datetime(bb_chart["ts"], utc=True)
                    _render_dark_area_chart(bb_chart, "ts", "n", "Events / min")
                else:
                    st.caption("No `agent_blackboard.jsonl` samples.")
            with t4:
                evo = tail_evolution_log(p, 200)
                st.markdown("##### Evolution log (tail)")
                _render_dark_log_block(evo[-25:] if evo else [])

        with monitor_tab:
            render_shared_monitoring_dashboard(api_base)

        with evo_tab:
            fn = _import_evolution_approval()
            if callable(fn):
                fn(api_base)
            else:
                st.error("Could not load evolution_approval module.")

        with sim_tab:
            render_sim_evolution_dashboard_tab(p)

        with react_tab:
            react_url = react_dashboard_url(api_base, p)
            st.caption("Dezelfde React cockpit als /ui/, ingebed in het command center.")
            if react_url:
                try:
                    components.iframe(react_url, height=980, scrolling=True)
                except Exception:
                    st.link_button("Open React Dashboard", react_url, use_container_width=True)
            else:
                st.info("React dashboard URL kon niet bepaald worden.")

        st.caption(
            f"Mode={runtime_mode} | Backend={api_base} | "
            f"First-boot artifacts missing={first_boot_manager.artifacts_missing()}"
        )

    run_with_autorefresh(_dashboard_body, enabled=auto, interval_seconds=10)
    st.caption("Auto-refresh keeps active tab content up to date.")
