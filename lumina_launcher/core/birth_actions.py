"""Birth phase actions shared by tests (BirthService-only; no HTTP client)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.first_boot_progress import resolve_birth_training_pulse
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.birth_service import BirthService


def persist_first_boot_settings(
    first_boot_manager: FirstBootManager,
    *,
    training_trades: int,
    prefer_real_data_only: bool,
    max_real_days: int,
    allow_minimal_synthetic_fallback: bool,
    require_real_simulator_data: bool,
) -> None:
    """Persist first-boot settings only — never starts Birth Phase."""
    first_boot_manager.save_full_settings(
        training_trades=int(training_trades),
        prefer_real_data_only=bool(prefer_real_data_only),
        max_real_days=int(max_real_days),
        allow_minimal_synthetic_fallback=bool(allow_minimal_synthetic_fallback),
        require_real_simulator_data=bool(require_real_simulator_data),
        mark_user_configured=True,
    )


def _resolve_birth_status_payload(
    *,
    birth_service: BirthService | None,
    workspace_root: Path,
) -> dict[str, Any]:
    if birth_service is not None:
        birth_service.configure_workspace(workspace_root)
        return birth_service.get_status()
    return {}


def _birth_status_is_running(status_payload: dict[str, Any]) -> bool:
    raw = str(status_payload.get("status", "") or "").strip().lower()
    return raw in {"running", "started", "already_running"}


def resolve_command_center_birth_flags(
    *,
    birth_service: BirthService | None,
    workspace_root: Path,
    process_alive: bool,
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_payload = _resolve_birth_status_payload(
        birth_service=birth_service,
        workspace_root=workspace_root,
    )
    thread_running = bool(birth_service.is_running()) if birth_service is not None else False
    birth_running = _birth_status_is_running(status_payload) or thread_running
    birth_stopping = bool(birth_service.is_stopping()) if birth_service is not None else False
    pulse = resolve_birth_training_pulse(
        progress,
        birth_running=birth_running,
        birth_stopping=birth_stopping,
        process_alive=process_alive,
        workspace_root=workspace_root,
        thread_running=thread_running,
    )
    return {
        "birth_running": birth_running,
        "birth_stopping": birth_stopping,
        "pulse": pulse,
        "status_payload": status_payload,
    }


def start_birth_training(
    *,
    birth_service: BirthService | None,
    workspace_root: Path,
    target_trades: int,
    force: bool = False,
    practice_mode: bool = False,
    continue_training: bool = False,
    explicit_user_start: bool = False,
) -> tuple[bool, str]:
    """Start Birth Phase via in-process BirthService."""
    if not explicit_user_start:
        return False, "Start Birth Phase vereist een expliciete klik op Start (of Retry/Practice)."

    if birth_service is not None:
        birth_service.configure_workspace(workspace_root)
        result = birth_service.start_birth(
            target_trades=int(target_trades),
            force=bool(force),
            practice_mode=bool(practice_mode),
            explicit_user_start=True,
            continue_training=bool(continue_training),
        )
        status = str(result.get("status", "")).strip().lower()
        message = str(result.get("message", "") or "").strip()
        if status in {"started", "already_running"}:
            return True, message or "Birth Phase gestart."
        return False, message or f"Birth Phase kon niet starten ({status or 'unknown'})."

    return False, "Geen BirthService beschikbaar."


def stop_birth_training(
    *,
    first_boot_manager: FirstBootManager,
    birth_service: BirthService | None,
    process_manager: Any | None,
    progress: dict[str, Any],
    stage: str,
) -> tuple[bool, str]:
    """Stop Birth Phase thread and legacy runtime."""
    from lumina_core.first_boot_progress import progress_is_recently_active

    messages: list[str] = []
    any_action = False
    progress_active = progress_is_recently_active(progress, stage=stage)
    birth_thread_running = birth_service is not None and birth_service.is_running()

    if birth_service is not None and (birth_thread_running or progress_active or birth_service.is_stopping()):
        result = birth_service.stop_birth()
        status = str(result.get("status", "") or "").strip().lower()
        message = str(result.get("message", "") or "").strip()
        messages.append(message or f"Birth stop: {status or 'unknown'}")
        any_action = status in {"stopped", "stopping"}

    if process_manager is not None:
        stopped, stop_msg = process_manager.stop_bot()
        if stopped:
            any_action = True
        if stop_msg:
            messages.append(stop_msg)

    first_boot_manager.request_pause()
    if any_action or progress_active:
        return True, " | ".join(m for m in messages if m) or "Training gestopt."
    return False, "Geen actieve Birth Phase training gevonden."
