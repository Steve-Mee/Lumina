"""
UI Tabs - First Boot Wizard
Improved and restored version for Fase 2.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import streamlit as st

from lumina_core.first_boot_progress import (
    is_sim_trades_complete,
    resolve_first_boot_completed_trades,
    resolve_first_boot_stage,
    resolve_ppo_batch_progress,
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

_FIRST_BOOT_START_REQUESTED_KEY = "first_boot_start_requested"
_FIRST_BOOT_PENDING_SAVE_KEY = "first_boot_pending_save"
_FIRST_BOOT_PENDING_START_KEY = "first_boot_pending_start"
_SAVE_SETTINGS_KEY = "first_boot_save_settings"
_START_BIRTH_KEY = "first_boot_start_birth_phase"
_STOP_TRAINING_KEY = "first_boot_stop_training"
_FIRST_BOOT_PENDING_STOP_KEY = "first_boot_pending_stop"
_PROGRESS_ACTIVE_MAX_AGE_SEC = 30.0


def _clear_start_request_flags() -> None:
    st.session_state[_FIRST_BOOT_START_REQUESTED_KEY] = False
    st.session_state[_FIRST_BOOT_PENDING_START_KEY] = False


def _arm_explicit_birth_start() -> None:
    st.session_state[_FIRST_BOOT_START_REQUESTED_KEY] = True


def _explicit_start_requested() -> bool:
    return bool(st.session_state.get(_FIRST_BOOT_START_REQUESTED_KEY, False))


def _on_save_settings_click() -> None:
    _clear_start_request_flags()
    st.session_state[_FIRST_BOOT_PENDING_SAVE_KEY] = True


def _on_start_birth_click() -> None:
    _arm_explicit_birth_start()
    st.session_state[_FIRST_BOOT_PENDING_START_KEY] = True


def _on_stop_training_click() -> None:
    st.session_state[_FIRST_BOOT_PENDING_STOP_KEY] = True


def _render_training_mode_warning(progress: dict[str, Any]) -> None:
    mode = str(progress.get("training_mode", "") or "").strip().lower()
    stage = str(progress.get("stage", "") or "").strip().lower()
    if mode != "practice" and stage != "practice_completed":
        return
    real_days = int(progress.get("actual_real_days_loaded", 0) or 0)
    real_pct = progress.get("real_data_pct")
    pct_suffix = ""
    if isinstance(real_pct, (int, float)):
        pct_suffix = f", ~{float(real_pct):.1f}% real ticks in stream"
    if real_days > 0:
        st.warning(
            f"Practice-run (niet certified voor live). Wel {real_days} echte historische dagen geladen"
            f"{pct_suffix}; synthetic top-up kan aanwezig zijn. "
            "Gebruik **Start Birth Phase** voor certified training op real historical data."
        )
    else:
        st.warning(
            "Deze run was een practice-run zonder echte historische data (synthetic). "
            "Dit telt niet mee om live te gaan; certified training op real historical data blijft verplicht."
        )


def _render_birth_phase_status_banner(
    *,
    progress: dict[str, Any],
    completed_trades: int,
    target_trades: int,
    ppo_phase: bool,
) -> None:
    phase = str(progress.get("phase", "") or "").strip().lower()
    sim_complete = is_sim_trades_complete(progress)
    batch_count = int(progress.get("ppo_batch_count", 0) or 0)

    if sim_complete and ppo_phase:
        st.info(
            "PPO policy-training actief (SIM-training afgerond). "
            "Het samenvattingsscherm met **Extra trainen** / **Ga naar bot** verschijnt na voltooiing."
        )
    elif ppo_phase and not sim_complete:
        batch_hint = f" (batch {batch_count})" if batch_count > 0 else ""
        st.info(
            f"SIM-training actief: {completed_trades:,}/{target_trades:,} trades — "
            f"tussentijdse PPO-update{batch_hint}."
        )
    elif not sim_complete and phase in {"birth_phase", "training_running", "loading_data"}:
        st.info(f"SIM-training actief: {completed_trades:,}/{target_trades:,} trades.")


def _render_ppo_progress_bars(progress: dict[str, Any]) -> None:
    ppo_steps, ppo_total, ppo_pct = resolve_ppo_training_progress(progress)
    batch_steps, batch_total, batch_pct = resolve_ppo_batch_progress(progress)
    if ppo_total <= 0 and batch_total <= 0:
        return
    total_ratio = float(ppo_steps) / float(max(1, ppo_total))
    st.progress(
        max(0.0, min(1.0, total_ratio)),
        text=(
            f"Totaal PPO: {ppo_steps:,}/{ppo_total:,} timesteps"
            + (f" ({(ppo_pct or 0.0):.1f}%)" if ppo_pct is not None else "")
        ),
    )
    if batch_total > 0:
        batch_ratio = float(batch_steps) / float(max(1, batch_total))
        st.progress(
            max(0.0, min(1.0, batch_ratio)),
            text=(
                f"Huidige PPO-batch: {batch_steps:,}/{batch_total:,} timesteps"
                + (f" ({(batch_pct or 0.0):.1f}%)" if batch_pct is not None else "")
            ),
        )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Totaal PPO", f"{ppo_steps:,}")
    c2.metric("Gepland totaal", f"{ppo_total:,}")
    c3.metric("Batch steps", f"{batch_steps:,}" if batch_total > 0 else "—")
    c4.metric("Batch %", f"{(batch_pct or 0.0):.1f}%" if batch_pct is not None and batch_total > 0 else "—")


def _render_certified_data_metrics(progress: dict[str, Any], *, estimate_days: int) -> None:
    mode = str(progress.get("training_mode", "") or "").strip().lower()
    if mode != "certified":
        return
    real_days = int(progress.get("actual_real_days_loaded", 0) or 0)
    real_pct = progress.get("real_data_pct")
    m1, m2, m3 = st.columns(3)
    m1.metric("Echte dagen geladen", real_days)
    m2.metric("Geschat benodigd", estimate_days)
    if isinstance(real_pct, (int, float)):
        m3.metric("Real data %", f"{float(real_pct):.1f}%")
    else:
        m3.metric("Real data %", "—")
    if real_days > 0 and real_days < estimate_days:
        st.caption(
            "Minder echte dagen geladen dan geschat nodig; verhoog max_real_days of verlaag training trades."
        )


def _progress_recently_active(progress: dict[str, Any], *, stage: str) -> bool:
    if stage not in _RUNNING_STAGES:
        return False
    age = _progress_age_seconds(progress)
    return age is not None and age < _PROGRESS_ACTIVE_MAX_AGE_SEC


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
        read_bytes = max(8_192, max_lines * 1_024)
        with stderr_path.open("rb") as handle:
            try:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - read_bytes))
            except Exception:
                handle.seek(0)
            lines = handle.read().decode("utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        return ""
    return "\n".join(non_empty[-max_lines:])


def _cached_duration_estimate(
    *,
    training_trades: int,
    max_real_days: int,
    prefer_real_data_only: bool,
    allow_fallback: bool,
    workspace_root: Path,
    ttl_seconds: float = 30.0,
):
    cache_key = (
        int(training_trades),
        int(max_real_days),
        bool(prefer_real_data_only),
        bool(allow_fallback),
    )
    cache = st.session_state.get("first_boot_duration_estimate_cache")
    now = time.time()
    if isinstance(cache, dict) and cache.get("key") == cache_key and (now - float(cache.get("ts", 0.0))) < ttl_seconds:
        cached = cache.get("value")
        if cached is not None:
            return cached
    estimate = estimate_first_boot_duration(
        training_trades=int(training_trades),
        max_real_days=int(max_real_days),
        prefer_real_data_only=bool(prefer_real_data_only),
        allow_minimal_synthetic_fallback=bool(allow_fallback),
        workspace_root=workspace_root,
    )
    st.session_state["first_boot_duration_estimate_cache"] = {"key": cache_key, "ts": now, "value": estimate}
    return estimate


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


def _persist_first_boot_settings(
    first_boot_manager: FirstBootManager,
    *,
    training_trades: int,
    prefer_real_data_only: bool,
    max_real_days: int,
    allow_minimal_synthetic_fallback: bool,
    require_real_simulator_data: bool,
) -> None:
    """Persist first-boot settings only — never starts Birth Phase."""
    _clear_start_request_flags()
    first_boot_manager.save_full_settings(
        training_trades=int(training_trades),
        prefer_real_data_only=bool(prefer_real_data_only),
        max_real_days=int(max_real_days),
        allow_minimal_synthetic_fallback=bool(allow_minimal_synthetic_fallback),
        require_real_simulator_data=bool(require_real_simulator_data),
        mark_user_configured=True,
    )
    persisted = first_boot_manager.read_settings()
    persisted_signature = build_first_boot_settings_signature_from_settings(persisted)
    st.session_state["first_boot_saved_signature"] = persisted_signature
    st.session_state["first_boot_rehydrate"] = True


def _start_birth_training(
    *,
    birth_service: BirthService | None,
    backend_client: BackendClient | None,
    workspace_root: Path,
    target_trades: int,
    force: bool = False,
    practice_mode: bool = False,
    require_explicit_request: bool = True,
) -> tuple[bool, str]:
    """Start Birth Phase via in-process BirthService, with HTTP fallback to FastAPI."""
    if require_explicit_request and not _explicit_start_requested():
        return False, "Start Birth Phase vereist een expliciete klik op Start (of Retry/Practice)."

    try:
        if birth_service is not None:
            birth_service.configure_workspace(workspace_root)
            result = birth_service.start_birth(
                target_trades=int(target_trades),
                force=bool(force),
                practice_mode=bool(practice_mode),
                explicit_user_start=True,
            )
            status = str(result.get("status", "")).strip().lower()
            message = str(result.get("message", "") or "").strip()
            if status in {"started", "already_running"}:
                return True, message or "Birth Phase gestart."
            return False, message or f"Birth Phase kon niet starten ({status or 'unknown'})."

        if backend_client is not None:
            payload = backend_client.start_birth_sync(
                target_trades=int(target_trades),
                force=bool(force),
                practice_mode=bool(practice_mode),
                explicit_user_start=True,
            )
            if payload.get("error"):
                detail = str(payload.get("detail", "") or "").strip()
                return False, f"Backend: {payload.get('error')}" + (f" — {detail}" if detail else "")
            status = str(payload.get("status", "")).strip().lower()
            message = str(payload.get("message", "") or "").strip()
            if status in {"started", "already_running"}:
                return True, message or "Birth Phase gestart via backend."
            return False, message or f"Backend weigerde start ({status or 'unknown'})."

        return False, "Geen BirthService of backend-client beschikbaar."
    finally:
        _clear_start_request_flags()


def _stop_birth_training(
    *,
    first_boot_manager: FirstBootManager,
    birth_service: BirthService | None,
    backend_client: BackendClient | None,
    process_manager: ProcessManager | None,
    progress: dict[str, Any],
    stage: str,
) -> tuple[bool, str]:
    """Stop Birth Phase thread, backend birth, legacy runtime, and unlock settings."""
    messages: list[str] = []
    any_action = False
    progress_active = _progress_recently_active(progress, stage=stage)
    birth_thread_running = birth_service is not None and birth_service.is_running()

    if birth_service is not None and (birth_thread_running or progress_active or birth_service.is_stopping()):
        result = birth_service.stop_birth()
        status = str(result.get("status", "") or "").strip().lower()
        message = str(result.get("message", "") or "").strip()
        messages.append(message or f"Birth stop: {status or 'unknown'}")
        any_action = status in {"stopped", "stopping"}

    if backend_client is not None and (progress_active or not birth_thread_running):
        payload = backend_client.stop_birth_sync()
        if not payload.get("error"):
            status = str(payload.get("status", "") or "").strip().lower()
            message = str(payload.get("message", "") or "").strip()
            if status in {"stopped", "stopping"}:
                any_action = True
            if message:
                messages.append(message)
        elif progress_active:
            detail = str(payload.get("detail", "") or payload.get("error", "") or "").strip()
            messages.append(f"Backend stop: {detail}" if detail else "Backend stop mislukt.")

    first_boot_manager.request_pause()

    if process_manager is not None:
        ok_rt, rt_msg = process_manager.stop_bot()
        if ok_rt and "already stopped" not in rt_msg.lower():
            any_action = True
        messages.append(rt_msg)

    st.session_state["first_boot_settings_locked"] = False

    if not messages:
        return False, "Geen actieve training gevonden."
    summary = " ".join(m for m in messages if m).strip()
    if any_action or birth_thread_running or progress_active:
        return True, summary or "Stop aangevraagd."
    return False, summary or "Geen actieve training gevonden."


def _is_history_unavailable(progress: dict[str, Any], stage: str) -> bool:
    phase = str(progress.get("phase", "") or "").strip().lower()
    return stage == "history_unavailable" or phase == "loading_history_failed"


def _render_history_unavailable_panel(
    *,
    first_boot_manager: FirstBootManager,
    stage: str,
    progress: dict[str, Any],
    settings: dict[str, Any],
    birth_service: BirthService | None,
    backend_client: BackendClient | None,
) -> None:
    st.error("Historische data tijdelijk niet beschikbaar.")
    st.warning(
        "Birth Phase kon geen real historical data laden (Crosstrade/NT-historie). "
        "Controleer credentials, netwerk en instrument."
    )
    msg = str(progress.get("message", "") or "").strip()
    if msg:
        st.caption(f"Details: {msg}")
    st.caption(
        "Je kan opnieuw proberen, een practice-run starten met synthetic data, "
        "of deze melding sluiten en later opnieuw proberen."
    )
    st.caption(
        "Let op: practice (synthetic) telt niet mee voor live-gang. "
        "Live kan pas na succesvolle training op real historical data."
    )

    retry_col, practice_col, close_col = st.columns(3)
    target_trades = int(settings.get("training_trades", FIRST_BOOT_DEFAULT_TRADES))
    with retry_col:
        if st.button("Opnieuw proberen", key="birth_retry_real", use_container_width=True):
            _arm_explicit_birth_start()
            first_boot_manager.clear_progress_runtime_state()
            ok, msg_retry = _start_birth_training(
                birth_service=birth_service,
                backend_client=backend_client,
                workspace_root=first_boot_manager.workspace_root,
                target_trades=target_trades,
                force=True,
                practice_mode=False,
            )
            if ok:
                st.session_state["first_boot_last_start_failed"] = False
                st.session_state["first_boot_settings_locked"] = True
                st.success(msg_retry)
            else:
                st.session_state["first_boot_last_start_failed"] = True
                st.session_state["first_boot_last_start_error"] = msg_retry
                st.error(msg_retry)
            st.rerun()
    with practice_col:
        if st.button("Practice met synthetic", key="birth_retry_practice", use_container_width=True):
            _arm_explicit_birth_start()
            first_boot_manager.clear_progress_runtime_state()
            ok, msg_practice = _start_birth_training(
                birth_service=birth_service,
                backend_client=backend_client,
                workspace_root=first_boot_manager.workspace_root,
                target_trades=target_trades,
                force=True,
                practice_mode=True,
            )
            if ok:
                st.session_state["first_boot_last_start_failed"] = False
                st.session_state["first_boot_settings_locked"] = True
                st.success(msg_practice)
            else:
                st.session_state["first_boot_last_start_failed"] = True
                st.session_state["first_boot_last_start_error"] = msg_practice
                st.error(msg_practice)
            st.rerun()
    with close_col:
        if st.button("Sluiten (later opnieuw)", key="birth_close_unavailable", use_container_width=True):
            first_boot_manager.clear_progress_runtime_state()
            st.session_state["first_boot_settings_locked"] = False
            st.session_state["first_boot_last_start_failed"] = False
            st.session_state["first_boot_last_start_error"] = ""
            st.rerun()
    st.divider()


def _birth_training_active(
    *,
    birth_service: BirthService | None,
    process_alive: bool,
    progress: dict[str, Any] | None = None,
    stage: str = "",
) -> bool:
    if birth_service is not None and birth_service.is_running():
        return True
    if birth_service is not None and birth_service.is_stopping():
        return True
    if process_alive:
        return True
    if progress is not None and _progress_recently_active(progress, stage=stage):
        return True
    return False


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
    progress_recently_active = _progress_recently_active(progress, stage=stage)
    training_active = _birth_training_active(
        birth_service=birth_service,
        process_alive=process_alive,
        progress=progress,
        stage=stage,
    )
    if birth_running:
        st.session_state["first_boot_settings_locked"] = True
    elif not training_active:
        st.session_state["first_boot_settings_locked"] = False

    settings_locked = bool(st.session_state.get("first_boot_settings_locked", False))
    stale_running_stage = stage in _RUNNING_STAGES and not training_active and not progress_recently_active
    orphan_progress_active = progress_recently_active and not birth_running and not process_alive

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

    if _is_history_unavailable(progress, stage) and not training_active:
        _render_history_unavailable_panel(
            first_boot_manager=first_boot_manager,
            stage=stage,
            progress=progress,
            settings=settings,
            birth_service=birth_service,
            backend_client=backend_client,
        )

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
    duration_estimate = _cached_duration_estimate(
        training_trades=int(training_trades),
        max_real_days=int(max_real_days),
        prefer_real_data_only=bool(prefer_real_data_only),
        allow_fallback=bool(allow_fallback),
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
    runtime_crashed = runtime_marked_started and (not training_active) and (not progress or ppo_interrupted)
    runtime_stderr_tail = _read_runtime_stderr_tail(root) if (runtime_crashed or recent_start_failed or ppo_interrupted) else ""

    save_col, start_col, stop_col = st.columns(3)
    with save_col:
        st.button(
            "💾 Save Settings",
            key=_SAVE_SETTINGS_KEY,
            use_container_width=True,
            disabled=settings_locked,
            on_click=_on_save_settings_click,
        )
    with start_col:
        start_disabled = dirty_settings or settings_locked or (birth_service is None and backend_client is None)
        st.button(
            "▶️ Start Birth Phase",
            key=_START_BIRTH_KEY,
            type="primary",
            use_container_width=True,
            disabled=start_disabled,
            on_click=_on_start_birth_click,
        )
    with stop_col:
        st.button(
            "⏹️ Stop training",
            key=_STOP_TRAINING_KEY,
            use_container_width=True,
            on_click=_on_stop_training_click,
        )

    if st.session_state.pop(_FIRST_BOOT_PENDING_STOP_KEY, False):
        ok, msg = _stop_birth_training(
            first_boot_manager=first_boot_manager,
            birth_service=birth_service,
            backend_client=backend_client,
            process_manager=process_manager,
            progress=progress,
            stage=stage,
        )
        if ok:
            st.success(msg)
        else:
            st.warning(msg)
        st.rerun()

    if st.session_state.pop(_FIRST_BOOT_PENDING_SAVE_KEY, False):
        if birth_running:
            st.warning("Birth Phase draait al; instellingen zijn niet gewijzigd.")
        else:
            _persist_first_boot_settings(
                first_boot_manager,
                training_trades=int(training_trades),
                prefer_real_data_only=bool(prefer_real_data_only),
                max_real_days=int(max_real_days),
                allow_minimal_synthetic_fallback=bool(allow_fallback),
                require_real_simulator_data=bool(require_real_sim),
            )
            st.success(
                "Instellingen opgeslagen. Klik **Start Birth Phase** om training te starten."
            )
        st.rerun()

    if st.session_state.pop(_FIRST_BOOT_PENDING_START_KEY, False):
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
        st.rerun()

    if settings_locked:
        st.warning("Instellingen zijn vergrendeld tijdens/na gestart Birth Phase training.")
    elif dirty_settings:
        st.info("Start Birth Phase is pas actief nadat je op Save Settings hebt geklikt.")

    if birth_running:
        birth_status = birth_service.get_status() if birth_service is not None else {}
        elapsed = birth_status.get("elapsed_seconds")
        elapsed_txt = f" ({elapsed}s)" if elapsed is not None else ""
        st.success(f"Birth Phase status: actief{elapsed_txt}.")
    elif birth_service is not None and birth_service.is_stopping():
        st.warning("Birth Phase status: stop aangevraagd — wacht op checkpoint.")
    elif orphan_progress_active:
        st.warning(
            "Birth Phase lijkt nog actief (recente progress op schijf) maar geen lokale thread. "
            "Klik **Stop training** om te stoppen."
        )
    elif stale_running_stage:
        st.warning(
            "Laatste progress op schijf toont een eerdere run; Birth Phase draait niet actief. "
            "Klik **Start Birth Phase** om opnieuw te starten."
        )
    elif _is_history_unavailable(progress, stage):
        st.error("Birth status: real historical data tijdelijk niet beschikbaar.")
    elif process_alive:
        st.success("Legacy runtime-bot actief (lumina_runtime.py).")
    elif ppo_interrupted:
        st.error(
            "Birth status: PPO-training onderbroken — process/thread is niet actief en policy ontbreekt nog. "
            "Klik op **Start Birth Phase** om PPO te hervatten."
        )
    elif runtime_crashed:
        st.error(
            f"Birth status: gestopt na start (laatste pid={runtime_pid}). "
            "Controleer `logs/launcher_runtime_stderr.log`."
        )
    elif recent_start_failed:
        last_error = str(st.session_state.get("first_boot_last_start_error", "") or "").strip()
        st.error(
            "Birth status: laatste startpoging mislukt."
            + (f" {last_error}" if last_error else " Controleer `logs/launcher_runtime_stderr.log`.")
        )
    else:
        st.info("Birth status: niet actief.")

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
        phase = str(progress.get("phase", "") or "").strip().lower()
        pct = first_boot_manager.get_stage_progress(stage)
        st.progress(pct, text=f"Stage: {stage}")
        if phase:
            st.caption(f"Phase: {phase}")
        _render_training_mode_warning(progress)
        _render_certified_data_metrics(progress, estimate_days=estimate_days)
        completed_trades = resolve_first_boot_completed_trades(progress)
        target = int(settings.get("training_trades", FIRST_BOOT_DEFAULT_TRADES))
        has_saved_settings = first_boot_manager.is_user_configured()
        st.metric("Trades Completed", f"{completed_trades:,}")
        if has_saved_settings:
            st.caption(f"Target trades: {target:,}")
        else:
            st.caption("Target trades: nog niet geconfigureerd (klik eerst op Save Settings).")
        if is_sim_trades_complete(progress):
            st.caption("SIM-training: afgerond voor geconfigureerd trade-aantal.")
        if ppo_phase and not show_summary:
            _render_birth_phase_status_banner(
                progress=progress,
                completed_trades=completed_trades,
                target_trades=target,
                ppo_phase=ppo_phase,
            )
            _render_ppo_progress_bars(progress)
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
            st.error("Birth crash gedetecteerd: training is niet actief. Bekijk de stderr-log hierboven.")
        else:
            st.info("Nog geen progress gevonden. Klik op Start Birth Phase om first-boot te starten.")

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
