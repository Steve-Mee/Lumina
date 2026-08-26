"""Certificate remediation loop for birth certificate pipeline."""
from __future__ import annotations

from lumina_core.birth.certificate_patch_bridge import cp_attr

from typing import Any

from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.runway import POST_BIRTH_CERTIFICATE_PHASE, post_birth_checkpoint_stage
from lumina_core.birth.data_expansion import clamp_expansion_steps, expand_birth_data
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.remediation import (
    RemediationAction,
    filter_train_ticks_for_holdout_profile,
    select_regime_diverse_train_ticks,
    select_remediation_plan,
)
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_remediation")


def run_certificate_remediation(
    pipeline,
    *,
    split: Any,
    eval_result: dict[str, Any],
    training_mode: str,
    ppo_steps_per_update: int,
    trade_budget_cap: int,
    prefer_real: bool,
    start_price: float,
) -> dict[str, Any]:
    cur_cfg = pipeline._host.birth_config.curriculum
    news_cfg = pipeline._host.birth_config.news
    max_attempts = max(1, int(cur_cfg.max_certificate_remediation_attempts))
    if cur_cfg.autonomous_recovery_enabled:
        max_attempts = max(max_attempts, 99)
    curriculum_timesteps = max(1000, int(cur_cfg.curriculum_ppo_timesteps))
    polish_timesteps = max(1000, int(cur_cfg.polish_ppo_timesteps))
    current_eval = dict(eval_result)
    remediation_expansion_step = max(
        0, int(pipeline._host._data_manifest.get("remediation_expansion_step", 0) or 0)
    )
    holdout_data = list(split.holdout)

    for attempt in range(1, max_attempts + 1):
        pipeline._host._remediation_attempt = attempt
        reasons = list(current_eval.get("failure_reasons") or [])
        plan = select_remediation_plan(
            reasons,
            attempt=attempt,
            curriculum_ppo_timesteps=curriculum_timesteps,
            polish_ppo_timesteps=polish_timesteps,
            rollout_chunk_trades=cur_cfg.rollout_chunk_trades,
        )
        write_birth_progress(
            pipeline._host.workspace_root,
            stage="training_running",
            phase="certificate_remediation",
            message=(
                f"Certificate remediation {attempt}/{max_attempts} "
                f"[{plan.label}]: {', '.join(reasons) or 'diagnose'}"
            ),
            progress_pct=min(99.0, 94.0 + (attempt / max_attempts) * 4.0),
            cumulative_trades=pipeline._host.cumulative_trades,
            target_trades=trade_budget_cap,
            ppo_steps=pipeline._host.ppo_steps,
            birth_start_time=pipeline._host.birth_start_time,
            remediation_attempt=attempt,
            remediation_max=max_attempts,
            remediation_action=plan.action.value,
            oos_metrics=current_eval,
            oos_regime_breakdown=dict(current_eval.get("oos_regime_breakdown") or {}),
            failure_reasons=reasons,
            quality_score=float(pipeline._host._data_manifest.get("quality_score", 0.0) or 0.0),
        )
        if pipeline._host._stop_requested():
            pipeline._host._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=post_birth_checkpoint_stage().value,
                phase=POST_BIRTH_CERTIFICATE_PHASE,
            )
            return pipeline._host._paused_result()

        active_train = list(split.train)
        if plan.expand_data:
            rem_max_days = int(pipeline._host.birth_config.max_real_days)
            expanded = cp_attr("expand_birth_data", expand_birth_data)(
                market_data_service=pipeline._host.market_data_service,
                runtime=pipeline._host.runtime,
                current_step=remediation_expansion_step + 1,
                expansion_steps=clamp_expansion_steps(
                    list(cur_cfg.data_expansion_steps),
                    max_real_days=rem_max_days,
                ),
                holdout_pct=pipeline._host.birth_config.holdout_pct,
                enrich_news_fn=lambda rows: cp_attr("enrich_ticks_with_news", enrich_ticks_with_news)(
                    rows,
                    workspace_root=pipeline._host.workspace_root,
                    primary=news_cfg.primary,
                    enable_cache=news_cfg.enable_cache,
                    cache_path=news_cfg.cache_path,
                ),
                synthetic_fallback_fn=(
                    None
                    if prefer_real
                    else lambda n, p: pipeline._host._generate_synthetic_ticks(n, start_price=p or start_price)
                ),
                start_price=start_price,
                max_real_days=rem_max_days,
            )
            remediation_expansion_step = expanded.step_index
            pipeline._host._data_manifest["remediation_expansion_step"] = remediation_expansion_step
            if expanded.train_ticks:
                active_train = list(expanded.train_ticks)
                pipeline._host._real_data_pct = expanded.real_data_pct

        if plan.action == RemediationAction.REGIME_EXPAND:
            rollout_ticks = select_regime_diverse_train_ticks(active_train)
        elif plan.action == RemediationAction.HOLDOUT_ACTIVITY:
            rollout_ticks = filter_train_ticks_for_holdout_profile(active_train, holdout_data)
        else:
            rollout_ticks = active_train

        explore_steps = cur_cfg.exploration_steps * plan.explore_multiplier
        remediation_rollout = cp_attr("run_policy_rollout", run_policy_rollout)(
            runtime=pipeline._host.runtime,
            data=rollout_ticks,
            policy=pipeline._host.current_policy,
            target_trades=plan.rollout_target_trades,
            workspace_root=pipeline._host.workspace_root,
            constitution_guard=pipeline._host._constitution_guard,
            exploration_steps=explore_steps,
            escalation_level=2 if plan.action != RemediationAction.SHARPE_POLISH else 1,
        )
        for traj in remediation_rollout.trajectories:
            pipeline._host.buffer.add(traj, priority=2.0)
        pipeline._host.cumulative_trades += remediation_rollout.trades

        ppo_steps = plan.ppo_timesteps
        if plan.action == RemediationAction.SHARPE_POLISH:
            ppo_steps = max(1000, polish_timesteps // max(1, attempt))
        elif len(pipeline._host.buffer) < 80:
            ppo_steps = min(ppo_steps, 2000)

        if len(pipeline._host.buffer) >= 80:
            pipeline._host.current_policy = pipeline._host.ppo_trainer.update_from_buffer(
                buffer=pipeline._host.buffer,
                timesteps=ppo_steps,
                birth_phase=True,
            )
            pipeline._host.ppo_steps += ppo_steps
            pipeline._host._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=post_birth_checkpoint_stage().value,
                phase=POST_BIRTH_CERTIFICATE_PHASE,
            )

        current_eval = cp_attr("evaluate_holdout_certificate", evaluate_holdout_certificate)(
            runtime=pipeline._host.runtime,
            holdout_data=holdout_data,
            policy=pipeline._host.current_policy,
            real_data_pct=pipeline._host._real_data_pct,
            holdout_days=split.holdout_days,
            constitution_violations=pipeline._host._constitution_guard.violations,
            workspace_root=pipeline._host.workspace_root,
            thresholds=pipeline._host.birth_config.certificate_thresholds,
        )
        if current_eval.get("certificate_passed"):
            return current_eval

    write_birth_progress(
        pipeline._host.workspace_root,
        stage="failed",
        phase="certificate_failed",
        message="Birth Certificate v2 thresholds not met after remediation.",
        progress_pct=100.0,
        cumulative_trades=pipeline._host.cumulative_trades,
        target_trades=trade_budget_cap,
        birth_start_time=pipeline._host.birth_start_time,
        oos_metrics=current_eval,
        oos_regime_breakdown=dict(current_eval.get("oos_regime_breakdown") or {}),
        failure_reasons=list(current_eval.get("failure_reasons") or []),
        remediation_attempt=pipeline._host._remediation_attempt,
        stages_passed=list(pipeline._host._stages_passed),
        data_manifest=dict(pipeline._host._data_manifest),
        needs_attention=True,
        retryable=True,
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
        curriculum_stage=post_birth_checkpoint_stage().value,
        phase="certificate_failed",
        oos_metrics=dict(current_eval),
    )
    return current_eval
