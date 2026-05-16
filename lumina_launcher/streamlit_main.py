"""Streamlit UI for LUMINA OS Launcher. Loaded by ``streamlit_launcher.py``."""

from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from lumina_core.engine.setup_service import SetupService
from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.core.process_manager import ProcessManager
from lumina_launcher.observability import ensure_run_id, log_event, timed_event
from lumina_launcher.services.backend_client import BackendClient
from lumina_launcher.services.hardware_service import HardwareService
from lumina_launcher.services.model_service import ModelService
from lumina_launcher.ui.components.presence_strip import render_presence_strip
from lumina_launcher.ui.help_texts import help_for
from lumina_launcher.ui.setup_wizard import render_setup_wizard
from lumina_launcher.ui.tabs.community_bibles import render_community_bibles_tab
from lumina_launcher.ui.tabs.first_boot import render_first_boot_tab
from lumina_launcher.ui.tabs.live_activity import render_live_activity_tab
from lumina_launcher.ui.tabs.training_dashboard import render_training_dashboard_tab

logger = logging.getLogger(__name__)

_LAUNCHER_ROOT = Path(__file__).resolve().parents[1]
_RUNTIME_ENTRY = Path("lumina_core/engine/runtime_entrypoint.py")
_STATE_PATH = _LAUNCHER_ROOT / "state" / "lumina_sim_state.json"
_TRACE_INTERVAL_OPTIONS = [0, 1, 2, 5, 10]
_LATENCY_SLA_OPTIONS = [150, 250, 400, 700, 1000]


@dataclass
class LauncherServices:
    setup_service: SetupService
    config_manager: ConfigManager
    process_manager: ProcessManager
    first_boot_manager: FirstBootManager
    hardware_service: HardwareService
    model_service: ModelService
    backend_client: BackendClient


@st.cache_resource
def _get_services() -> LauncherServices:
    return LauncherServices(
        setup_service=SetupService(
            workspace_root=_LAUNCHER_ROOT,
            config_path=_LAUNCHER_ROOT / "config.yaml",
            env_path=_LAUNCHER_ROOT / ".env",
        ),
        config_manager=ConfigManager(_LAUNCHER_ROOT / ".env", _LAUNCHER_ROOT / "config.yaml"),
        process_manager=ProcessManager(_LAUNCHER_ROOT, _RUNTIME_ENTRY),
        first_boot_manager=FirstBootManager(_LAUNCHER_ROOT),
        hardware_service=HardwareService(_LAUNCHER_ROOT),
        model_service=ModelService(_LAUNCHER_ROOT / "lumina_model_catalog.json"),
        backend_client=BackendClient(),
    )


def _load_runtime_state() -> dict:
    if not _STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        logger.exception("Could not load runtime state")
        return {}


def _ensure_backend_running(session_state: dict) -> bool:
    now = time.time()
    last = float(session_state.get("lumina_backend_check_ts", 0.0) or 0.0)
    cached = bool(session_state.get("lumina_backend_alive", False))
    if now - last < 5.0:
        return cached
    try:
        started = time.perf_counter()
        with socket.create_connection(("localhost", 8000), timeout=1.2):
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            session_state["lumina_backend_check_ts"] = now
            session_state["lumina_backend_alive"] = True
            log_event("launcher.health.backend_tcp", ok=True, duration_ms=elapsed_ms, port=8000)
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        session_state["lumina_backend_check_ts"] = now
        session_state["lumina_backend_alive"] = False
        log_event("launcher.health.backend_tcp", level=logging.DEBUG, ok=False, port=8000)
        return False


def _current_mode(config_manager: ConfigManager) -> str:
    env_values = config_manager.parse_env_file()
    env_mode = str(env_values.get("TRADE_MODE", "") or "").strip().lower()
    if env_mode in {"paper", "sim", "sim_real_guard", "real"}:
        return env_mode
    cfg = config_manager.load_yaml_config()
    mode = str(cfg.get("mode", "sim")).strip().lower()
    return mode if mode in {"paper", "sim", "sim_real_guard", "real"} else "sim"


def _persist_prestart_settings(
    *,
    config_manager: ConfigManager,
    first_boot_manager: FirstBootManager,
    mode: str,
    risk_profile: str,
    instrument: str,
    voice_enabled: bool,
    screen_share_enabled: bool,
    dashboard_enabled: bool,
    runtime_trace: bool,
    runtime_trace_interval: int,
    latency_sla_ms: int,
    require_real_simulator_data: bool,
    first_boot_trades: int,
) -> None:
    broker_backend = "paper" if mode == "paper" else "live"
    account_mode = "real" if mode == "real" else ("sim" if mode in {"sim", "sim_real_guard"} else "paper")
    updates = {
        "TRADE_MODE": mode,
        "LUMINA_MODE": mode,
        "BROKER_BACKEND": broker_backend,
        "TRADERLEAGUE_ACCOUNT_MODE": account_mode,
        "LUMINA_RISK_PROFILE": risk_profile.lower(),
        "INSTRUMENT": instrument,
        "VOICE_ENABLED": str(voice_enabled).lower(),
        "SCREEN_SHARE_ENABLED": str(screen_share_enabled).lower(),
        "DASHBOARD_ENABLED": str(dashboard_enabled).lower(),
        "LUMINA_RUNTIME_TRACE": str(runtime_trace).lower(),
        "LUMINA_RUNTIME_TRACE_INTERVAL_SEC": str(runtime_trace_interval),
        "LUMINA_LATENCY_SLA_MS": str(latency_sla_ms),
        "ENABLE_SIM_REAL_GUARD": "true" if mode == "sim_real_guard" else "false",
    }
    with timed_event("launcher.config.save", mode=mode):
        config_manager.write_env_file(updates)
        existing = first_boot_manager.read_settings()
        first_boot_manager.save_full_settings(
            training_trades=int(first_boot_trades),
            prefer_real_data_only=bool(existing["prefer_real_data_only"]),
            max_real_days=int(existing["max_real_days"]),
            allow_minimal_synthetic_fallback=bool(existing["allow_minimal_synthetic_fallback"]),
            require_real_simulator_data=bool(require_real_simulator_data),
        )


def render_streamlit_app() -> None:
    st.set_page_config(page_title="LUMINA OS Launcher", layout="wide")
    run_id = ensure_run_id(st.session_state)
    log_event("launcher.rerun_started", run_id=run_id, seq=int(st.session_state.get("lumina_run_seq", 1)))
    services = _get_services()

    backend_up = _ensure_backend_running(st.session_state)
    if not backend_up:
        st.info(
            "Backend (FastAPI) lijkt niet te draaien op poort 8000. "
            "Start met `powershell -ExecutionPolicy Bypass -File .\\lumina_os\\run_backend.ps1`."
        )

    if services.setup_service.is_first_run():
        render_setup_wizard(
            workspace_root=_LAUNCHER_ROOT,
            setup_service=services.setup_service,
            config_manager=services.config_manager,
            first_boot_manager=services.first_boot_manager,
            hardware_service=services.hardware_service,
            model_service=services.model_service,
        )
        return

    state = _load_runtime_state()
    current_dream = state.get("current_dream", {}) if isinstance(state.get("current_dream"), dict) else {}
    snapshot = services.hardware_service.get_cached_snapshot() or services.hardware_service.get_snapshot()
    process_alive = services.process_manager.is_process_alive()
    current_mode = _current_mode(services.config_manager)
    first_boot = services.first_boot_manager.read_settings()

    st.title("LUMINA OS Launcher")
    render_presence_strip(
        {
            "pulse_live": process_alive,
            "last_activity_verbose": f"Mode={current_mode.upper()} • Backend={'UP' if backend_up else 'DOWN'}",
            "tpm_label": f"{int(state.get('total_trades', 0) or 0):,} trades",
        }
    )

    if services.first_boot_manager.artifacts_missing():
        st.warning("First-boot training is nog niet voltooid.")
    else:
        st.success("First-boot training artifacts zijn aanwezig.")

    with st.sidebar:
        st.header("Bot Configuration")
        mode = st.selectbox(
            "Trading Mode",
            options=["paper", "sim", "sim_real_guard", "real"],
            index=["paper", "sim", "sim_real_guard", "real"].index(current_mode if current_mode in {"paper", "sim", "sim_real_guard", "real"} else "sim"),
            help=help_for("trading_mode"),
        )
        risk_profile = st.selectbox(
            "Risk Profile",
            options=["Conservative", "Balanced", "Aggressive"],
            index=1,
            help=help_for("risk_profile"),
        )
        instrument = st.selectbox(
            "Instrument",
            options=["MES JUN26", "MNQ JUN26", "MYM JUN26", "ES JUN26"],
            index=0,
            help=help_for("instrument"),
        )
        first_boot_trades = st.number_input(
            "First-boot training trades",
            min_value=500,
            max_value=2_000_000,
            value=int(first_boot.get("training_trades", 500_000)),
            step=500,
            help=help_for("training_trades"),
        )
        require_real_simulator_data = st.checkbox(
            "Require real simulator data",
            value=bool(first_boot.get("require_real_simulator_data", True)),
            help=help_for("require_real_simulator_data"),
        )
        voice_enabled = st.checkbox("Voice (TTS + input)", value=True, help=help_for("voice_enabled"))
        screen_share_enabled = st.checkbox(
            "Live Chart Screen Share", value=True, help=help_for("screen_share_enabled")
        )
        dashboard_enabled = st.checkbox("Dashboard", value=True, help=help_for("dashboard_enabled"))
        runtime_trace = st.checkbox("Runtime trace", value=True, help=help_for("runtime_trace"))
        runtime_trace_interval = int(
            st.selectbox(
                "Runtime trace interval (sec)",
                options=_TRACE_INTERVAL_OPTIONS,
                index=0,
                help=help_for("runtime_trace_interval"),
            )
        )
        latency_sla_ms = int(
            st.selectbox(
                "Latency SLA (ms)",
                options=_LATENCY_SLA_OPTIONS,
                index=1,
                help=help_for("latency_sla"),
            )
        )
        if st.button("Save Config", use_container_width=True):
            _persist_prestart_settings(
                config_manager=services.config_manager,
                first_boot_manager=services.first_boot_manager,
                mode=mode,
                risk_profile=risk_profile,
                instrument=instrument,
                voice_enabled=voice_enabled,
                screen_share_enabled=screen_share_enabled,
                dashboard_enabled=dashboard_enabled,
                runtime_trace=runtime_trace,
                runtime_trace_interval=runtime_trace_interval,
                latency_sla_ms=latency_sla_ms,
                require_real_simulator_data=require_real_simulator_data,
                first_boot_trades=int(first_boot_trades),
            )
            st.success("Pre-start configuratie opgeslagen.")
        if st.button("Save Config and Start Bot", type="primary", use_container_width=True):
            _persist_prestart_settings(
                config_manager=services.config_manager,
                first_boot_manager=services.first_boot_manager,
                mode=mode,
                risk_profile=risk_profile,
                instrument=instrument,
                voice_enabled=voice_enabled,
                screen_share_enabled=screen_share_enabled,
                dashboard_enabled=dashboard_enabled,
                runtime_trace=runtime_trace,
                runtime_trace_interval=runtime_trace_interval,
                latency_sla_ms=latency_sla_ms,
                require_real_simulator_data=require_real_simulator_data,
                first_boot_trades=int(first_boot_trades),
            )
            ok, msg = services.process_manager.start_bot(mode="auto")
            st.success(msg) if ok else st.error(msg)
        if st.button("Stop Bot", use_container_width=True):
            ok, msg = services.process_manager.stop_bot()
            st.info(msg) if ok else st.error(msg)

    tab_labels: list[str] = [
        "📡 Live Activity",
        "🚀 First Boot",
        "Live Trader",
        "Hardware",
        "Model Mgmt",
        "Trader League",
        "SIM Evolution",
        "📊 LUMINA OS Dashboard",
        "📖 Community Bibles",
        "🛠️ Admin",
    ]
    if current_mode == "real":
        tab_labels.append("🛡️ REAL Operations")

    if hasattr(st, "segmented_control"):
        selected = st.segmented_control("Workspace", options=tab_labels, default=tab_labels[0])
        if selected is None:
            selected = tab_labels[0]
    else:
        selected = st.selectbox("Workspace", options=tab_labels, index=0)

    if selected == "📡 Live Activity":
        proc_state = services.process_manager._load_process_state()
        render_live_activity_tab(
            _LAUNCHER_ROOT,
            alive=process_alive,
            pid=int(proc_state.get("pid", 0) or 0) or None,
        )
    elif selected == "🚀 First Boot":
        render_first_boot_tab(services.first_boot_manager)
    elif selected == "Live Trader":
        from lumina_launcher.ui.tabs.live_trader import render_live_trader_tab

        render_live_trader_tab(state, current_dream)
    elif selected == "Hardware":
        from lumina_launcher.ui.tabs.hardware_tab import render_hardware_tab

        render_hardware_tab(services.hardware_service, services.model_service, snapshot)
    elif selected == "Model Mgmt":
        from lumina_launcher.ui.tabs.model_management_tab import render_model_management_tab

        render_model_management_tab(
            services.hardware_service, services.model_service, snapshot, setup_service=services.setup_service
        )
    elif selected == "Trader League":
        from lumina_launcher.ui.tabs.trader_league import render_trader_league_tab

        render_trader_league_tab(services.backend_client)
    elif selected == "SIM Evolution":
        from lumina_launcher.ui.tabs.sim_evolution import render_sim_evolution_tab

        render_sim_evolution_tab(_LAUNCHER_ROOT)
    elif selected == "📊 LUMINA OS Dashboard":
        render_training_dashboard_tab(
            _LAUNCHER_ROOT,
            first_boot_manager=services.first_boot_manager,
            hardware_service=services.hardware_service,
            process_manager=services.process_manager,
            backend_base_url=services.backend_client.base_url,
        )
    elif selected == "📖 Community Bibles":
        render_community_bibles_tab(services.backend_client)
    elif selected == "🛠️ Admin":
        from lumina_launcher.ui.tabs.admin import render_admin_tab

        render_admin_tab(services.backend_client)
    elif selected == "🛡️ REAL Operations":
        from lumina_launcher.ui.tabs.real_operations import render_real_operations_tab

        render_real_operations_tab(_LAUNCHER_ROOT)

    st.divider()
    st.caption("LUMINA OS Launcher — parity restored, modular, observable, and performance-focused.")
