"""Birth phase certificate fast-path resume (runway / remediation / complete)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.birth_phase_bootstrap import BirthPhaseBootstrap
from lumina_core.birth.birth_phase_certificate_gate import certificate_fast_path_eligible
from lumina_core.birth.birth_phase_data_policy import BirthPhaseDataReady
from lumina_core.birth.purged_split import purged_validation_split
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.birth_phase_certificate_resume")


def _orch():
    """Late-bound façade for monkeypatch-compatible symbol resolution."""
    from lumina_core.birth import birth_phase_orchestrator as _facade

    return _facade


def try_certificate_fast_path_resume(
    host: Any,
    boot: BirthPhaseBootstrap,
    data: BirthPhaseDataReady,
) -> dict[str, Any] | None:
    """Return a terminal result if certificate fast-path handles this run; else None."""
    cfg = boot.cfg
    training_mode = boot.training_mode
    resume = boot.resume
    practice_mode = boot.practice_mode
    progress_snapshot = boot.progress_snapshot
    checkpoint_state = boot.checkpoint_state
    ppo_steps_per_update = boot.ppo_steps_per_update
    prefer_real = boot.prefer_real
    split = data.split
    start_price = data.start_price
    from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

    if not is_birth_exit_sufficient(host.workspace_root):
        logger.info("birth.certificate_fast_path.blocked_until_foundation_exit")
        return None

    if (
        not practice_mode
        and resume
        and certificate_fast_path_eligible(host, progress_snapshot, checkpoint_state)
    ):
        if cfg.curriculum.certificate_runway_enabled:
            _orch().write_birth_progress(
                host.workspace_root,
                stage="training_running",
                phase=POST_BIRTH_CERTIFICATE_PHASE,
                message="Resuming post-Birth certificate (Proving Ground) from checkpoint.",
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

        _orch().write_birth_progress(
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
        prior_progress = _orch().read_birth_progress(host.workspace_root)
        prior_eval = prior_progress.get("oos_metrics")
        if not isinstance(prior_eval, dict) or not prior_eval.get("failure_reasons"):
            prior_eval = _orch().evaluate_holdout_certificate(
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


    return None
