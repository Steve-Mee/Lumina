"""Birth phase top-level orchestration (extracted from engine)."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.buffer_persist import clear_buffer
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.checkpoint import (
    can_resume_checkpoint,
    clear_checkpoint,
    load_checkpoint_state,
    read_checkpoint_payload,
    reset_adaptation_budget_for_manual_resume,
    write_checkpoint_payload,
)
from lumina_core.birth.config import BRO_ENGINE_VERSION, resolve_effective_trade_budget
from lumina_core.birth.curriculum import (
    CurriculumStage,
    filter_ticks_for_stage,
    ordered_stages,
    stage_trade_target,
)
from lumina_core.birth.progress import read_birth_progress, write_birth_progress
from lumina_core.birth.purged_split import purged_validation_split
from lumina_core.birth.remediation import (
    reconstruct_checkpoint_from_progress,
    should_fast_path_remediation_from_state,
)
from lumina_core.birth.runway import micro_oos_probe
from lumina_core.birth.stage_pass_receipt import parse_stage_pass_receipts
from lumina_core.birth.stage_scorecard import build_scorecard_payload, compute_regime_distribution
from lumina_core.first_boot_progress import ensure_first_boot_hardware_profile
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.birth_phase_orchestrator")


def run_birth_phase(
    host: Any,
    *,
    target_trades: int | None = None,
    max_real_days: int = 365,
    prefer_real_data_only: bool = True,
    chunk_size: int = 50_000,
    ppo_update_timesteps: int = 25_000,
    force: bool = False,
    practice_mode: bool = False,
    reuse_existing_policy: bool | None = None,
    reuse_data_manifest: bool = False,
    expand_data: bool = False,
) -> dict[str, Any]:
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
    host._hardware_profile_payload = ensure_first_boot_hardware_profile(host.workspace_root)
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

    progress_snapshot = read_birth_progress(host.workspace_root)
    existing_checkpoint = load_checkpoint_state(host.workspace_root)
    if (
        not force
        and not practice_mode
        and not read_checkpoint_payload(host.workspace_root)
        and should_fast_path_remediation_from_state(progress_snapshot, existing_checkpoint)
    ):
        policy_hint = str(host.final_policy_path)
        reconstruct_checkpoint_from_progress(
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
    write_birth_progress(
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

    data_prep = host._data_pipeline().prepare_ticks_and_split(
        cfg=cfg,
        max_days=max_days,
        prefer_real=prefer_real,
        practice_mode=practice_mode,
        allow_minimal_synthetic=allow_minimal_synthetic,
        resume=resume,
        training_mode=training_mode,
    )
    if data_prep.early_return is not None:
        return data_prep.early_return
    ticks = data_prep.ticks
    split = data_prep.split
    resume_cache_decision = data_prep.resume_cache_decision
    resume_skip_load = data_prep.resume_skip_load
    _ = data_prep.resume_reenrich_only

    preflight_result = host._ensure_holdout_preflight(
        ticks=ticks,
        split=split,
        max_days=max_days,
        prefer_real=prefer_real,
        start_price=float(ticks[-1].get("last", 5000.0) or 5000.0) if ticks else 5000.0,
        training_mode=training_mode,
        reuse_manifest=bool(resume and host._data_manifest),
        saved_manifest=host._data_manifest if resume else None,
    )
    if isinstance(preflight_result, dict):
        return preflight_result
    ticks, split, host._data_manifest = preflight_result

    write_birth_progress(
        host.workspace_root,
        stage="historical_loaded",
        phase="ticks_ready",
        message=(
            f"Data geladen: {len(ticks):,} ticks, holdout {split.holdout_days} dagen, "
            f"regimes {','.join(host._data_manifest.get('holdout_regimes', []))}."
        ),
        progress_pct=25.0,
        cumulative_trades=host.cumulative_trades if resume else 0,
        target_trades=cfg.trade_budget_cap,
        birth_start_time=host.birth_start_time,
        ppo_steps=host.ppo_steps if resume else 0,
        actual_real_days_loaded=max(1, len(ticks) // 450),
        real_data_pct=host._real_data_pct,
        preflight_report={
            "ok": True,
            "holdout_regimes": host._data_manifest.get("holdout_regimes", []),
        },
        data_manifest=host._data_manifest,
        regime_distribution=compute_regime_distribution(ticks),
        resume_cache_tier=(
            resume_cache_decision.tier.value
            if resume_cache_decision and resume_skip_load
            else ""
        ),
    )

    from lumina_core.notifications.milestone_events import (
        history_loaded_event,
        regime_map_ready_event,
    )

    host._notify_milestone(
        history_loaded_event(
            tick_count=len(ticks),
            real_data_pct=host._real_data_pct,
            max_real_days=max_days,
        )
    )
    host._notify_milestone(
        regime_map_ready_event(
            tick_count=len(ticks),
            train_bars=len(split.train),
            holdout_bars=len(split.holdout),
            holdout_days=int(split.holdout_days),
            real_data_pct=host._real_data_pct,
        )
    )

    host._write_data_prep_progress(
        phase="policy_init",
        message="Birth policy initialiseren…",
        progress_pct=26.0,
        training_mode=training_mode,
    )
    host.current_policy = host._create_birth_policy(
        allow_load_existing=allow_load and resume,
        policy_path=resume_policy_path or None,
    )
    start_price = float(ticks[-1].get("last", 5000.0) or 5000.0) if ticks else 5000.0

    if resume and not checkpoint_phase:
        progress_phase = str(progress_snapshot.get("phase", "") or "").strip().lower()
        if progress_phase in {"certificate_failed", "certificate_remediation"}:
            checkpoint_phase = progress_phase
            if not host._stages_passed:
                host._stages_passed = list(progress_snapshot.get("stages_passed") or [])
            host._remediation_attempt = max(
                host._remediation_attempt,
                int(progress_snapshot.get("remediation_attempt", 0) or 0),
            )
            if not host._data_manifest:
                manifest = progress_snapshot.get("data_manifest")
                if isinstance(manifest, dict):
                    host._data_manifest = dict(manifest)

    if (
        not practice_mode
        and resume
        and should_fast_path_remediation_from_state(progress_snapshot, checkpoint_state)
    ):
        if cfg.curriculum.certificate_runway_enabled:
            write_birth_progress(
                host.workspace_root,
                stage="training_running",
                phase="runway_stage",
                message="Resuming certificate runway from checkpoint (S5→S8).",
                progress_pct=80.0,
                cumulative_trades=host.cumulative_trades,
                target_trades=cfg.trade_budget_cap,
                ppo_steps=host.ppo_steps,
                birth_start_time=host.birth_start_time,
                fast_path_resume=True,
            )
            val_split = purged_validation_split(
                list(split.train),
                validation_pct=float(cfg.curriculum.certificate_runway_validation_pct),
            )
            birth_exit_wr = host._resolve_birth_exit_winrate()
            baseline_oos_wr = host._resolve_baseline_oos_winrate(
                checkpoint_state=checkpoint_state
            )
            runway_error = host._run_certificate_runway_stages(
                split=split,
                validation_ticks=list(val_split.validation),
                train_core_ticks=list(val_split.train_core),
                training_mode=training_mode,
                ppo_steps_per_update=ppo_steps_per_update,
                trade_budget_cap=cfg.trade_budget_cap,
                prefer_real=prefer_real,
                start_price=start_price,
                baseline_oos_winrate=baseline_oos_wr,
                birth_exit_winrate=birth_exit_wr,
            )
            if runway_error is not None:
                return runway_error
            return host._run_stage8_polish_and_certificate(
                split=split,
                training_mode=training_mode,
                ppo_steps_per_update=ppo_steps_per_update,
                trade_budget_cap=cfg.trade_budget_cap,
                prefer_real=prefer_real,
                start_price=start_price,
            )

        write_birth_progress(
            host.workspace_root,
            stage="training_running",
            phase="certificate_remediation",
            message="Resuming certificate remediation from checkpoint (fast path).",
            progress_pct=93.0,
            cumulative_trades=host.cumulative_trades,
            target_trades=cfg.trade_budget_cap,
            ppo_steps=host.ppo_steps,
            birth_start_time=host.birth_start_time,
            fast_path_resume=True,
        )
        prior_progress = read_birth_progress(host.workspace_root)
        prior_eval = prior_progress.get("oos_metrics")
        if not isinstance(prior_eval, dict) or not prior_eval.get("failure_reasons"):
            prior_eval = evaluate_holdout_certificate(
                runtime=host.runtime,
                holdout_data=split.holdout,
                policy=host.current_policy,
                real_data_pct=host._real_data_pct,
                holdout_days=split.holdout_days,
                constitution_violations=host._constitution_guard.violations,
                workspace_root=host.workspace_root,
                thresholds=cfg.certificate_thresholds,
            )
        eval_result = host._run_certificate_remediation(
            split=split,
            eval_result=dict(prior_eval),
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=cfg.trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
        )
        if isinstance(eval_result, dict) and eval_result.get("status") == "paused":
            return eval_result
        if not eval_result.get("certificate_passed"):
            return {
                "status": "certificate_failed",
                "total_trades": host.cumulative_trades,
                "ppo_steps": host.ppo_steps,
                "real_data_pct": host._real_data_pct,
                "eval": eval_result,
                "training_mode": "certified",
            }
        from lumina_core.notifications.milestone_events import oos_evaluation_passed_event

        host._notify_milestone(oos_evaluation_passed_event(eval_result=eval_result))

        return host._complete_certified_birth(
            split=split,
            eval_result=eval_result,
            training_mode=training_mode,
            trade_budget_cap=cfg.trade_budget_cap,
        )

    total_stages = len(ordered_stages())
    stage_index = 0
    curriculum_timesteps = max(1000, int(cfg.curriculum.curriculum_ppo_timesteps))

    write_birth_progress(
        host.workspace_root,
        stage="training_running",
        phase="curriculum_stage",
        message="Curriculum training starten…",
        progress_pct=27.0,
        cumulative_trades=0,
        target_trades=cfg.trade_budget_cap,
        birth_start_time=host.birth_start_time,
        training_mode=training_mode,
    )

    for stage in ordered_stages():
        if host._stop_requested():
            policy_hint = str(host.final_policy_path)
            if host.final_policy_path.is_file():
                policy_hint = str(host.final_policy_path)
            host._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=policy_hint,
                phase="paused",
            )
            return host._paused_result()

        if stage == CurriculumStage.STAGE4_POLISH:
            break

        if stage.value in host._stages_passed:
            if host._verify_stage_pass_receipt_for_skip(stage, training_mode=training_mode):
                stage_index += 1
                continue

        stage_ticks = filter_ticks_for_stage(stage, split.train)
        if not stage_ticks:
            stage_ticks = list(split.train)
        target = stage_trade_target(stage, cfg.curriculum)
        host._accumulate_constitution_violations_before_stage_reset()

        stage_progress_pct = 27.0 + (stage_index / total_stages) * 53.0
        # Note: direct path still supported. Preferred long-term: host.start_event_driven_curriculum()
        # which uses the thin CurriculumOrchestrator + dedicated handlers over central EventBus.
        stage_error = host._run_stage_research_loop(
            stage=stage,
            stage_index=stage_index,
            stage_ticks=stage_ticks,
            train_ticks=list(split.train),
            holdout_ticks=list(split.holdout),
            target=target,
            stage_progress_pct=stage_progress_pct,
            training_mode=training_mode,
            ppo_steps_per_update=curriculum_timesteps,
            polish_ppo_timesteps=max(1000, int(cfg.curriculum.polish_ppo_timesteps)),
            trade_budget_cap=cfg.trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
        )
        if stage_error is not None:
            return stage_error

        host._commit_stage_graduation(
            stage,
            training_mode=training_mode,
            curriculum_stage=stage.value,
            policy_path=str(host.final_policy_path),
            phase="curriculum_stage_complete",
        )
        stage_index += 1

    val_split = purged_validation_split(
        list(split.train),
        validation_pct=float(cfg.curriculum.certificate_runway_validation_pct),
    )
    birth_exit_wr = host._resolve_birth_exit_winrate()
    baseline_oos_wr = host._resolve_baseline_oos_winrate(checkpoint_state=checkpoint_state)

    if cfg.curriculum.certificate_runway_enabled and not practice_mode:
        if baseline_oos_wr <= 0.0:
            baseline_probe = micro_oos_probe(
                runtime=host.runtime,
                holdout_data=list(split.holdout),
                policy=host.current_policy,
                real_data_pct=host._real_data_pct,
                holdout_days=split.holdout_days,
                constitution_violations=host._constitution_guard.violations,
                workspace_root=host.workspace_root,
                thresholds=cfg.certificate_thresholds,
                max_trades=int(cfg.curriculum.runway_micro_oos_max_trades),
            )
            baseline_oos_wr = float(baseline_probe.get("oos_winrate", 0.0) or 0.0)
            write_birth_progress(
                host.workspace_root,
                stage="training_running",
                phase="runway_micro_oos",
                message=(
                    f"Pre-runway micro-OOS baseline WR {baseline_oos_wr:.1%} "
                    f"(birth exit {birth_exit_wr:.1%})"
                ),
                progress_pct=79.0,
                cumulative_trades=host.cumulative_trades,
                target_trades=cfg.trade_budget_cap,
                micro_oos_probe=baseline_probe,
                birth_exit_winrate=birth_exit_wr,
            )
        runway_error = host._run_certificate_runway_stages(
            split=split,
            validation_ticks=list(val_split.validation),
            train_core_ticks=list(val_split.train_core),
            training_mode=training_mode,
            ppo_steps_per_update=curriculum_timesteps,
            trade_budget_cap=cfg.trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
            baseline_oos_winrate=baseline_oos_wr,
            birth_exit_winrate=birth_exit_wr,
        )
        if runway_error is not None:
            return runway_error

    if practice_mode:
        polish_scorecard = build_scorecard_payload(
            stage=CurriculumStage.STAGE4_POLISH,
            curriculum_index=4,
            stages_passed=list(host._stages_passed),
            stage_trades=0,
            stage_wins=0,
            stage_hold_signals=0,
            stage_total_signals=0,
            constitution_violations=host._constitution_guard.violations,
            target_trades=0,
            phase="ppo_polish",
            patterns_mined=0,
            learning_attempt=0,
            cfg=cfg.curriculum,
        )
        write_birth_progress(
            host.workspace_root,
            stage="ppo_training",
            phase="ppo_polish",
            message="Final PPO polish (practice).",
            progress_pct=85.0,
            cumulative_trades=host.cumulative_trades,
            target_trades=cfg.trade_budget_cap,
            ppo_steps=host.ppo_steps,
            birth_start_time=host.birth_start_time,
            curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
            **polish_scorecard,
        )
        polish_steps = cfg.curriculum.polish_ppo_timesteps
        if len(host.buffer) >= 256:
            host.ppo_trainer.final_birth_polish(host.buffer)
            host.ppo_steps += polish_steps
        else:
            polish_batch = min(polish_steps, 10_000)
            host.ppo_trainer.update_from_buffer(
                buffer=host.buffer,
                timesteps=polish_batch,
                birth_phase=True,
            )
            host.ppo_steps += polish_batch
        target_policy = host.practice_policy_path
        host.ppo_trainer.save_final_birth_policy(str(target_policy))
        host.practice_completed_flag_path.write_text(
            datetime.now(timezone.utc).isoformat(), encoding="utf-8"
        )
        clear_checkpoint(host.workspace_root)
        clear_buffer(host.workspace_root)
        write_birth_progress(
            host.workspace_root,
            stage="practice_completed",
            phase="practice_completed",
            message="Practice Birth voltooid (geen certificate).",
            progress_pct=100.0,
            cumulative_trades=host.cumulative_trades,
            target_trades=cfg.trade_budget_cap,
            birth_start_time=host.birth_start_time,
        )
        from lumina_core.notifications.milestone_events import practice_birth_completed_event

        host._notify_milestone(
            practice_birth_completed_event(
                cumulative_trades=host.cumulative_trades,
                ppo_steps=host.ppo_steps,
                policy_path=str(target_policy),
            )
        )
        return {
            "status": "practice_completed",
            "total_trades": host.cumulative_trades,
            "ppo_steps": host.ppo_steps,
            "real_data_pct": host._real_data_pct,
            "policy_path": str(target_policy),
            "training_mode": "practice",
        }

    return host._run_stage8_polish_and_certificate(
        split=split,
        training_mode=training_mode,
        ppo_steps_per_update=ppo_steps_per_update,
        trade_budget_cap=cfg.trade_budget_cap,
        prefer_real=prefer_real,
        start_price=start_price,
    )
