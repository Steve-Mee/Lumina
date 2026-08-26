"""Certificate runway stages + fail helpers for birth certificate pipeline."""
from __future__ import annotations


from typing import Any

from lumina_core.birth.curriculum import (
    CurriculumStage,
    ordered_runway_stages,
    stage_trade_target,
)
from lumina_core.birth.progress import read_birth_progress, write_birth_progress
from lumina_core.birth.runway import (
    POST_BIRTH_CERTIFICATE_PHASE,
    micro_oos_evolution_proof_passed,
    micro_oos_probe,
    micro_oos_sanity_passed,
    runway_stage_index,
    ticks_for_runway_stage,
)
from lumina_core.birth.stage_pass_receipt import receipt_for_stage
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_runway")


def resolve_birth_exit_winrate(pipeline) -> float:
    receipt = receipt_for_stage(pipeline._host._stage_pass_receipts, CurriculumStage.STAGE3_MIXED.value)
    if receipt is not None:
        return float(receipt.winrate)
    progress = read_birth_progress(pipeline._host.workspace_root)
    raw = progress.get("birth_exit_winrate")
    if isinstance(raw, (int, float)):
        return float(raw)
    return 0.0

def resolve_baseline_oos_winrate(pipeline, *, checkpoint_state: dict[str, Any] | None = None) -> float:
    ckpt = checkpoint_state or {}
    ckpt_oos = ckpt.get("oos_metrics")
    if isinstance(ckpt_oos, dict):
        wr = ckpt_oos.get("oos_winrate")
        if isinstance(wr, (int, float)):
            return float(wr)
    progress = read_birth_progress(pipeline._host.workspace_root)
    prog_oos = progress.get("oos_metrics")
    if isinstance(prog_oos, dict):
        wr = prog_oos.get("oos_winrate")
        if isinstance(wr, (int, float)):
            return float(wr)
    return 0.0

def bootstrap_runway_stage5(pipeline, *, train_ticks: list[dict[str, Any]]) -> None:
    """Post-Birth cert runway only. Never seed S1-trend oracle into a later buffer."""
    _ = (pipeline, train_ticks)
    logger.info("birth.runway.s5_oracle_seed_forbidden_under_foundation")


def run_certificate_runway_stages(
    pipeline,
    *,
    split: Any,
    validation_ticks: list[dict[str, Any]],
    train_core_ticks: list[dict[str, Any]],
    training_mode: str,
    ppo_steps_per_update: int,
    trade_budget_cap: int,
    prefer_real: bool,
    start_price: float,
    baseline_oos_winrate: float,
    birth_exit_winrate: float,
) -> dict[str, Any] | None:
    """MVR runway S5→S6→S7 with micro-OOS gates (post-S6 sanity, post-S7 EP)."""
    cur_cfg = pipeline._host.birth_config.curriculum
    holdout_ticks = list(split.holdout)
    runway_stages = ordered_runway_stages()
    max_micro_trades = int(getattr(cur_cfg, "runway_micro_oos_max_trades", 800))

    write_birth_progress(
        pipeline._host.workspace_root,
        stage="training_running",
        phase=POST_BIRTH_CERTIFICATE_PHASE,
        message="Post-Birth certificate (Proving Ground): profit → risk → generalize",
        progress_pct=80.0,
        cumulative_trades=pipeline._host.cumulative_trades,
        target_trades=trade_budget_cap,
        ppo_steps=pipeline._host.ppo_steps,
        birth_start_time=pipeline._host.birth_start_time,
        runway_phase="PG1",
        birth_exit_winrate=birth_exit_winrate,
    )

    for runway_index, stage in enumerate(runway_stages):
        if pipeline._host._stop_requested():
            pipeline._host._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                phase="paused",
            )
            return pipeline._host._paused_result()

        if stage.value in pipeline._host._stages_passed:
            if pipeline._host._verify_stage_pass_receipt_for_skip(stage, training_mode=training_mode):
                continue

        if stage == CurriculumStage.STAGE5_PROFIT_VAL:
            pipeline.bootstrap_runway_stage5(train_ticks=train_core_ticks)

        stage_ticks = ticks_for_runway_stage(
            stage,
            train_ticks=train_core_ticks,
            holdout_ticks=holdout_ticks,
            validation_ticks=validation_ticks,
        )
        if not stage_ticks:
            logger.error("birth.runway.empty_filter_fail_closed stage=%s", stage.value)
            return {
                "status": "stage_failed",
                "failure_reason": f"empty_runway_ticks:{stage.value}",
                "total_trades": pipeline._host.cumulative_trades,
                "training_mode": training_mode,
            }
        target = stage_trade_target(stage, cur_cfg)
        pipeline._host._accumulate_constitution_violations_before_stage_reset()

        stage_progress_pct = 80.0 + (runway_index / max(1, len(runway_stages))) * 8.0
        write_birth_progress(
            pipeline._host.workspace_root,
            stage="training_running",
            phase=POST_BIRTH_CERTIFICATE_PHASE,
            message=f"Post-Birth certificate (Proving Ground) {stage.value}: training…",
            progress_pct=stage_progress_pct,
            cumulative_trades=pipeline._host.cumulative_trades,
            target_trades=trade_budget_cap,
            ppo_steps=pipeline._host.ppo_steps,
            birth_start_time=pipeline._host.birth_start_time,
            curriculum_stage=stage.value,
            runway_phase=f"PG{runway_stage_index(stage)}",
            birth_exit_winrate=birth_exit_winrate,
        )

        micro_probe: dict[str, Any] | None = None
        while True:
            stage_error = pipeline._host._run_stage_research_loop(
                stage=stage,
                stage_index=runway_index + 4,
                stage_ticks=stage_ticks,
                train_ticks=list(train_core_ticks),
                holdout_ticks=holdout_ticks,
                target=target,
                stage_progress_pct=stage_progress_pct,
                training_mode=training_mode,
                ppo_steps_per_update=ppo_steps_per_update,
                polish_ppo_timesteps=max(1000, int(cur_cfg.polish_ppo_timesteps)),
                trade_budget_cap=trade_budget_cap,
                prefer_real=prefer_real,
                start_price=start_price,
            )
            if stage_error is not None:
                return stage_error

            if stage == CurriculumStage.STAGE6_RISK_DISCIPLINE:
                micro_probe = micro_oos_probe(
                    runtime=pipeline._host.runtime,
                    holdout_data=holdout_ticks,
                    policy=pipeline._host.current_policy,
                    real_data_pct=pipeline._host._real_data_pct,
                    holdout_days=split.holdout_days,
                    constitution_violations=pipeline._host._constitution_guard.violations,
                    workspace_root=pipeline._host.workspace_root,
                    thresholds=pipeline._host.birth_config.certificate_thresholds,
                    max_trades=max_micro_trades,
                )
                ok, probe_msg = micro_oos_sanity_passed(
                    micro_probe,
                    cfg=cur_cfg,
                    baseline_oos_winrate=baseline_oos_winrate,
                )
                write_birth_progress(
                    pipeline._host.workspace_root,
                    stage="training_running",
                    phase="runway_micro_oos",
                    message=f"Post-S6 micro-OOS: {probe_msg}",
                    progress_pct=stage_progress_pct + 1.0,
                    cumulative_trades=pipeline._host.cumulative_trades,
                    target_trades=trade_budget_cap,
                    micro_oos_probe=micro_probe,
                    runway_phase="PG2_probe",
                )
                if not ok:
                    logger.info("birth.runway.s6_sanity_retry reason=%s", probe_msg)
                    continue

            if stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
                micro_probe = micro_oos_probe(
                    runtime=pipeline._host.runtime,
                    holdout_data=holdout_ticks,
                    policy=pipeline._host.current_policy,
                    real_data_pct=pipeline._host._real_data_pct,
                    holdout_days=split.holdout_days,
                    constitution_violations=pipeline._host._constitution_guard.violations,
                    workspace_root=pipeline._host.workspace_root,
                    thresholds=pipeline._host.birth_config.certificate_thresholds,
                    max_trades=max_micro_trades,
                )
                ok, probe_msg = micro_oos_evolution_proof_passed(
                    micro_probe,
                    birth_exit_winrate=birth_exit_winrate,
                    cfg=cur_cfg,
                )
                write_birth_progress(
                    pipeline._host.workspace_root,
                    stage="training_running",
                    phase="runway_micro_oos",
                    message=f"Post-S7 EP probe: {probe_msg}",
                    progress_pct=stage_progress_pct + 1.5,
                    cumulative_trades=pipeline._host.cumulative_trades,
                    target_trades=trade_budget_cap,
                    micro_oos_probe=micro_probe,
                    runway_phase="PG3_ep_probe",
                )
                if not ok:
                    logger.info("birth.runway.s7_ep_retry reason=%s", probe_msg)
                    continue

            break

        pipeline._host._commit_stage_graduation(
            stage,
            training_mode=training_mode,
            curriculum_stage=stage.value,
            policy_path=str(pipeline._host.final_policy_path),
            phase="runway_stage_complete",
        )

    return None

def fail_certificate_with_runway_checkpoint(
    pipeline,
    *,
    eval_result: dict[str, Any],
    training_mode: str,
    trade_budget_cap: int,
) -> dict[str, Any]:
    """Persist cert failure for runway resume (skip generic remediation when MVR enabled)."""
    current_eval = dict(eval_result)
    write_birth_progress(
        pipeline._host.workspace_root,
        stage="failed",
        phase="certificate_failed",
        message="Birth Certificate v2 thresholds not met — resume enters runway S5.",
        progress_pct=100.0,
        cumulative_trades=pipeline._host.cumulative_trades,
        target_trades=trade_budget_cap,
        birth_start_time=pipeline._host.birth_start_time,
        oos_metrics=current_eval,
        oos_regime_breakdown=dict(current_eval.get("oos_regime_breakdown") or {}),
        failure_reasons=list(current_eval.get("failure_reasons") or []),
        stages_passed=list(pipeline._host._stages_passed),
        data_manifest=dict(pipeline._host._data_manifest),
        needs_attention=True,
        retryable=True,
        birth_exit_winrate=pipeline.resolve_birth_exit_winrate(),
    )
    try:
        from lumina_core.notifications.attention_events import birth_certificate_failed_event
        from lumina_core.notifications.attention_notifier import notify_attention

        notify_attention(
            birth_certificate_failed_event(
                failure_reasons=list(current_eval.get("failure_reasons") or []),
            ),
            workspace_root=pipeline._host.workspace_root,
        )
    except Exception as exc:
        logger.warning("birth.cert_attention_failed: %s", exc)
    pipeline._host._persist_checkpoint(
        training_mode=training_mode,
        curriculum_stage=CurriculumStage.STAGE5_PROFIT_VAL.value,
        phase="certificate_failed",
        oos_metrics=dict(current_eval),
    )
    return {
        "status": "certificate_failed",
        "total_trades": pipeline._host.cumulative_trades,
        "ppo_steps": pipeline._host.ppo_steps,
        "real_data_pct": pipeline._host._real_data_pct,
        "eval": current_eval,
        "training_mode": "certified",
    }
