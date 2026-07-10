"""Birth retry/resume recovery paths (checkpoint-preserving)."""

from __future__ import annotations

from typing import Any, Dict

from lumina_core.logging_utils import get_logger
from lumina_launcher.services.birth_status_mapper import resolve_terminal_birth_status

logger = get_logger(__name__)


def is_stage_stalled_recovery_eligible(svc: Any) -> bool:
    progress = svc._load_progress()
    terminal = resolve_terminal_birth_status(progress)
    if terminal is not None and terminal[0] == "stage_stalled":
        return True
    from lumina_core.birth.checkpoint import load_checkpoint_state

    checkpoint_state = load_checkpoint_state(svc.workspace_root)
    ckpt_phase = str(checkpoint_state.get("phase", "") or "").strip().lower()
    progress_phase = str(progress.get("phase", "") or "").strip().lower()
    recoverable_phases = {"stage_stalled", "plateau_evolution", "stall_remediation", "phoenix_cycle"}
    if ckpt_phase in recoverable_phases:
        return True
    return progress_phase in recoverable_phases


def retry_birth(
    svc: Any,
    target_trades: int | None = None,
    *,
    wipe: bool = False,
) -> Dict[str, Any]:
    """Resume from checkpoint on certificate failure; wipe only when explicitly requested."""
    from lumina_core.birth.config import BRO_ENGINE_VERSION
    from lumina_core.birth.checkpoint import load_checkpoint_state
    from lumina_core.birth.remediation import (
        reconstruct_checkpoint_from_progress,
        should_fast_path_remediation_from_state,
    )

    progress = svc._load_progress()
    phase = str(progress.get("phase", "") or "").strip().lower()
    checkpoint_state = load_checkpoint_state(svc.workspace_root)
    checkpoint_exists = (
        svc.checkpoint_file.exists()
        or (svc.workspace_root / "state" / "first_boot_checkpoint.json").exists()
    )
    fast_path_eligible = (
        should_fast_path_remediation_from_state(progress, checkpoint_state) if not wipe else False
    )
    preserve_checkpoint = not wipe and fast_path_eligible
    if preserve_checkpoint and not checkpoint_exists:
        policy_hint = str(svc.policy_path) if svc.policy_path.exists() else ""
        reconstructed = reconstruct_checkpoint_from_progress(
            svc.workspace_root,
            progress,
            policy_path=policy_hint,
            checkpoint=checkpoint_state,
        )
        if not reconstructed:
            logger.warning(
                "birth.retry reconstruct_failed phase=%s policy_exists=%s",
                phase,
                svc.policy_path.exists(),
            )
            preserve_checkpoint = False
        checkpoint_exists = (
            svc.checkpoint_file.exists()
            or (svc.workspace_root / "state" / "first_boot_checkpoint.json").exists()
        )
    logger.info(
        "birth.retry preserve_checkpoint=%s phase=%s checkpoint_exists=%s wipe=%s "
        "fast_path_eligible=%s engine_version=%s",
        preserve_checkpoint,
        phase,
        checkpoint_exists,
        wipe,
        fast_path_eligible,
        BRO_ENGINE_VERSION,
    )
    if wipe:
        from lumina_launcher.services.birth_runner_wipe import wipe_birth_training_artifacts

        wipe_error = wipe_birth_training_artifacts(svc)
        if wipe_error is not None:
            return wipe_error
    elif not preserve_checkpoint:
        from lumina_launcher.core.first_boot import FirstBootManager

        FirstBootManager(svc.workspace_root).clear_stale_for_certified_retry()
    from lumina_launcher.services.birth_runner_start import start_birth

    return start_birth(
        svc,
        target_trades=target_trades,
        force=not preserve_checkpoint,
        explicit_user_start=True,
        continue_training=preserve_checkpoint,
    )


def resume_stalled_stage(svc: Any, target_trades: int | None = None) -> Dict[str, Any]:
    """Resume curriculum from terminal stage_stalled without wiping checkpoint."""
    from lumina_core.birth.checkpoint import reset_adaptation_budget_for_manual_resume

    if not is_stage_stalled_recovery_eligible(svc):
        return {
            "status": "rejected",
            "message": "Resume stage requires stage_stalled progress or checkpoint.",
        }
    reset_adaptation_budget_for_manual_resume(svc.workspace_root)
    from lumina_launcher.services.birth_runner_start import start_birth

    return start_birth(
        svc,
        target_trades=target_trades,
        force=False,
        explicit_user_start=True,
        continue_training=True,
    )


def expand_and_retry_stalled_stage(svc: Any, target_trades: int | None = None) -> Dict[str, Any]:
    """Expand historical data window then resume stalled stage (no checkpoint wipe)."""
    from lumina_core.birth.checkpoint import (
        read_checkpoint_payload,
        reset_adaptation_budget_for_manual_resume,
        write_checkpoint_payload,
    )

    if not is_stage_stalled_recovery_eligible(svc):
        return {
            "status": "rejected",
            "message": "Expand and retry requires stage_stalled progress or checkpoint.",
        }
    reset_adaptation_budget_for_manual_resume(svc.workspace_root)
    payload = read_checkpoint_payload(svc.workspace_root)
    if payload:
        metrics = dict(payload.get("stage_metrics") or {})
        metrics["pending_data_expand"] = True
        payload["stage_metrics"] = metrics
        payload["phase"] = "curriculum_learning"
        write_checkpoint_payload(svc.workspace_root, payload)
    from lumina_launcher.services.birth_runner_start import start_birth

    return start_birth(
        svc,
        target_trades=target_trades,
        force=False,
        explicit_user_start=True,
        continue_training=True,
        reuse_data=True,
        expand_data=True,
    )


def resume_birth(svc: Any, target_trades: int | None = None) -> Dict[str, Any]:
    """Non-destructive resume from the last birth checkpoint."""
    from lumina_launcher.services.birth_runner_start import start_birth

    return start_birth(
        svc,
        target_trades=target_trades,
        force=False,
        explicit_user_start=True,
        continue_training=True,
    )


def reuse_data_birth(svc: Any, target_trades: int | None = None) -> Dict[str, Any]:
    """Resume checkpoint and skip holdout preflight expansion when manifest hash matches."""
    from lumina_launcher.services.birth_runner_start import start_birth

    return start_birth(
        svc,
        target_trades=target_trades,
        force=False,
        explicit_user_start=True,
        continue_training=True,
        reuse_data=True,
    )