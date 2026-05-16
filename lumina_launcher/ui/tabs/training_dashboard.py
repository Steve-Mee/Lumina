"""LUMINA OS «Training Dashboard» tab inside the unified Streamlit launcher.

Surfaces the same state files and API endpoints as ``dashboard_views`` plus launcher
services (first-boot, process manager, hardware snapshot) for SIM→REAL clarity.
"""

from __future__ import annotations

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.observability import log_event, timed_event
from lumina_launcher.core.process_manager import ProcessManager
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
    resolve_mode,
    stability_report,
    tail_evolution_log,
    training_dashboard_fallback_url,
)

logger = logging.getLogger(__name__)


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
    if auto and hasattr(st, "autorefresh"):
        st.autorefresh(interval=10_000, key="lumina_training_autorefresh_tick")

    render_luxury_status_bar(p, api_base, runtime_mode)

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

    st.subheader("Quick actions")
    q1, q2, q3, q4, q5 = st.columns(5)
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
    with q5:
        st.link_button(
            "Full dashboard (8502)",
            training_dashboard_fallback_url(8502),
            use_container_width=True,
        )

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
            st.line_chart(dfh.set_index("day")["sharpe"], height=220)
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
            st.area_chart(bb.set_index("ts")["n"], height=200)
        else:
            st.caption("No `agent_blackboard.jsonl` samples.")
    with t4:
        evo = tail_evolution_log(p, 200)
        st.markdown("##### Evolution log (tail)")
        if evo:
            st.code("\n".join(evo[-25:]), language="text")
        else:
            st.caption("No evolution lines yet.")

    with st.expander("Monitoring (embedded)", expanded=False):
        render_shared_monitoring_dashboard(api_base)

    with st.expander("Evolution approvals", expanded=False):
        fn = _import_evolution_approval()
        if callable(fn):
            fn(api_base)
        else:
            st.error("Could not load evolution_approval module.")

    with st.expander("SIM evolution (full panel)", expanded=False):
        render_sim_evolution_dashboard_tab(p)

    st.caption(
        f"Mode={runtime_mode} | Backend={api_base} | "
        f"First-boot artifacts missing={first_boot_manager.artifacts_missing()}"
    )
