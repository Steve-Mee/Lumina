"""Birth phase bootstrap: config, checkpoint resume, milestones, initial progress."""
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_phase_certificate_gate import certificate_fast_path_eligible
from lumina_core.birth.checkpoint import (
    can_resume_checkpoint,
    load_checkpoint_state,
    read_checkpoint_payload,
    reset_adaptation_budget_for_manual_resume,
    write_checkpoint_payload,
)
from lumina_core.birth.config import BRO_ENGINE_VERSION, resolve_effective_trade_budget
from lumina_core.birth.stage_pass_receipt import parse_stage_pass_receipts
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.birth_phase_bootstrap")


def _orch():
    from lumina_core.birth import birth_phase_orchestrator as _facade

    return _facade


def _read_birth_progress(*args, **kwargs):
    return _orch().read_birth_progress(*args, **kwargs)


def _write_birth_progress(*args, **kwargs):
    return _orch().write_birth_progress(*args, **kwargs)


def _ensure_first_boot_hardware_profile(*args, **kwargs):
    return _orch().ensure_first_boot_hardware_profile(*args, **kwargs)


def _reconstruct_checkpoint_from_progress(*args, **kwargs):
    return _orch().reconstruct_checkpoint_from_progress(*args, **kwargs)


@dataclass(slots=True)
class BirthPhaseBootstrap:
    """Shared state produced by bootstrap for later birth-phase steps."""

    cfg: Any
    training_mode: str
    ppo_steps_per_update: int
    resume: bool
    resume_policy_path: str
    checkpoint_state: dict[str, Any]
    checkpoint_phase: str
    progress_snapshot: dict[str, Any]
    allow_load: bool
    allow_minimal_synthetic: bool
    max_days: int
    prefer_real: bool
    practice_mode: bool
    force: bool


def bootstrap_birth_phase(
    host: Any,
    *,
    target_trades: int | None,
    max_real_days: int,
    prefer_real_data_only: bool,
    chunk_size: int,
    ppo_update_timesteps: int,
    force: bool,
    practice_mode: bool,
    reuse_existing_policy: bool | None,
    expand_data: bool,
) -> BirthPhaseBootstrap:
    _ = (chunk_size, force)
    cfg = host.birth_config
    raw_yaml = host._load_workspace_yaml()
    max_days = max(30, min(3650, int(max_real_days or cfg.max_real_days)))
    prefer_real = bool(prefer_real_data_only if prefer_real_data_only is not None else cfg.prefer_real_data_only)
    effective_cap, budget_source = resolve_effective_trade_budget(raw_yaml, target_trades=target_trades)
    host._trade_budget_source = budget_source
    cfg = replace(
        cfg,
        trade_budget_cap=effective_cap,
        max_real_days=max_days,
        prefer_real_data_only=prefer_real,
    )
    host.birth_config = cfg
    allow_minimal_synthetic = host._allow_minimal_synthetic_fallback()
    host._hardware_profile_payload = _ensure_first_boot_hardware_profile(host.workspace_root)
    host._apply_hardware_profile()
    logger.info(
        "birth.engine.version=%s budget_cap=%s source=%s max_real_days=%s",
        BRO_ENGINE_VERSION,
        effective_cap,
        budget_source,
        max_days,
    )
    training_mode = "practice" if practice_mode else "certified"
    ppo_steps_per_update = max(1000, int(ppo_update_timesteps or cfg.ppo_update_timesteps))
    host.birth_start_time = time.time()
    host._stages_passed = []
    host._stage_pass_receipts = []
    host._pending_stage_pass_receipt = None
    host.cumulative_trades = 0
    host.ppo_steps = 0
    host._data_manifest = {}
    host._last_raw_ticks_hash = ""
    host._remediation_attempt = 0
    host._last_checkpoint_at = 0.0
    host._active_stage_metrics = {}
    host.buffer.clear()
    host._constitution_violations_cumulative = 0
    host._constitution_guard.reset()

    progress_snapshot = _read_birth_progress(host.workspace_root)
    existing_checkpoint = load_checkpoint_state(host.workspace_root)
    if (
        not force
        and not practice_mode
        and not read_checkpoint_payload(host.workspace_root)
        and certificate_fast_path_eligible(host, progress_snapshot, existing_checkpoint)
    ):
        policy_hint = str(host.final_policy_path)
        _reconstruct_checkpoint_from_progress(
            host.workspace_root,
            progress_snapshot,
            policy_path=policy_hint if Path(policy_hint).is_file() else "",
            checkpoint=existing_checkpoint,
        )

    completion_flags = (host.completion_flag_path, host.legacy_completion_flag_path)
    resume = can_resume_checkpoint(
        host.workspace_root,
        training_mode=training_mode,
        completion_flag_paths=completion_flags,
    ) and not force
    resume_policy_path = ""
    checkpoint_state: dict[str, Any] = {}
    checkpoint_phase = ""
    if resume:
        checkpoint_state = load_checkpoint_state(host.workspace_root)
        checkpoint_phase = str(checkpoint_state.get("phase", "") or "")
        host.cumulative_trades = int(checkpoint_state.get("cumulative_trades", 0) or 0)
        host.ppo_steps = int(checkpoint_state.get("ppo_steps", 0) or 0)
        host._stages_passed = list(checkpoint_state.get("stages_passed") or [])
        host._stage_pass_receipts = parse_stage_pass_receipts(
            checkpoint_state.get("stage_pass_receipts")
        )
        host._apply_curriculum_integrity_audit(training_mode=training_mode)
        resume_policy_path = str(checkpoint_state.get("policy_path", "") or "")
        host._data_manifest = dict(checkpoint_state.get("data_manifest") or {})
        host._remediation_attempt = max(
            0, int(checkpoint_state.get("remediation_attempt", 0) or 0)
        )
        host._active_stage_metrics = dict(checkpoint_state.get("stage_metrics") or {})
        host.buffer.clear()
        host._restore_buffer_from_checkpoint(checkpoint_state)
        if checkpoint_phase.strip().lower() == "stage_stalled":
            reset_adaptation_budget_for_manual_resume(host.workspace_root)
            checkpoint_state = load_checkpoint_state(host.workspace_root)
            host._active_stage_metrics = dict(checkpoint_state.get("stage_metrics") or {})
        if expand_data and resume:
            metrics = dict(host._active_stage_metrics)
            metrics["pending_data_expand"] = True
            host._active_stage_metrics = metrics
            payload = read_checkpoint_payload(host.workspace_root)
            if payload:
                payload["stage_metrics"] = metrics
                write_checkpoint_payload(host.workspace_root, payload)

    allow_load = resume if reuse_existing_policy is None else bool(reuse_existing_policy)
    if resume_policy_path and Path(resume_policy_path).is_file():
        allow_load = True

    try:
        from lumina_core.notifications.milestone_notifier import (
            get_milestone_notifier,
            seed_milestones_from_birth_state,
        )

        if resume:
            resume_metrics = dict(checkpoint_state.get("stage_metrics") or {})
            proof_passed: bool | None = None
            try:
                from lumina_core.birth.evolution_proof_gate import (
                    load_evolution_proof_record,
                )

                proof_record = load_evolution_proof_record(host.workspace_root)
                if proof_record:
                    proof_passed = bool(proof_record.get("passed"))
            except Exception:
                proof_passed = None
            seed_milestones_from_birth_state(
                stages_passed=list(host._stages_passed),
                phase=checkpoint_phase or str(progress_snapshot.get("phase", "") or ""),
                training_mode=training_mode,
                workspace_root=host.workspace_root,
                plateau_active=bool(resume_metrics.get("plateau_active")),
                evolution_step=int(resume_metrics.get("plateau_evolution_step", 0) or 0),
                hold_trap_detected=bool(progress_snapshot.get("hold_trap_detected")),
                evolution_proof_passed=proof_passed,
            )
        else:
            get_milestone_notifier(workspace_root=host.workspace_root).reset_notified()
    except Exception as exc:
        logger.warning("birth.milestone_seed_failed: %s", exc)

    resume_message = "Birth Phase v2 gestart."
    if resume:
        ckpt_stage = str(checkpoint_state.get("curriculum_stage", "") or "curriculum").strip()
        resume_message = (
            f"Checkpoint hervat — {ckpt_stage}, {host.ppo_steps:,} PPO steps "
            f"(curriculum gaat verder)."
        )
    resume_progress_extra: dict[str, Any] = {}
    if resume:
        resume_progress_extra = {
            "needs_attention": False,
            "attention_summary": "",
            "attention_reason_code": "",
            "attention_recommended_actions": [],
            "user_initiated_stop": False,
        }
    _write_birth_progress(
        host.workspace_root,
        stage="detected",
        phase="detected",
        message=resume_message,
        progress_pct=5.0,
        cumulative_trades=host.cumulative_trades if resume else 0,
        target_trades=cfg.trade_budget_cap,
        ppo_steps=host.ppo_steps if resume else 0,
        birth_start_time=host.birth_start_time,
        training_mode=training_mode,
        resumed=resume,
        **resume_progress_extra,
        **host._budget_progress_fields(),
    )

    from lumina_core.notifications.milestone_events import birth_started_event

    host._notify_milestone(
        birth_started_event(
            training_mode=training_mode,
            trade_budget=cfg.trade_budget_cap,
            resumed=resume,
        )
    )
    from lumina_core.maturity.milestone_hooks import hook_birth_started

    hook_birth_started(
        host.workspace_root,
        training_mode=training_mode,
        trade_budget=cfg.trade_budget_cap,
        resumed=resume,
    )
    wr_threshold = float(cfg.curriculum.stage1_winrate_pass_threshold)
    wr_recommended = float(cfg.curriculum.stage1_winrate_recommended)
    if wr_threshold < wr_recommended - 0.001:
        try:
            from lumina_core.notifications.milestone_events import birth_gate_warning_event

            host._notify_milestone(
                birth_gate_warning_event(threshold=wr_threshold, recommended=wr_recommended)
            )
        except Exception as exc:
            logger.debug("birth.milestone_gate_warning_failed: %s", exc)

    return BirthPhaseBootstrap(
        cfg=cfg,
        training_mode=training_mode,
        ppo_steps_per_update=ppo_steps_per_update,
        resume=resume,
        resume_policy_path=resume_policy_path,
        checkpoint_state=checkpoint_state,
        checkpoint_phase=checkpoint_phase,
        progress_snapshot=progress_snapshot,
        allow_load=allow_load,
        allow_minimal_synthetic=allow_minimal_synthetic,
        max_days=max_days,
        prefer_real=prefer_real,
        practice_mode=practice_mode,
        force=force,
    )
