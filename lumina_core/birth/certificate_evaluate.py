"""Certificate S8 polish + certified-birth completion helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.birth.birth_certificate import (
    build_certificate_from_eval,
    certificate_path,
    write_certificate,
)
from lumina_core.birth.buffer_persist import clear_buffer
from lumina_core.birth.checkpoint import clear_checkpoint
from lumina_core.birth.runway import (
    POST_BIRTH_CERTIFICATE_PHASE,
    post_birth_checkpoint_stage,
)
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.dna_handoff import register_birth_gen0_dna
from lumina_core.birth.bible_meta import update_bible_after_birth
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.stage_scorecard import build_scorecard_payload
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_evaluate")


def run_stage8_polish_and_certificate(
    pipeline: Any,
    *,
    split: Any,
    training_mode: str,
    ppo_steps_per_update: int,
    trade_budget_cap: int,
    prefer_real: bool,
    start_price: float,
) -> dict[str, Any]:
    """S8: PPO polish + unified holdout certificate eval (+ EP record on pass)."""
    _ = (ppo_steps_per_update, prefer_real, start_price)
    cfg = pipeline._host.birth_config
    cur_cfg = cfg.curriculum

    polish_scorecard = build_scorecard_payload(
        stage=post_birth_checkpoint_stage(),
        curriculum_index=5,
        stages_passed=list(pipeline._host._stages_passed),
        stage_trades=0,
        stage_wins=0,
        stage_hold_signals=0,
        stage_total_signals=0,
        constitution_violations=pipeline._host._constitution_guard.violations,
        target_trades=0,
        phase=POST_BIRTH_CERTIFICATE_PHASE,
        patterns_mined=0,
        learning_attempt=0,
        cfg=cur_cfg,
    )
    write_birth_progress(
        pipeline._host.workspace_root,
        stage="ppo_training",
        phase=POST_BIRTH_CERTIFICATE_PHASE,
        message="Post-Birth certificate (Proving Ground).",
        progress_pct=88.0,
        cumulative_trades=pipeline._host.cumulative_trades,
        target_trades=trade_budget_cap,
        ppo_steps=pipeline._host.ppo_steps,
        birth_start_time=pipeline._host.birth_start_time,
        curriculum_stage=post_birth_checkpoint_stage().value,
        runway_phase="proving_ground",
        **polish_scorecard,
    )

    from lumina_core.notifications.milestone_events import (
        curriculum_stage4_polish_passed_event,
        refinement_started_event,
    )

    pipeline._host._notify_milestone(
        curriculum_stage4_polish_passed_event(
            stages_passed=list(pipeline._host._stages_passed),
            cumulative_trades=pipeline._host.cumulative_trades,
        )
    )
    pipeline._host._notify_milestone(
        refinement_started_event(
            cumulative_trades=pipeline._host.cumulative_trades,
            ppo_steps=pipeline._host.ppo_steps,
        )
    )

    polish_steps = cur_cfg.polish_ppo_timesteps
    if len(pipeline._host.buffer) >= 256:
        pipeline._host.ppo_trainer.final_birth_polish(pipeline._host.buffer)
        pipeline._host.ppo_steps += polish_steps
    else:
        polish_batch = min(polish_steps, 10_000)
        pipeline._host.ppo_trainer.update_from_buffer(
            buffer=pipeline._host.buffer,
            timesteps=polish_batch,
            birth_phase=True,
        )
        pipeline._host.ppo_steps += polish_batch
    pipeline._host._persist_checkpoint(
        training_mode=training_mode,
        curriculum_stage=post_birth_checkpoint_stage().value,
        policy_path=str(pipeline._host.final_policy_path),
        phase=POST_BIRTH_CERTIFICATE_PHASE,
    )
    pipeline._host.ppo_trainer.save_final_birth_policy(str(pipeline._host.final_policy_path))

    oos_scorecard = build_scorecard_payload(
        stage=post_birth_checkpoint_stage(),
        curriculum_index=5,
        stages_passed=list(pipeline._host._stages_passed),
        stage_trades=0,
        stage_wins=0,
        stage_hold_signals=0,
        stage_total_signals=0,
        constitution_violations=pipeline._host._constitution_guard.violations,
        target_trades=0,
        phase="oos_evaluation",
        patterns_mined=0,
        learning_attempt=0,
        cfg=cur_cfg,
    )
    write_birth_progress(
        pipeline._host.workspace_root,
        stage="training_running",
        phase="oos_evaluation",
        message="OOS certificate evaluatie (Proving Ground)…",
        progress_pct=94.0,
        cumulative_trades=pipeline._host.cumulative_trades,
        target_trades=trade_budget_cap,
        birth_start_time=pipeline._host.birth_start_time,
        runway_phase="proving_ground",
        **oos_scorecard,
    )

    eval_result = evaluate_holdout_certificate(
        runtime=pipeline._host.runtime,
        holdout_data=split.holdout,
        policy=pipeline._host.current_policy,
        real_data_pct=pipeline._host._real_data_pct,
        holdout_days=split.holdout_days,
        constitution_violations=pipeline._host._constitution_guard.violations,
        workspace_root=pipeline._host.workspace_root,
        thresholds=cfg.certificate_thresholds,
    )

    if not eval_result.get("certificate_passed"):
        if cur_cfg.certificate_runway_enabled:
            return pipeline.fail_certificate_with_runway_checkpoint(
                eval_result=eval_result,
                training_mode=training_mode,
                trade_budget_cap=trade_budget_cap,
            )
        eval_result = pipeline.run_certificate_remediation(
            split=split,
            eval_result=eval_result,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
        )
        if isinstance(eval_result, dict) and eval_result.get("status") == "paused":
            return eval_result
        if not eval_result.get("certificate_passed"):
            return {
                "status": "certificate_failed",
                "total_trades": pipeline._host.cumulative_trades,
                "ppo_steps": pipeline._host.ppo_steps,
                "real_data_pct": pipeline._host._real_data_pct,
                "eval": eval_result,
                "training_mode": "certified",
            }

    from lumina_core.notifications.milestone_events import oos_evaluation_passed_event

    pipeline._host._notify_milestone(oos_evaluation_passed_event(eval_result=eval_result))

    return pipeline.complete_certified_birth(
        split=split,
        eval_result=eval_result,
        training_mode=training_mode,
        trade_budget_cap=trade_budget_cap,
    )



def complete_certified_birth(
    pipeline: Any,
    *,
    split: Any,
    eval_result: dict[str, Any],
    training_mode: str,
    trade_budget_cap: int,
) -> dict[str, Any]:
    # Do not append stage4_polish — Foundation resume treats it as legacy rewind.
    certificate = build_certificate_from_eval(
        workspace_root=pipeline._host.workspace_root,
        eval_result=eval_result,
        curriculum_stages_passed=pipeline._host._stages_passed,
        training_trades=pipeline._host.cumulative_trades,
        ppo_steps=pipeline._host.ppo_steps,
    )
    write_certificate(pipeline._host.workspace_root, certificate)
    clear_checkpoint(pipeline._host.workspace_root)
    clear_buffer(pipeline._host.workspace_root)
    stamp = datetime.now(timezone.utc).isoformat()
    for path in (pipeline._host.completion_flag_path, pipeline._host.legacy_completion_flag_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stamp, encoding="utf-8")

    register_birth_gen0_dna(pipeline._host.workspace_root, certificate)
    try:
        from lumina_core.evolution.meta_milestones import propose_next_milestone

        propose_next_milestone(
            pipeline._host.workspace_root,
            generation=0,
            current_winrate=float(eval_result.get("oos_winrate", eval_result.get("winrate", 0.0)) or 0.0),
            current_sharpe=float(eval_result.get("oos_sharpe", eval_result.get("sharpe", 0.0)) or 0.0),
            regime_coverage=int(eval_result.get("regimes_covered", 0) or 0),
        )
    except Exception as exc:
        logger.warning("birth.meta_milestone.gen0_failed: %s", exc)
    update_bible_after_birth(pipeline._host.workspace_root, certificate, eval_result)

    from lumina_core.birth.evolution_proof_gate import (
        EvolutionProofConfig,
        record_and_evaluate_at_certificate,
    )
    from lumina_core.notifications.milestone_events import (
        birth_certificate_issued_event,
        evolution_proof_failed_event,
        evolution_proof_passed_event,
    )

    birth_exit_wr = pipeline.resolve_birth_exit_winrate()
    if birth_exit_wr <= 0.0:
        birth_exit_wr = float(
            eval_result.get("training_winrate", eval_result.get("winrate", 0.0)) or 0.0
        )
    curriculum_cfg = pipeline._host.birth_config.curriculum
    proof_cfg = EvolutionProofConfig(
        min_trades=int(curriculum_cfg.evolution_proof_min_trades),
        min_winrate_lift=float(curriculum_cfg.evolution_proof_min_winrate_lift),
        polish_oos_winrate_min=float(curriculum_cfg.evolution_proof_polish_oos_winrate_min),
    )
    proof_result = record_and_evaluate_at_certificate(
        pipeline._host.workspace_root,
        eval_result=eval_result,
        birth_exit_winrate=birth_exit_wr,
        cfg=proof_cfg,
    )
    if proof_result.passed:
        pipeline._host._notify_milestone(
            evolution_proof_passed_event(
                oos_winrate=float(proof_result.polish_oos_winrate or 0.0),
                lift=proof_result.winrate_lift,
            )
        )
        from lumina_core.maturity.milestone_hooks import hook_evolution_proof_passed

        hook_evolution_proof_passed(
            pipeline._host.workspace_root,
            oos_winrate=float(proof_result.polish_oos_winrate or 0.0),
            lift=proof_result.winrate_lift,
        )
    else:
        pipeline._host._notify_milestone(
            evolution_proof_failed_event(reasons=list(proof_result.reasons))
        )
        from lumina_core.notifications.attention_events import evolution_proof_failed_attention_event

        pipeline._host._notify_attention(
            evolution_proof_failed_attention_event(reasons=list(proof_result.reasons))
        )

    pipeline._host._notify_milestone(
        birth_certificate_issued_event(
            eval_result=eval_result,
            stages_passed=list(pipeline._host._stages_passed),
            cumulative_trades=pipeline._host.cumulative_trades,
            ppo_steps=pipeline._host.ppo_steps,
        )
    )
    from lumina_core.maturity.milestone_hooks import hook_birth_certificate_issued

    hook_birth_certificate_issued(
        pipeline._host.workspace_root,
        cumulative_trades=pipeline._host.cumulative_trades,
        stages_passed=list(pipeline._host._stages_passed),
    )

    write_birth_progress(
        pipeline._host.workspace_root,
        stage="completed",
        phase="certificate_issued",
        message="Birth Certificate v2 issued.",
        progress_pct=100.0,
        cumulative_trades=pipeline._host.cumulative_trades,
        target_trades=trade_budget_cap,
        ppo_steps=pipeline._host.ppo_steps,
        birth_start_time=pipeline._host.birth_start_time,
        certificate_ok=True,
        oos_metrics=eval_result,
        oos_regime_breakdown=dict(eval_result.get("oos_regime_breakdown") or {}),
        curriculum_stages_passed=pipeline._host._stages_passed,
    )

    # C1 residual: optional Perfect Birth auto-declare (default off, conjunction-gated).
    auto_declare: dict[str, Any] = {"declared": False, "reason": "skipped"}
    try:
        from lumina_core.birth.perfect_birth_gate import maybe_auto_declare_perfect_birth

        auto_declare = maybe_auto_declare_perfect_birth(
            pipeline._host.workspace_root,
            curriculum_cfg=curriculum_cfg,
        )
        if auto_declare.get("declared"):
            logger.info(
                "perfect_birth.auto_declare declared=%s passed=%s",
                auto_declare.get("declared"),
                auto_declare.get("passed"),
            )
    except Exception as exc:
        logger.debug("perfect_birth.auto_declare_failed: %s", exc)
        auto_declare = {"declared": False, "reason": f"error:{exc}"}

    target_policy = pipeline._host.final_policy_path
    return {
        "status": "completed",
        "total_trades": pipeline._host.cumulative_trades,
        "ppo_steps": pipeline._host.ppo_steps,
        "real_data_pct": pipeline._host._real_data_pct,
        "policy_path": str(target_policy),
        "certificate_path": str(certificate_path(pipeline._host.workspace_root)),
        "eval": eval_result,
        "training_mode": training_mode,
        "perfect_birth_auto_declare": auto_declare,
    }
