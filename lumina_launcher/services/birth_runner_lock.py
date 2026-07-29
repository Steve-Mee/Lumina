"""Birth runner lock + interrupted progress persistence."""

from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from typing import Any, Dict

from lumina_core.first_boot_progress import (
    birth_runner_lock_active,
    birth_training_is_live,
    read_birth_runner_lock,
    resolve_first_boot_stage,
)
from lumina_core.first_boot_ui import FIRST_BOOT_DEFAULT_TRADES
from lumina_core.logging_utils import get_logger
from lumina_launcher.services.birth_status_mapper import BIRTH_ACTIVE_STAGES

logger = get_logger(__name__)


def write_runner_lock(svc: Any) -> None:
    payload = {
        "pid": int(os.getpid()),
        "host": socket.gethostname(),
        "runner": "thread",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(svc.workspace_root),
    }
    try:
        svc.runner_lock_path.parent.mkdir(parents=True, exist_ok=True)
        svc.runner_lock_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    except OSError:
        logger.warning("birth.runner_lock.write_failed path=%s", svc.runner_lock_path, exc_info=True)


def read_runner_lock(svc: Any) -> Dict[str, Any] | None:
    return read_birth_runner_lock(svc.workspace_root)


def clear_runner_lock(svc: Any) -> None:
    try:
        if svc.runner_lock_path.exists():
            svc.runner_lock_path.unlink()
    except OSError:
        logger.warning("birth.runner_lock.clear_failed path=%s", svc.runner_lock_path, exc_info=True)


def clear_stale_runner_lock(svc: Any) -> None:
    if not svc.runner_lock_path.exists():
        return
    if birth_runner_lock_active(svc.workspace_root):
        return
    clear_runner_lock(svc)


def reset_in_memory_birth_state(svc: Any) -> None:
    svc._result = None
    svc._error = None
    svc._start_time = None
    svc._stop_requested.clear()
    clear_stale_runner_lock(svc)
    svc._launcher_setup_cache = None
    svc._launcher_setup_cached_at = 0.0
    svc._stalled_auto_resume_attempted = False


def clear_orphan_runner_lock_for_wipe(svc: Any) -> None:
    """Remove stale birth_runner.json when this process has no live birth thread."""
    if svc.is_running():
        return
    payload = read_birth_runner_lock(svc.workspace_root)
    if payload is None:
        return
    raw_pid = payload.get("pid")
    try:
        int(raw_pid)
    except (TypeError, ValueError):
        clear_runner_lock(svc)
        return
    if not birth_runner_lock_active(svc.workspace_root):
        clear_runner_lock(svc)


def mark_user_stopped_progress(svc: Any) -> None:
    """Persist paused progress with user_initiated_stop (Starship pause SSOT)."""
    clear_stale_runner_lock(svc)
    progress = svc._load_progress()
    stage = resolve_first_boot_stage(progress)
    from lumina_core.birth.starship_birth import build_pause_ssot_payload, write_pause_ssot

    merged = dict(progress)
    merged.update(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_trades": int(
                progress.get("target_trades", FIRST_BOOT_DEFAULT_TRADES) or FIRST_BOOT_DEFAULT_TRADES
            ),
            "trades_done": int(progress.get("trades_done", 0) or 0),
            "cumulative_trades": int(progress.get("cumulative_trades", 0) or 0),
            "total_trades": int(progress.get("total_trades", 0) or 0),
            "ppo_steps": int(progress.get("ppo_steps", 0) or 0),
            "progress_pct": float(progress.get("progress_pct", 0) or 0),
            "prior_stage": (
                stage if stage in BIRTH_ACTIVE_STAGES else str(progress.get("stage", "") or "")
            ),
            "prior_phase": str(progress.get("phase", "") or ""),
            "curriculum_stage": str(
                progress.get("curriculum_stage") or progress.get("prior_stage") or ""
            ),
        }
    )
    payload = build_pause_ssot_payload(
        progress=merged,
        message=(
            "Birth Phase gestopt door gebruiker. "
            "Kies Hervat checkpoint of Wis birth-data voor schone run."
        ),
    )
    write_pause_ssot(svc.workspace_root, payload)
    try:
        if svc.pause_flag_path.exists():
            svc.pause_flag_path.unlink()
    except OSError:
        logger.warning("birth.user_stop.pause_clear_failed", exc_info=True)
    try:
        from lumina_core.notifications.attention_events import birth_interrupted_event
        from lumina_core.notifications.operator_notifier import notify_problem

        notify_problem(
            birth_interrupted_event(detail=str(payload.get("message", "") or "")),
            workspace_root=svc.workspace_root,
        )
    except Exception as exc:
        logger.warning("birth.interrupted_attention_failed: %s", exc)


def reconcile_orphaned_birth_progress(svc: Any) -> bool:
    """Mark on-disk active progress as interrupted when no live Birth runner exists."""
    clear_stale_runner_lock(svc)
    progress = svc._load_progress()
    stage = resolve_first_boot_stage(progress)
    phase = str(progress.get("phase", "") or "").strip().lower()
    # Starship: also reconcile plateau/stall death-modes (where birth most often dies).
    orphan_recovery_phases = {
        "plateau_evolution",
        "stall_remediation",
        "stage_stalled",
        "phoenix_cycle",
        "policy_swarm",
        "exploration_burst",
    }
    if stage not in BIRTH_ACTIVE_STAGES and phase not in orphan_recovery_phases and stage not in orphan_recovery_phases:
        return False
    if birth_training_is_live(svc.workspace_root, thread_running=svc.is_running()):
        return False
    from lumina_core.birth.starship_birth import build_pause_ssot_payload, write_pause_ssot

    merged = dict(progress)
    merged.update(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_trades": int(
                progress.get("target_trades", FIRST_BOOT_DEFAULT_TRADES) or FIRST_BOOT_DEFAULT_TRADES
            ),
            "trades_done": int(progress.get("trades_done", 0) or 0),
            "cumulative_trades": int(progress.get("cumulative_trades", 0) or 0),
            "total_trades": int(progress.get("total_trades", 0) or 0),
            "ppo_steps": int(progress.get("ppo_steps", 0) or 0),
            "progress_pct": float(progress.get("progress_pct", 0) or 0),
            "prior_stage": stage,
            "prior_phase": str(progress.get("phase", "") or ""),
            "curriculum_stage": str(progress.get("curriculum_stage") or stage or ""),
        }
    )
    payload = build_pause_ssot_payload(
        progress=merged,
        message=(
            "Vorige sessie onderbroken — klik Hervat checkpoint om verder te gaan."
        ),
    )
    write_pause_ssot(svc.workspace_root, payload)
    logger.info("birth.reconcile_orphaned prior_stage=%s workspace=%s", stage, svc.workspace_root)
    try:
        from lumina_core.notifications.attention_events import birth_interrupted_event
        from lumina_core.notifications.operator_notifier import notify_problem

        notify_problem(
            birth_interrupted_event(detail=str(payload.get("message", "") or "")),
            workspace_root=svc.workspace_root,
        )
    except Exception as exc:
        logger.warning("birth.reconcile_attention_failed: %s", exc)
    return True