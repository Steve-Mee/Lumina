"""Operator retry of the current curriculum stage (occupancy fencepost recovery)."""

from __future__ import annotations

from typing import Any, Dict

from lumina_core.logging_utils import get_logger

logger = get_logger(__name__)


def retry_current_stage(svc: Any, target_trades: int | None = None) -> Dict[str, Any]:
    """Zero poisoned current-stage sample, keep S1/S2 + tape. No expand. Operator only."""
    from lumina_core.birth.checkpoint import (
        read_checkpoint_payload,
        write_checkpoint_payload,
    )
    from lumina_core.birth.progress import write_birth_progress
    from lumina_core.birth.stage_sample_reset import reset_current_stage_sample
    from lumina_core.birth.terminal_freeze import (
        extract_terminal_freeze,
        mark_freeze_resolved,
    )
    from lumina_launcher.services.birth_runner_recovery import (
        is_stage_stalled_recovery_eligible,
    )
    from lumina_launcher.services.birth_runner_start import start_birth

    if not is_stage_stalled_recovery_eligible(svc):
        return {
            "status": "rejected",
            "message": "Retry stage requires stage_stalled progress or checkpoint.",
        }
    progress = dict(svc._load_progress())
    try:
        payload = read_checkpoint_payload(svc.workspace_root) or {}
    except Exception:
        payload = {}
    metrics = reset_current_stage_sample(payload.get("stage_metrics"))
    freeze = extract_terminal_freeze(progress, payload, metrics)
    resolved = None
    if freeze:
        resolved = mark_freeze_resolved(
            freeze,
            action="retry_stage",
            resolved_by="autonomy",
        )
        metrics["terminal_freeze"] = resolved
        payload["terminal_freeze"] = resolved
        progress["terminal_freeze"] = resolved
    payload["stage_metrics"] = metrics
    if str(payload.get("phase") or "").strip().lower() in {
        "stage_stalled",
        "paused",
        "plateau_evolution",
        "stall_remediation",
        "swarm_reject_hard_stop",
        "phoenix_cycle",
    }:
        payload["phase"] = "curriculum_learning"
    write_checkpoint_payload(svc.workspace_root, payload)
    message = (
        "Stage sample reset after occupancy fencepost — retrying current stage "
        "on the same tape. S1/S2 receipts kept. No expand."
    )
    try:
        write_birth_progress(
            svc.workspace_root,
            stage="training_running",
            phase="curriculum_learning",
            message=message,
            progress_pct=float(progress.get("progress_pct") or 0),
            cumulative_trades=int(progress.get("cumulative_trades") or 0),
            target_trades=int(progress.get("target_trades") or 0),
            ppo_steps=int(progress.get("ppo_steps") or 0),
            birth_start_time=float(progress.get("birth_start_time") or 0),
            swarm_rejected_no_lift=False,
            swarm_champion_accepted=False,
            policy_swarm_rejected_no_lift=False,
            policy_swarm_champion_accepted=False,
            needs_attention=False,
            retryable=True,
            attention_summary="",
            attention_reason_code="",
            attention_recommended_actions=[],
            user_initiated_stop=False,
            curriculum_stage=str(progress.get("curriculum_stage") or ""),
            terminal_freeze=resolved,
        )
    except Exception as exc:
        logger.warning("birth.retry_stage.progress_write_failed: %s", exc)
    return start_birth(
        svc,
        target_trades=target_trades,
        force=False,
        explicit_user_start=True,
        continue_training=True,
        reuse_data=True,
    )
