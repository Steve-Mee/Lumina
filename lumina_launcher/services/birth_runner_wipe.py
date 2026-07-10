"""Birth training artifact wipe and cooperative stop-before-wipe."""

from __future__ import annotations

import time
from typing import Any, Dict

from lumina_core.first_boot_progress import birth_training_is_live
from lumina_core.logging_utils import get_logger
from lumina_launcher.services.birth_runner_lock import (
    clear_orphan_runner_lock_for_wipe,
    reset_in_memory_birth_state,
)

logger = get_logger(__name__)


def ensure_birth_stopped_for_wipe(svc: Any, *, join_timeout: float) -> Dict[str, Any] | None:
    """Stop birth thread and cross-process runner; return error payload if still live."""
    from lumina_launcher.services.birth_runner_start import stop_birth

    if svc.is_running() or svc.is_stopping():
        stop_birth(svc, join_timeout=join_timeout)
    if svc.is_running():
        return {
            "status": "rejected",
            "message": (
                "Birth Phase kon niet volledig stoppen — probeer opnieuw na enkele seconden "
                "of herstart de backend."
            ),
        }

    if birth_training_is_live(svc.workspace_root, thread_running=svc.is_running()):
        stop_birth(svc, join_timeout=min(join_timeout, 10.0))
        clear_orphan_runner_lock_for_wipe(svc)
        deadline = time.monotonic() + min(join_timeout, 15.0)
        while birth_training_is_live(svc.workspace_root, thread_running=svc.is_running()):
            if time.monotonic() >= deadline:
                return {
                    "status": "rejected",
                    "message": (
                        "Birth Phase draait nog (andere runner of lock) — stop birth, "
                        "wacht enkele seconden en probeer opnieuw."
                    ),
                    "checkpoint_resumable": svc.checkpoint_resumable(),
                }
            time.sleep(0.25)
            clear_orphan_runner_lock_for_wipe(svc)

    return None


def wipe_birth_training_artifacts(svc: Any, *, join_timeout: float = 30.0) -> Dict[str, Any] | None:
    """Shared wipe for genesis wipe-all and retry(wipe=True). Returns error dict on failure."""
    stop_result = ensure_birth_stopped_for_wipe(svc, join_timeout=join_timeout)
    if stop_result is not None:
        return stop_result
    from lumina_launcher.core.birth_reset import clear_birth_training_state

    clear_birth_training_state(svc.workspace_root, wipe_genesis=True)
    reset_in_memory_birth_state(svc)
    return None


def wipe_all_birth_data(
    svc: Any,
    *,
    join_timeout: float = 30.0,
    preserve_tick_cache: bool = False,
) -> Dict[str, Any]:
    """Stop active birth (if any) and remove birth training artifacts."""
    logger.info(
        "birth.wipe_all.start thread_running=%s is_stopping=%s workspace=%s preserve_tick_cache=%s",
        svc.is_running(),
        svc.is_stopping(),
        svc.workspace_root,
        preserve_tick_cache,
    )
    stop_result = ensure_birth_stopped_for_wipe(svc, join_timeout=join_timeout)
    if stop_result is not None:
        stop_result["checkpoint_resumable"] = svc.checkpoint_resumable()
        logger.warning(
            "birth.wipe_all.aborted status=%s message=%s checkpoint_resumable=%s",
            stop_result.get("status"),
            stop_result.get("message"),
            stop_result.get("checkpoint_resumable"),
        )
        return stop_result

    from lumina_launcher.core.birth_reset import clear_birth_training_state

    reset_result = clear_birth_training_state(
        svc.workspace_root,
        wipe_genesis=True,
        preserve_tick_cache=bool(preserve_tick_cache),
    )
    reset_in_memory_birth_state(svc)
    svc._launcher_setup_cache = None
    svc._launcher_setup_cached_at = 0.0
    logger.info(
        "birth.wipe_all.completed removed=%s preserved=%s preserve_tick_cache=%s",
        len(reset_result.removed),
        len(reset_result.preserved),
        preserve_tick_cache,
    )
    return {
        "status": "wiped",
        "message": reset_result.message,
        "removed_artifacts": reset_result.removed,
        "preserved_artifacts": reset_result.preserved,
        "checkpoint_resumable": False,
        "setup_complete": False,
        "redirect_to_genesis": True,
        "preserve_tick_cache": bool(preserve_tick_cache),
    }