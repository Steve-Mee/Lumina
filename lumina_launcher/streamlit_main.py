"""Streamlit UI for LUMINA OS Launcher. Loaded by ``streamlit_launcher.py``."""

from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import streamlit as st

from lumina_core.first_boot_progress import (
    resolve_first_boot_completed_trades,
    resolve_first_boot_target_from_progress,
    resolve_first_boot_stage,
)
from lumina_core.first_boot_ui import FIRST_BOOT_DEFAULT_TRADES
from lumina_core.runtime_session import resolve_runtime_session_state
from lumina_core.engine.setup_service import SetupService
from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.core.pause_policy import resolve_pause_policy
from lumina_launcher.core.process_manager import ProcessManager
from lumina_launcher.observability import ensure_run_id, log_event, timed_event
from lumina_launcher.services.backend_client import BackendClient
from lumina_launcher.services.hardware_service import HardwareService
from lumina_launcher.services.model_service import ModelService
from lumina_launcher.ui.components.presence_strip import render_presence_strip
from lumina_launcher.ui.help_texts import help_for
from lumina_launcher.ui.setup_wizard import render_setup_wizard
from lumina_launcher.ui.tab_registry import TabRenderContext, launcher_tab_specs
from lumina_launcher.ui.tabs.first_boot import render_first_boot_tab
from lumina_launcher.ui.tabs.training_dashboard import render_training_dashboard_tab

logger = logging.getLogger(__name__)

_LAUNCHER_ROOT = Path(__file__).resolve().parents[1]
_RUNTIME_ENTRY = Path("lumina_core/engine/runtime_entrypoint.py")
_STATE_PATH = _LAUNCHER_ROOT / "state" / "lumina_sim_state.json"
_TRACE_INTERVAL_OPTIONS = [0, 1, 2, 5, 10]
_LATENCY_SLA_OPTIONS = [150, 250, 400, 700, 1000]
_LAUNCHER_PREMIUM_CSS = """
<style>
section[data-testid="stMain"] {
  background:
    radial-gradient(circle at 11% 5%, rgba(0, 240, 255, 0.1), transparent 38%),
    radial-gradient(circle at 88% 12%, rgba(0, 255, 159, 0.08), transparent 34%),
    #0a0a0f;
}
h1, h2, h3, h4 {
  color: #e8e6e3;
}
.stApp [data-testid="stMarkdownContainer"] p {
  color: #9aa4b6;
}
.stApp [data-testid="stMarkdownContainer"] h5,
.stApp [data-testid="stMarkdownContainer"] h6 {
  color: #c8d3e2;
}
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  gap: 8px;
  border-radius: 14px;
  border: 1px solid rgba(0, 240, 255, 0.2);
  background: rgba(9, 10, 15, 0.7);
  padding: 8px;
}
[data-testid="stTabs"] [aria-selected="true"] {
  background: linear-gradient(92deg, rgba(0, 240, 255, 0.2), rgba(0, 255, 159, 0.13));
  border: 1px solid rgba(0, 240, 255, 0.35);
}
[data-testid="stTextInput"] > div > div,
[data-testid="stNumberInput"] > div > div > input,
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
  background: rgba(12, 14, 20, 0.9) !important;
  border-color: rgba(0, 240, 255, 0.28) !important;
  color: #e8e6e3 !important;
}
[data-testid="stSlider"] [role="slider"] {
  box-shadow: 0 0 0 2px rgba(0, 240, 255, 0.45) !important;
}
.stButton > button {
  background: linear-gradient(95deg, rgba(0, 240, 255, 0.2), rgba(0, 255, 159, 0.16)) !important;
  color: #e8e6e3 !important;
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
</style>
"""


class LauncherPhase(str, Enum):
    FIRST_BOOT_REQUIRED = "first_boot_required"
    OPERATIONS_READY = "operations_ready"


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
            mark_user_configured=False,
        )


def _resolve_launcher_phase(*, first_boot_manager: FirstBootManager) -> LauncherPhase:
    return LauncherPhase.OPERATIONS_READY if first_boot_manager.should_enter_operations() else LauncherPhase.FIRST_BOOT_REQUIRED


def _render_first_boot_home(
    *,
    services: LauncherServices,
    workspace_root: Path,
    show_setup_wizard: bool,
) -> None:
    # BIRTH ENGINE 2026-05-17
    st.markdown("## First Boot Command Center")
    st.caption(
        "Je ziet nu enkel de Birth Phase ervaring. Rond training volledig af, "
        "daarna schakelt de launcher automatisch naar het volledige operations dashboard."
    )
    if show_setup_wizard:
        setup_tab = st.tabs(["Setup"])[0]
        with setup_tab:
            render_setup_wizard(
                workspace_root=workspace_root,
                setup_service=services.setup_service,
                config_manager=services.config_manager,
                first_boot_manager=services.first_boot_manager,
                hardware_service=services.hardware_service,
                model_service=services.model_service,
            )
        return

    auto_start = st.session_state.pop("lumina_auto_start_birth_after_setup", False)
    if not show_setup_wizard and services.first_boot_manager.artifacts_missing():
        auto_start = auto_start or not st.session_state.get("lumina_birth_auto_start_attempted")
    if auto_start and not services.process_manager.is_process_alive():
        st.session_state["lumina_birth_auto_start_attempted"] = True
        ok, msg = services.process_manager.start_bot(mode="auto")
        if ok:
            st.session_state["first_boot_settings_locked"] = True
            st.success(f"Birth Phase training gestart: {msg}")
        else:
            st.session_state["first_boot_last_start_failed"] = True
            st.session_state["first_boot_last_start_error"] = msg
            st.error(f"Birth Phase kon niet starten: {msg}")
    elif auto_start and services.process_manager.is_process_alive():
        st.info("Runtime draait al; Birth Phase training wordt hervat.")

    tabs = st.tabs(["Birth Phase", "Overview"])
    with tabs[0]:
        render_first_boot_tab(
            services.first_boot_manager,
            process_manager=services.process_manager,
            backend_client=services.backend_client,
        )
    with tabs[1]:
        render_training_dashboard_tab(
            workspace_root,
            first_boot_manager=services.first_boot_manager,
            hardware_service=services.hardware_service,
            process_manager=services.process_manager,
            backend_base_url=services.backend_client.base_url,
        )


def _render_operations_shell(
    *,
    services: LauncherServices,
    workspace_root: Path,
    state: dict,
    current_dream: dict,
    snapshot: object,
    process_alive: bool,
    current_mode: str,
) -> None:
    ctx = TabRenderContext(
        launcher_root=workspace_root,
        services=services,
        state=state,
        current_dream=current_dream,
        snapshot=snapshot,
        process_alive=process_alive,
        current_mode=current_mode,
        first_boot_completed=True,
    )
    visible_specs = [spec for spec in launcher_tab_specs() if spec.visible(ctx)]
    groups = list(dict.fromkeys(spec.group for spec in visible_specs))
    if not groups:
        st.error("No workspace groups available in current launcher mode.")
        return

    default_group = str(st.session_state.get("lumina_nav_group", groups[0]))
    if default_group not in groups:
        default_group = groups[0]
    selected_group = st.radio(
        "Workspace section",
        options=groups,
        index=groups.index(default_group),
        horizontal=True,
        key="lumina_nav_group",
    )
    group_specs = [spec for spec in visible_specs if spec.group == selected_group]
    labels = [spec.label for spec in group_specs]
    if not labels:
        st.warning("Selected workspace section has no tabs.")
        return
    tab_state_key = f"lumina_nav_tab_{selected_group.lower()}"
    default_label = str(st.session_state.get(tab_state_key, labels[0]))
    if default_label not in labels:
        default_label = labels[0]
    selected_label = st.selectbox(
        "Workspace tab",
        options=labels,
        index=labels.index(default_label),
        key=tab_state_key,
    )
    selected_spec = next(spec for spec in group_specs if spec.label == selected_label)
    selected_spec.render(ctx)


def render_streamlit_app() -> None:
    st.set_page_config(page_title="LUMINA OS Launcher", layout="wide")
    st.markdown(_LAUNCHER_PREMIUM_CSS, unsafe_allow_html=True)
    run_id = ensure_run_id(st.session_state)
    log_event("launcher.rerun_started", run_id=run_id, seq=int(st.session_state.get("lumina_run_seq", 1)))
    services = _get_services()

    backend_up = _ensure_backend_running(st.session_state)
    if not backend_up:
        st.info(
            "Backend (FastAPI) lijkt niet te draaien op poort 8000. "
            "Start met `powershell -ExecutionPolicy Bypass -File .\\lumina_os\\run_backend.ps1`."
        )

    setup_complete = services.setup_service.is_setup_complete()
    phase = _resolve_launcher_phase(first_boot_manager=services.first_boot_manager)

    state = _load_runtime_state()
    current_dream = state.get("current_dream", {}) if isinstance(state.get("current_dream"), dict) else {}
    snapshot = services.hardware_service.get_cached_snapshot() or services.hardware_service.get_snapshot()
    process_alive = services.process_manager.is_process_alive()
    current_mode = _current_mode(services.config_manager)
    first_boot = services.first_boot_manager.read_settings()
    first_boot_progress = services.first_boot_manager.read_progress()
    first_boot_completed_trades = resolve_first_boot_completed_trades(first_boot_progress)
    first_boot_target_trades = int(
        resolve_first_boot_target_from_progress(first_boot_progress)
        or first_boot.get("training_trades", FIRST_BOOT_DEFAULT_TRADES)
        or 0
    )
    first_boot_stage = resolve_first_boot_stage(first_boot_progress)
    runtime_session = resolve_runtime_session_state(
        first_boot_stage=first_boot_stage,
        process_alive=process_alive,
        current_mode=current_mode,
        first_boot_timestamp=str(first_boot_progress.get("timestamp") or ""),
    )
    show_training_target = (
        services.first_boot_manager.is_user_configured()
        and runtime_session.training_target_applicable
        and first_boot_target_trades > 0
    )

    st.title("LUMINA OS Launcher")
    render_presence_strip(
        {
            "pulse_live": process_alive,
            "last_activity_verbose": f"Mode={current_mode.upper()} • Backend={'UP' if backend_up else 'DOWN'}",
            "tpm_label": (
                f"{first_boot_completed_trades:,}/{first_boot_target_trades:,} first-boot trades"
                if show_training_target
                else "Not started"
            ),
        }
    )
    st.caption(
        "Progress source: state/lumina_birth_progress.json (fallback: state/first_boot_progress.json) "
        "• target source: config.yaml:first_boot.training_trades"
    )

    if phase == LauncherPhase.FIRST_BOOT_REQUIRED:
        st.warning("Birth Phase training is nog niet voltooid.")
    else:
        st.success("Birth Phase training is voltooid. Volledige launcher is geactiveerd.")

    if phase == LauncherPhase.OPERATIONS_READY:
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
                value=int(first_boot.get("training_trades", FIRST_BOOT_DEFAULT_TRADES)),
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
            pause_policy = resolve_pause_policy(
                context="operations",
                runtime_mode=current_mode,
                process_alive=process_alive,
            )
            if pause_policy.require_risk_warning:
                st.warning(
                    "Live pause stopt trading direct en probeert open orders onmiddellijk te sluiten/annuleren. "
                    "Dit kan verlies veroorzaken bij snelle marktbewegingen."
                )
                ops_pause_ack = st.checkbox(
                    "Ik begrijp het risico en wil live trading direct pauzeren.",
                    key="ops_pause_ack",
                )
                if st.button(
                    "⏸️ Pauzeer live trading (veiligheidsstop)",
                    use_container_width=True,
                    disabled=not ops_pause_ack,
                ):
                    emergency_result = services.backend_client.emergency_flatten_and_cancel()
                    ok, msg = services.process_manager.pause_trading_safely(
                        emergency_action=services.backend_client.emergency_flatten_and_cancel,
                        require_emergency_success=True,
                    )
                    if emergency_result.get("ok"):
                        st.success("Orders gesloten/geannuleerd via backend safety endpoint.")
                    st.success(msg) if ok else st.error(msg)
            if st.button("Stop alles & afsluiten", use_container_width=True):
                emergency_result = services.backend_client.emergency_flatten_and_cancel()
                ok, msg = services.process_manager.stop_all_activities()
                if emergency_result.get("ok"):
                    st.success("Orders gesloten/geannuleerd via backend safety endpoint.")
                else:
                    detail = emergency_result.get("detail") or emergency_result.get("error") or "onbekende backendfout"
                    st.error(f"Order-safety endpoint faalde: {detail}")
                st.success(msg) if ok else st.error(msg)
                st.info("Je kan het launcher-venster nu veilig sluiten.")
        _render_operations_shell(
            services=services,
            workspace_root=_LAUNCHER_ROOT,
            state=state,
            current_dream=current_dream,
            snapshot=snapshot,
            process_alive=process_alive,
            current_mode=current_mode,
        )
    else:
        _render_first_boot_home(
            services=services,
            workspace_root=_LAUNCHER_ROOT,
            show_setup_wizard=not setup_complete,
        )

    st.divider()
    st.caption("LUMINA OS Launcher — parity restored, modular, observable, and performance-focused.")
