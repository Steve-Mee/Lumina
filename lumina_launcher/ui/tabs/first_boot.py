"""
UI Tabs - First Boot Wizard
Improved and restored version for Fase 2.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import streamlit as st

from lumina_core.first_boot_progress import (
    resolve_first_boot_completed_trades,
    resolve_first_boot_stage,
    resolve_ppo_training_progress,
)
from lumina_launcher.core.first_boot import (
    FirstBootManager,
    build_first_boot_settings_signature,
    build_first_boot_settings_signature_from_settings,
    first_boot_settings_match_saved,
)
from lumina_launcher.core.pause_policy import resolve_pause_policy
from lumina_launcher.core.process_manager import ProcessManager
from lumina_launcher.services.backend_client import BackendClient
from lumina_launcher.services.birth_service import BirthService
from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_TRADES,
    FIRST_BOOT_LAUNCHER_TRADE_STEP,
    FIRST_BOOT_TRAINING_TRADES_MAX,
    FIRST_BOOT_TRAINING_TRADES_MIN,
    estimate_first_boot_duration,
    estimate_first_boot_real_days,
    exceeds_max_real_days_window,
    format_duration_range,
)
from lumina_launcher.ui.auto_refresh import run_with_autorefresh
from lumina_launcher.ui.help_texts import help_for


_RUNNING_STAGES = {
    "detected",
    "loading_data",
    "training_running",
    "pipeline_boot",
    "historical_loaded",
    "synthetic_top_up",
    "parallel_simulation",
    "ppo_training",
    "deferred_calendar",
}
_LOCKED_STAGES = _RUNNING_STAGES | {"paused"}


def _load_first_boot_reports(root: Path) -> list[dict]:
    # BIRTH ENGINE 2026-05-17
    reports_dir = root / "journal" / "simulator"
    if not reports_dir.exists():
        return []
    reports: list[dict] = []
    paths = list(reports_dir.glob("lumina_birth_training_*.json")) + list(reports_dir.glob("first_boot_training_*.json"))
    for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        payload["_path"] = str(path)
        reports.append(payload)
    return reports


def _report_summary(reports: list[dict]) -> tuple[dict, dict]:
    latest = reports[0] if reports else {}
    if not reports:
        return latest, {}
    total_trades = sum(int(r.get("trades", 0) or 0) for r in reports)
    total_elapsed = sum(float(r.get("elapsed_sec", 0.0) or 0.0) for r in reports)
    synthetic_values = [float(r.get("synthetic_pct", 0.0) or 0.0) for r in reports]
    return latest, {
        "runs": len(reports),
        "total_trades": total_trades,
        "total_elapsed_sec": total_elapsed,
        "avg_synthetic_pct": float(mean(synthetic_values)) if synthetic_values else 0.0,
    }


def _read_runtime_stderr_tail(root: Path, *, max_lines: int = 6) -> str:
    stderr_path = root / "logs" / "launcher_runtime_stderr.log"
    if not stderr_path.exists():
        return ""
    try:
        lines = stderr_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        return ""
    return "\n".join(non_empty[-max_lines:])


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


def _settings_signature(
    *,
    training_trades: int,
    prefer_real_data_only: bool,
    max_real_days: int,
    allow_fallback: bool,
    require_real_sim: bool,
) -> tuple[int, bool, int, bool, bool]:
    return build_first_boot_settings_signature(
        training_trades=training_trades,
        prefer_real_data_only=prefer_real_data_only,
        max_real_days=max_real_days,
        allow_minimal_synthetic_fallback=allow_fallback,
        require_real_simulator_data=require_real_sim,
    )


_FIRST_BOOT_FORM_VERSION_KEY = "first_boot_form_version"


def _first_boot_form_version() -> int:
    return int(st.session_state.get(_FIRST_BOOT_FORM_VERSION_KEY, 0))


def _bump_first_boot_form_version() -> int:
    version = _first_boot_form_version() + 1
    st.session_state[_FIRST_BOOT_FORM_VERSION_KEY] = version
    return version


def _versioned_widget_key(base_key: str) -> str:
    return f"{base_key}_v{_first_boot_form_version()}"


def _apply_first_boot_settings_to_form(settings: dict) -> None:
    """Sync canonical value keys from disk; bump widget generation so Streamlit creates fresh widgets."""
    _bump_first_boot_form_version()
    st.session_state["first_boot_training_trades_value"] = int(
        settings.get("training_trades", FIRST_BOOT_DEFAULT_TRADES)
    )
    st.session_state["first_boot_max_real_days_value"] = int(settings.get("max_real_days", 365))
    st.session_state["first_boot_prefer_real_data_only_value"] = bool(settings.get("prefer_real_data_only", True))
    st.session_state["first_boot_allow_fallback_value"] = bool(settings.get("allow_minimal_synthetic_fallback", False))
    st.session_state["first_boot_require_real_sim_value"] = bool(settings.get("require_real_simulator_data", True))


def _init_checkbox_from_settings(*, base_key: str, settings: dict, settings_field: str, default: bool) -> None:
    value_key = f"{base_key}_value"
    widget_key = _versioned_widget_key(base_key)
    if value_key not in st.session_state:
        st.session_state[value_key] = bool(settings.get(settings_field, default))
    if widget_key not in st.session_state:
        st.session_state[widget_key] = bool(st.session_state[value_key])


def _slider_with_input(
    *,
    label: str,
    key: str,
    min_value: int,
    max_value: int,
    default_value: int,
    step: int,
    help_text: str | None = None,
    disabled: bool = False,
) -> int:
    state_key = f"{key}_value"
    slider_key = _versioned_widget_key(f"{key}_slider")
    input_key = _versioned_widget_key(f"{key}_input")
    if state_key not in st.session_state:
        st.session_state[state_key] = int(default_value)
    current = int(st.session_state[state_key])
    current = max(min(current, max_value), min_value)
    st.session_state[state_key] = current
    if slider_key not in st.session_state:
        st.session_state[slider_key] = current
    if input_key not in st.session_state:
        st.session_state[input_key] = current

    def _on_slider_change() -> None:
        selected = int(st.session_state.get(slider_key, current))
        selected = max(min(selected, max_value), min_value)
        st.session_state[state_key] = selected
        st.session_state[input_key] = selected

    def _on_input_change() -> None:
        selected = int(st.session_state.get(input_key, current))
        selected = max(min(selected, max_value), min_value)
        st.session_state[state_key] = selected
        st.session_state[slider_key] = selected

    left, right = st.columns([3, 1])
    with left:
        # Widget value comes from session_state[key]; do not also pass value= (Streamlit conflict).
        st.slider(
            f"{label} (slider)",
            min_value=min_value,
            max_value=max_value,
            step=step,
            key=slider_key,
            on_change=_on_slider_change,
            help=help_text,
            disabled=disabled,
        )
    with right:
        st.number_input(
            f"{label} (input)",
            min_value=min_value,
            max_value=max_value,
            step=step,
            key=input_key,
            on_change=_on_input_change,
            disabled=disabled,
        )
    selected_value = int(st.session_state.get(state_key, current))
    selected_value = max(min(selected_value, max_value), min_value)
    st.session_state[state_key] = selected_value
    return selected_value


def _start_birth_training(
    *,
    birth_service: BirthService | None,
    backend_client: BackendClient | None,
    workspace_root: Path,
    target_trades: int,
    force: bool = False,
) -> tuple[bool, str]:
    """Start Birth Phase via in-process BirthService, with HTTP fallback to FastAPI."""
    if birth_service is not None:
        birth_service.configure_workspace(workspace_root)
        result = birth_service.start_birth(target_trades=int(target_trades), force=bool(force))
        status = str(result.get("status", "")).strip().lower()
        message = str(result.get("message", "") or "").strip()
        if status in {"started", "already_running"}:
            return True, message or "Birth Phase gestart."
        return False, message or f"Birth Phase kon niet starten ({status or 'unknown'})."

    if backend_client is not None:
        payload = backend_client.start_birth_sync(target_trades=int(target_trades), force=bool(force))
        if payload.get("error"):
            detail = str(payload.get("detail", "") or "").strip()
            return False, f"Backend: {payload.get('error')}" + (f" — {detail}" if detail else "")
        status = str(payload.get("status", "")).strip().lower()
        message = str(payload.get("message", "") or "").strip()
        if status in {"started", "already_running"}:
            return True, message or "Birth Phase gestart via backend."
        return False, message or f"Backend weigerde start ({status or 'unknown'})."

    return False, "Geen BirthService of backend-client beschikbaar."


def _birth_training_active(
    *,
    birth_service: BirthService | None,
    process_manager: ProcessManager | None,
) -> bool:
    if birth_service is not None and birth_service.is_running():
        return True
    return bool(process_manager.is_process_alive()) if process_manager is not None else False


def render_first_boot_tab(
    first_boot_manager: FirstBootManager,
    *,
    process_manager: ProcessManager | None = None,
    backend_client: BackendClient | None = None,
    birth_service: BirthService | None = None,
) -> None:
    # BIRTH ENGINE 2026-05-17
    st.subheader("Birth Phase Training")
    auto_refresh = st.checkbox("Auto-refresh (10s)", value=False, key="lumina_first_boot_tab_autorefresh")

    def _first_boot_body() -> None:
        _render_first_boot_body(
            first_boot_manager,
            process_manager=process_manager,
            backend_client=backend_client,
            birth_service=birth_service,
        )

    run_with_autorefresh(_first_boot_body, enabled=auto_refresh, interval_seconds=10)


def _render_first_boot_body(
    first_boot_manager: FirstBootManager,
    *,
    process_manager: ProcessManager | None = None,
    backend_client: BackendClient | None = None,
    birth_service: BirthService | None = None,
) -> None:
    settings = first_boot_manager.read_settings()
    progress = first_boot_manager.read_progress()
    stage = resolve_first_boot_stage(progress)
    show_summary = first_boot_manager.should_show_completion_summary(progress)
    ppo_phase = first_boot_manager.is_ppo_training_phase(progress)
    process_alive = bool(process_manager.is_process_alive()) if process_manager is not None else False
    birth_running = bool(birth_service.is_running()) if birth_service is not None else False
    training_active = _birth_training_active(birth_service=birth_service, process_manager=process_manager)
    if stage in _LOCKED_STAGES or birth_running:
        st.session_state["first_boot_settings_locked"] = True
    elif not progress and not training_active:
        # Streamlit server session survives browser hard-refresh; drop stale pre-start lock.
        st.session_state["first_boot_settings_locked"] = False

    settings_locked = stage in _LOCKED_STAGES or bool(st.session_state.get("first_boot_settings_locked", False))

    # Form sync must run before widgets are created (Streamlit forbids mutating widget keys after bind).
    if st.session_state.pop("first_boot_rehydrate", False):
        _apply_first_boot_settings_to_form(settings)
    elif first_boot_manager.is_user_configured() and not settings_locked:
        disk_signature = build_first_boot_settings_signature_from_settings(settings)
        saved_signature = st.session_state.get("first_boot_saved_signature")
        if saved_signature is None or tuple(saved_signature) != disk_signature:
            _apply_first_boot_settings_to_form(settings)
            st.session_state["first_boot_saved_signature"] = disk_signature

    if show_summary:
        if not first_boot_manager.is_completed():
            st.warning(
                "Training is afgerond in progress, maar policy/flag worden nog weggeschreven. "
                "Wacht even of controleer of de runtime nog draait."
            )
        st.success("Birth Phase training is voltooid.")
        reports = _load_first_boot_reports(first_boot_manager.workspace_root)
        latest, aggregate = _report_summary(reports)
        c1, c2, c3 = st.columns(3)
        c1.metric("Laatste run trades", f"{int(latest.get('trades', 0) or 0):,}")
        c2.metric("Laatste run duur", f"{float(latest.get('elapsed_sec', 0.0) or 0.0):.1f}s")
        c3.metric("Laatste status", str(latest.get("status", "unknown")))
        st.markdown("#### Totaal over alle Birth Phase runs")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Aantal runs", int(aggregate.get("runs", 0) or 0))
        g2.metric("Totaal trades", f"{int(aggregate.get('total_trades', 0) or 0):,}")
        g3.metric("Totale tijd", f"{float(aggregate.get('total_elapsed_sec', 0.0) or 0.0):.1f}s")
        g4.metric("Gem. synthetic", f"{float(aggregate.get('avg_synthetic_pct', 0.0) or 0.0):.1f}%")
        action_col_1, action_col_2 = st.columns(2)
        with action_col_1:
            if st.button("Extra trainen", use_container_width=True):
                if process_manager is not None:
                    process_manager.stop_bot()
                first_boot_manager.clear_completion_artifacts_for_extra_training()
                st.session_state["first_boot_saved_signature"] = None
                st.session_state["first_boot_settings_locked"] = False
                st.session_state["first_boot_summary_mode"] = False
                st.session_state[_FIRST_BOOT_FORM_VERSION_KEY] = 0
                st.success("Completion artifacts gewist. Je kan opnieuw instellingen kiezen en trainen.")
                st.rerun()
        with action_col_2:
            if st.button("Ga naar bot", type="primary", use_container_width=True):
                first_boot_manager.mark_go_to_bot()
                st.success("Launcher schakelt naar bot-operations.")
                st.rerun()
        st.caption(f"Policy: `{first_boot_manager.policy_path}`")
        return

    # Settings
    st.markdown("#### Training Instellingen")
    col1, col2 = st.columns(2)

    with col1:
        training_trades = _slider_with_input(
            label="Aantal training trades",
            key="first_boot_training_trades",
            min_value=FIRST_BOOT_TRAINING_TRADES_MIN,
            max_value=FIRST_BOOT_TRAINING_TRADES_MAX,
            default_value=int(settings.get("training_trades", FIRST_BOOT_DEFAULT_TRADES)),
            step=FIRST_BOOT_LAUNCHER_TRADE_STEP,
            help_text=help_for("training_trades"),
            disabled=settings_locked,
        )
    with col2:
        _init_checkbox_from_settings(
            base_key="first_boot_prefer_real_data_only",
            settings=settings,
            settings_field="prefer_real_data_only",
            default=True,
        )
        prefer_real_data_only = st.checkbox(
            "Prefer real data only",
            key=_versioned_widget_key("first_boot_prefer_real_data_only"),
            help=help_for("prefer_real_data_only"),
            disabled=settings_locked,
        )

    col3, col4 = st.columns(2)
    with col3:
        max_real_days = _slider_with_input(
            label="Max real days",
            key="first_boot_max_real_days",
            min_value=30,
            max_value=3650,
            default_value=int(settings.get("max_real_days", 365)),
            step=5,
            help_text=help_for("max_real_days"),
            disabled=settings_locked,
        )
    with col4:
        _init_checkbox_from_settings(
            base_key="first_boot_allow_fallback",
            settings=settings,
            settings_field="allow_minimal_synthetic_fallback",
            default=False,
        )
        allow_fallback = st.checkbox(
            "Allow minimal synthetic fallback",
            key=_versioned_widget_key("first_boot_allow_fallback"),
            help=help_for("allow_minimal_synthetic_fallback"),
            disabled=settings_locked,
        )

    _init_checkbox_from_settings(
        base_key="first_boot_require_real_sim",
        settings=settings,
        settings_field="require_real_simulator_data",
        default=True,
    )
    require_real_sim = st.checkbox(
        "Require real simulator data (fail-closed)",
        key=_versioned_widget_key("first_boot_require_real_sim"),
        help=help_for("require_real_simulator_data"),
        disabled=settings_locked,
    )
    current_signature = _settings_signature(
        training_trades=int(training_trades),
        prefer_real_data_only=bool(prefer_real_data_only),
        max_real_days=int(max_real_days),
        allow_fallback=bool(allow_fallback),
        require_real_sim=bool(require_real_sim),
    )
    saved_signature = st.session_state.get("first_boot_saved_signature")
    settings_match_saved = first_boot_settings_match_saved(
        current_signature=current_signature,
        settings_on_disk=settings,
        session_saved_signature=saved_signature,
    )
    dirty_settings = not first_boot_manager.is_user_configured() or not settings_match_saved

    estimate_days = estimate_first_boot_real_days(int(training_trades))
    st.caption(f"Geschatte benodigde echte historische dagen: {estimate_days}")
    duration_estimate = estimate_first_boot_duration(
        training_trades=int(training_trades),
        max_real_days=int(max_real_days),
        prefer_real_data_only=bool(prefer_real_data_only),
        allow_minimal_synthetic_fallback=bool(allow_fallback),
        workspace_root=first_boot_manager.workspace_root,
    )
    st.caption(
        "Geschatte trainingsduur: "
        f"{format_duration_range(duration_estimate)} "
        f"({duration_estimate.confidence} confidence, bron: {duration_estimate.method})."
    )
    for note in duration_estimate.notes[:2]:
        st.caption(f"- {note}")
    exceeds_window = exceeds_max_real_days_window(estimate_days, int(max_real_days))
    if exceeds_window:
        warn_col, button_col = st.columns([3, 1])
        with warn_col:
            st.warning("Trade volume overschrijdt vermoedelijk max_real_days; verlaag trades of verhoog venster.")
        with button_col:
            if st.button("Pas max days aan", key="first_boot_adjust_days", use_container_width=True, disabled=settings_locked):
                st.session_state["first_boot_max_real_days_value"] = int(estimate_days)
                _bump_first_boot_form_version()
                st.rerun()

    root = first_boot_manager.workspace_root
    if process_manager is not None:
        process_manager._reconcile_stale_process_state()
    runtime_state = process_manager._load_process_state() if process_manager is not None else {}
    runtime_pid = int(runtime_state.get("pid", 0) or 0)
    runtime_marked_started = runtime_pid > 0
    recent_start_failed = bool(st.session_state.get("first_boot_last_start_failed", False))
    policy_exists = first_boot_manager.policy_path.exists()
    ppo_interrupted = first_boot_manager.is_ppo_interrupted(
        progress=progress,
        process_alive=process_alive,
        policy_exists=policy_exists,
    )
    runtime_crashed = runtime_marked_started and not process_alive and (not progress or ppo_interrupted)
    runtime_stderr_tail = _read_runtime_stderr_tail(root) if (runtime_crashed or recent_start_failed or ppo_interrupted) else ""

    save_col, start_col, stop_col = st.columns(3)
    with save_col:
        if st.button("💾 Save Settings", use_container_width=True, disabled=settings_locked):
            first_boot_manager.save_full_settings(
                training_trades=int(training_trades),
                prefer_real_data_only=bool(prefer_real_data_only),
                max_real_days=int(max_real_days),
                allow_minimal_synthetic_fallback=bool(allow_fallback),
                require_real_simulator_data=bool(require_real_sim),
                mark_user_configured=True,
            )
            persisted = first_boot_manager.read_settings()
            persisted_signature = build_first_boot_settings_signature_from_settings(persisted)
            st.session_state["first_boot_saved_signature"] = persisted_signature
            st.session_state["first_boot_rehydrate"] = True
            st.success("Instellingen opgeslagen.")
            st.rerun()
    with start_col:
        start_disabled = dirty_settings or settings_locked or (birth_service is None and backend_client is None)
        if st.button(
            "▶️ Start Birth Phase",
            type="primary",
            use_container_width=True,
            disabled=start_disabled,
        ):
            ok, msg = _start_birth_training(
                birth_service=birth_service,
                backend_client=backend_client,
                workspace_root=first_boot_manager.workspace_root,
                target_trades=int(training_trades),
            )
            if ok:
                st.session_state["first_boot_last_start_failed"] = False
                st.session_state["first_boot_settings_locked"] = True
                st.success(msg)
            else:
                st.session_state["first_boot_last_start_failed"] = True
                st.session_state["first_boot_last_start_error"] = msg
                st.session_state["first_boot_settings_locked"] = False
                st.error(msg)
    with stop_col:
        if process_manager is not None and st.button("⏹️ Stop Bot", use_container_width=True):
            ok, msg = process_manager.stop_bot()
            st.info(msg) if ok else st.error(msg)
    if settings_locked:
        st.warning("Instellingen zijn vergrendeld tijdens/na gestart Birth Phase training.")
    elif dirty_settings:
        st.info("Start Birth Phase is pas actief nadat je op Save Settings hebt geklikt.")

    if birth_running:
        birth_status = birth_service.get_status() if birth_service is not None else {}
        elapsed = birth_status.get("elapsed_seconds")
        elapsed_txt = f" ({elapsed}s)" if elapsed is not None else ""
        st.success(f"Birth Phase status: actief{elapsed_txt}.")
    elif process_alive:
        st.success("Legacy runtime-bot actief (lumina_runtime.py).")
    elif ppo_interrupted:
        st.error(
            "Runtime status: PPO-training onderbroken — runtime is niet actief en policy ontbreekt nog. "
            "Klik op **Start Bot (training)** om PPO te hervatten."
        )
    elif runtime_crashed:
        st.error(
            f"Runtime status: gestopt na start (laatste pid={runtime_pid}). "
            "Controleer `logs/launcher_runtime_stderr.log`."
        )
    elif recent_start_failed:
        last_error = str(st.session_state.get("first_boot_last_start_error", "") or "").strip()
        st.error(
            "Runtime status: laatste startpoging mislukt."
            + (f" {last_error}" if last_error else " Controleer `logs/launcher_runtime_stderr.log`.")
        )
    else:
        st.info("Runtime status: niet actief.")

    log_paths = (
        root / "logs" / "lumina_full_log.csv",
        root / "logs" / "structured_errors.jsonl",
        root / "logs" / "launcher_runtime_stderr.log",
        root / "state" / "lumina_birth_progress.json",
        root / "state" / "first_boot_progress.json",
    )
    with st.expander("Waar vind ik logs en training-status?", expanded=not progress):
        st.markdown(
            "Birth Phase training draait via **BirthService** (achtergrondthread + LuminaBirthEngine), niet in Streamlit zelf. "
            "Sla instellingen op en klik **Start Birth Phase**."
        )
        for path in log_paths:
            exists = "✓" if path.exists() else "—"
            st.caption(f"{exists} `{path}`")
        if runtime_stderr_tail:
            st.code(runtime_stderr_tail, language="text")
        if runtime_crashed or recent_start_failed or ppo_interrupted:
            st.warning("Runtime startte maar stopte direct; check stderr-log en interpreter configuratie.")
        elif not progress:
            st.warning(
                "Zolang `lumina_birth_progress.json` en `first_boot_progress.json` ontbreken, "
                "is de runtime nog niet gestart of nog niet begonnen met trainen."
            )

    st.divider()

    # Progress
    st.markdown("#### Training Progress")

    if progress:
        stage = progress.get("stage", "unknown")
        pct = first_boot_manager.get_stage_progress(stage)
        st.progress(pct, text=f"Stage: {stage}")
        completed_trades = resolve_first_boot_completed_trades(progress)
        target = int(settings.get("training_trades", FIRST_BOOT_DEFAULT_TRADES))
        has_saved_settings = first_boot_manager.is_user_configured()
        st.metric("Trades Completed", f"{completed_trades:,}")
        if has_saved_settings:
            st.caption(f"Target trades: {target:,}")
        else:
            st.caption("Target trades: nog niet geconfigureerd (klik eerst op Save Settings).")
        if ppo_phase and not show_summary:
            ppo_steps, ppo_total, ppo_pct = resolve_ppo_training_progress(progress)
            ppo_ratio = float(ppo_steps) / float(max(1, ppo_total))
            st.info(
                "SIM-training is voltooid (alle geconfigureerde trades zijn gesimuleerd). "
                "PPO policy-training loopt nog — het samenvattingsscherm met **Extra trainen** / **Ga naar bot** "
                "verschijnt automatisch zodra dit klaar is."
            )
            st.progress(
                max(0.0, min(1.0, ppo_ratio)),
                text=f"PPO progress: {ppo_steps:,}/{ppo_total:,} timesteps ({(ppo_pct or 0.0):.1f}%)",
            )
            p1, p2, p3 = st.columns(3)
            p1.metric("PPO steps", f"{ppo_steps:,}")
            p2.metric("PPO total", f"{ppo_total:,}")
            p3.metric("PPO progress", f"{(ppo_pct or 0.0):.1f}%")
            if ppo_interrupted:
                st.error("PPO-training is onderbroken. Start de bot opnieuw om verder te gaan vanaf het checkpoint.")
            age_sec = _progress_age_seconds(progress)
            if process_alive and age_sec is not None and age_sec > 120:
                st.warning("PPO lijkt vastgelopen: geen nieuwe progress-update in > 2 minuten.")
            elif process_alive:
                st.caption("PPO actief — live progress wordt automatisch bijgewerkt.")
        if stage == "training_running":
            eta_minutes = progress.get("eta_minutes")
            if isinstance(eta_minutes, (int, float)) and float(eta_minutes) > 0:
                st.caption(f"Resterende tijd (live): ~{float(eta_minutes):.0f} min")
            velocity = progress.get("velocity_trades_per_sec")
            if isinstance(velocity, (int, float)) and float(velocity) > 0:
                st.caption(f"Huidige SIM snelheid: {float(velocity):.1f} trades/s")
    else:
        if runtime_crashed or recent_start_failed:
            st.error("Runtime crash gedetecteerd: training is niet actief. Bekijk de stderr-log hierboven.")
        else:
            st.info("Nog geen progress gevonden. Start de bot om first-boot te activeren.")

    # Actions
    st.markdown("#### Acties")
    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("⏸️ Pauzeer training", width="stretch"):
            first_boot_manager.request_pause()
            st.success("Pause requested — training stopt op het volgende checkpoint.")

    with col_b:
        if st.button("▶️ Resume na pauze", width="stretch"):
            first_boot_manager.clear_pause_request()
            paused_marker = first_boot_manager.workspace_root / "state" / "paused_by_user.json"
            paused_marker.unlink(missing_ok=True)
            st.success("Pause-vlag gewist. Start de bot opnieuw als deze gestopt was.")

    pause_policy = resolve_pause_policy(
        context="birth_phase_training",  # BIRTH ENGINE 2026-05-17
        runtime_mode="sim",
        process_alive=bool(process_alive),
    )
    st.info(f"Tijdens Birth Phase training is pauze een {pause_policy.label} (niet-destructief).")

    st.caption("First Boot tab — Fase 2 (Feature Restoration)")
