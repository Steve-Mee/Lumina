"""Birth retry/resume recovery paths (checkpoint-preserving)."""

from __future__ import annotations

from typing import Any, Dict, Optional

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


def _checkpoint_stage_metrics(svc: Any) -> dict[str, Any]:
    try:
        from lumina_core.birth.checkpoint import read_checkpoint_payload

        payload = read_checkpoint_payload(svc.workspace_root) or {}
        metrics = payload.get("stage_metrics")
        return dict(metrics) if isinstance(metrics, dict) else {}
    except Exception:
        return {}


def champion_freeze_active_for_svc(svc: Any, progress: dict[str, Any] | None = None) -> bool:
    """True when swarm no-lift freeze blocks silent service recovery."""
    from lumina_core.birth.starship_swarm_gates import is_champion_freeze_active

    prog = progress if isinstance(progress, dict) else svc._load_progress()
    return is_champion_freeze_active(
        progress=prog,
        checkpoint_metrics=_checkpoint_stage_metrics(svc),
    )


def reject_if_champion_freeze(svc: Any, progress: dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
    """Return reject payload when champion freeze is active; else None."""
    if not champion_freeze_active_for_svc(svc, progress=progress):
        return None
    from lumina_core.birth.starship_swarm_gates import champion_freeze_blocks_recovery_payload

    logger.warning("birth.recovery.blocked_champion_freeze")
    return champion_freeze_blocks_recovery_payload()


def _is_paused_or_interrupted_progress(progress: dict[str, Any]) -> bool:
    stage = str(progress.get("stage", "") or "").strip().lower()
    phase = str(progress.get("phase", "") or "").strip().lower()
    if progress.get("user_initiated_stop") is True:
        return True
    return stage in {"paused", "interrupted"} or phase in {"paused", "interrupted"}


def retry_birth(
    svc: Any,
    target_trades: int | None = None,
    *,
    wipe: bool = False,
) -> Dict[str, Any]:
    """Resume from checkpoint on certificate failure / user pause; wipe only when asked.

    Critical: user-paused runs with a checkpoint must **continue**, never
    ``clear_stale_for_certified_retry`` (that deletes checkpoint + progress).
    """
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
    # Paused/interrupted + checkpoint = honest resume (not cert fast-path only).
    paused_resume = (
        not wipe and checkpoint_exists and _is_paused_or_interrupted_progress(progress)
    )
    preserve_checkpoint = not wipe and (fast_path_eligible or paused_resume)
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
        "fast_path_eligible=%s paused_resume=%s engine_version=%s",
        preserve_checkpoint,
        phase,
        checkpoint_exists,
        wipe,
        fast_path_eligible,
        paused_resume,
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
        # Resume with preserved checkpoint reuses tick cache / manifest; no launcher history probe.
        reuse_data=bool(preserve_checkpoint),
    )


def resume_stalled_stage(svc: Any, target_trades: int | None = None) -> Dict[str, Any]:
    """Resume curriculum from terminal stage_stalled without wiping checkpoint."""
    from lumina_core.birth.checkpoint import reset_adaptation_budget_for_manual_resume

    blocked = reject_if_champion_freeze(svc)
    if blocked is not None:
        return blocked
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

    blocked = reject_if_champion_freeze(svc)
    if blocked is not None:
        return blocked
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


def persist_operator_resolved_terminal_freeze(
    svc: Any,
    *,
    action: str,
    source: str,
) -> None:
    """Explicit Continue-from-checkpoint resolves an unresolved terminal freeze.

    Swarm-accept flags can be cleared while ``terminal_freeze.resolved`` stays
    false; the curriculum gate then blocks HUD/process-R forever. Operator
    resume is the Twin fork — mark the freeze resolved on disk before start.
    """
    from lumina_core.birth.checkpoint import read_checkpoint_payload, write_checkpoint_payload
    from lumina_core.birth.progress import write_birth_progress
    from lumina_core.birth.terminal_freeze import (
        extract_terminal_freeze,
        freeze_is_active,
        mark_freeze_resolved,
    )

    progress = dict(svc._load_progress())
    try:
        payload = read_checkpoint_payload(svc.workspace_root) or {}
    except Exception:
        payload = {}
    freeze = extract_terminal_freeze(progress, payload, payload.get("stage_metrics"))
    if freeze is None or not freeze_is_active(freeze):
        return
    resolved = mark_freeze_resolved(freeze, action=action, resolved_by=str(source or "app"))
    metrics = dict(payload.get("stage_metrics") or {})
    metrics["terminal_freeze"] = resolved
    payload["stage_metrics"] = metrics
    payload["terminal_freeze"] = resolved
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
    try:
        write_birth_progress(
            svc.workspace_root,
            stage=str(progress.get("stage") or "paused"),
            phase=str(progress.get("phase") or "paused"),
            message=str(progress.get("message") or ""),
            progress_pct=float(progress.get("progress_pct") or 0),
            cumulative_trades=int(progress.get("cumulative_trades") or 0),
            target_trades=int(progress.get("target_trades") or 0),
            ppo_steps=int(progress.get("ppo_steps") or 0),
            birth_start_time=float(progress.get("birth_start_time") or 0),
            terminal_freeze=resolved,
            curriculum_stage=str(progress.get("curriculum_stage") or ""),
        )
    except Exception as exc:
        logger.debug("birth.resume.freeze_progress_write_failed: %s", exc)


def resume_birth(svc: Any, target_trades: int | None = None) -> Dict[str, Any]:
    """Non-destructive resume from the last birth checkpoint.

    Silent recovery (stall auto-retry / expand) stays blocked under champion freeze.
    Explicit operator **Continue from checkpoint** with freeze active means:
    accept the frozen champion and continue curriculum (not wipe).
    """
    from lumina_launcher.services.birth_runner_start import clear_birth_pause_flags, start_birth

    # Explicit resume: clear pause flags before thread spawn (defense in depth).
    clear_birth_pause_flags(svc)
    # Fail-closed: require checkpoint so we never hollow-"start" a wiped workspace.
    checkpoint_exists = (
        getattr(svc, "checkpoint_file", None) is not None and svc.checkpoint_file.exists()
    ) or (svc.workspace_root / "state" / "first_boot_checkpoint.json").exists()
    if not checkpoint_exists:
        return {
            "status": "rejected",
            "message": (
                "No birth checkpoint to resume. Use Start birth for a fresh run, "
                "or wipe only if you intend a clean start."
            ),
            "retryable": True,
        }

    persist_operator_resolved_terminal_freeze(
        svc,
        action="accept_champion" if champion_freeze_active_for_svc(svc) else "operator_resume",
        source="resume_checkpoint",
    )

    # Champion freeze: Continue from checkpoint = human accepts frozen champion + train.
    # Auto/silent paths (resume_stalled_stage, expand_and_retry) still reject via freeze gate.
    if champion_freeze_active_for_svc(svc):
        logger.info(
            "birth.resume.champion_freeze_accept_and_continue target_trades=%s",
            target_trades,
        )
        return accept_champion_birth(
            svc,
            target_trades=target_trades,
            start=True,
            source="resume_checkpoint",
        )

    return start_birth(
        svc,
        target_trades=target_trades,
        force=False,
        explicit_user_start=True,
        continue_training=True,
        reuse_data=True,
    )


def accept_champion_birth(
    svc: Any,
    target_trades: int | None = None,
    *,
    start: bool = True,
    source: str = "app",
) -> Dict[str, Any]:
    """Operator accepts frozen champion after swarm no-lift; clear attention and resume.

    When ``start=False``, only clears freeze flags (progress/checkpoint) so the
    operator can follow the Stage 2 re-entry checklist before explicit start.
    ``source`` is echoed to Telegram (app/cli/telegram) for remote audit.
    """
    from datetime import datetime, timezone

    from lumina_core.birth.checkpoint import (
        read_checkpoint_payload,
        write_checkpoint_payload,
    )
    from lumina_core.birth.progress import write_birth_progress
    from lumina_core.birth.terminal_freeze import (
        extract_terminal_freeze,
        mark_freeze_resolved,
    )
    from lumina_launcher.services.birth_runner_start import start_birth

    progress = dict(svc._load_progress())
    payload_pre = None
    try:
        payload_pre = read_checkpoint_payload(svc.workspace_root)
    except Exception:
        payload_pre = None
    freeze = extract_terminal_freeze(progress, payload_pre)
    if freeze:
        resolved_freeze = mark_freeze_resolved(
            freeze,
            action="accept_champion",
            resolved_by=str(source or "app"),
        )
        progress["terminal_freeze"] = resolved_freeze
    stage = str(progress.get("stage", "") or "").strip().lower()
    phase = str(progress.get("phase", "") or "").strip().lower()
    if stage in {"paused", "interrupted"}:
        stage = "training_running" if start else "paused"
        phase = "curriculum_learning" if start else (phase or "paused")
    message = (
        "Champion accepted after swarm no-lift — continuing curriculum."
        if start
        else (
            "Champion accepted after swarm no-lift — freeze cleared; "
            "start Birth explicitly after Stage 2 re-entry checklist."
        )
    )
    progress.update(
        {
            "stage": stage or ("training_running" if start else "paused"),
            "phase": phase or ("curriculum_learning" if start else "paused"),
            "swarm_rejected_no_lift": False,
            "swarm_champion_accepted": True,
            "swarm_tournament_lift_ok": False,
            "swarm_edgescore_lift_ok": False,
            "needs_attention": False,
            "attention_summary": "",
            "attention_reason_code": "",
            "attention_recommended_actions": [],
            "policy_swarm_rejected_no_lift": False,
            "policy_swarm_champion_accepted": True,
            "user_initiated_stop": False,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    try:
        write_birth_progress(
            svc.workspace_root,
            stage=str(progress.get("stage") or ("training_running" if start else "paused")),
            phase=str(progress.get("phase") or ("curriculum_learning" if start else "paused")),
            message=str(progress.get("message") or ""),
            progress_pct=float(progress.get("progress_pct", 0) or 0),
            cumulative_trades=int(progress.get("cumulative_trades", 0) or 0),
            target_trades=int(progress.get("target_trades", 0) or 0),
            ppo_steps=int(progress.get("ppo_steps", 0) or 0),
            birth_start_time=float(progress.get("birth_start_time", 0) or 0),
            swarm_rejected_no_lift=False,
            swarm_champion_accepted=True,
            swarm_tournament_lift_ok=False,
            swarm_edgescore_lift_ok=False,
            needs_attention=False,
            attention_summary="",
            attention_reason_code="",
            attention_recommended_actions=[],
            policy_swarm_rejected_no_lift=False,
            policy_swarm_champion_accepted=True,
            user_initiated_stop=False,
            curriculum_stage=str(progress.get("curriculum_stage") or ""),
            terminal_freeze=progress.get("terminal_freeze"),
        )
    except Exception as exc:
        logger.warning("birth.accept_champion.progress_write_failed: %s", exc)
    try:
        payload = read_checkpoint_payload(svc.workspace_root) or {}
        metrics = dict(payload.get("stage_metrics") or {})
        metrics["swarm_rejected_no_lift"] = False
        metrics["swarm_champion_accepted"] = True
        metrics["swarm_tournament_lift_ok"] = False
        metrics["swarm_edgescore_lift_ok"] = False
        metrics["policy_swarm_rejected_no_lift"] = False
        metrics["policy_swarm_champion_accepted"] = True
        freeze_ckpt = extract_terminal_freeze(progress, payload, metrics)
        if freeze_ckpt:
            resolved = mark_freeze_resolved(
                freeze_ckpt,
                action="accept_champion",
                resolved_by=str(source or "app"),
            )
            metrics["terminal_freeze"] = resolved
            payload["terminal_freeze"] = resolved
        payload["stage_metrics"] = metrics
        if start and str(payload.get("phase", "") or "").strip().lower() in {
            "stage_stalled",
            "paused",
            "plateau_evolution",
            "stall_remediation",
            "swarm_reject_hard_stop",
            "phoenix_cycle",
        }:
            payload["phase"] = "curriculum_learning"
        write_checkpoint_payload(svc.workspace_root, payload)
    except Exception as exc:
        logger.warning("birth.accept_champion.checkpoint_patch_failed: %s", exc)
    def _echo() -> None:
        # Telegram apply path already sends a confirmation message.
        if str(source or "").strip().lower() == "telegram":
            return
        try:
            from lumina_core.birth.champion_freeze_telegram import echo_operator_decision

            echo_operator_decision(
                svc.workspace_root,
                action="ACCEPT_NO_START" if not start else "ACCEPT",
                source=source,
                detail=message,
                started=bool(start),
            )
        except Exception as exc:
            logger.debug("birth.accept_champion.telegram_echo_failed: %s", exc)

    if not start:
        _echo()
        return {
            "status": "champion_accepted",
            "started": False,
            "message": message,
            "checkpoint_resumable": bool(svc.checkpoint_resumable()),
            "checklist": "docs/birth-stage2-certified-reentry-checklist.md",
            "source": source,
        }
    start_result = start_birth(
        svc,
        target_trades=target_trades,
        force=False,
        explicit_user_start=True,
        continue_training=True,
        reuse_data=True,
    )
    _echo()
    if isinstance(start_result, dict):
        start_result = dict(start_result)
        start_result.setdefault("source", source)
        start_result.setdefault("started", True)
    return start_result


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