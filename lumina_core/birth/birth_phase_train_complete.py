"""Birth phase curriculum loop, runway, practice complete, stage8 certificate."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.birth.birth_phase_bootstrap import BirthPhaseBootstrap
from lumina_core.birth.birth_phase_data_policy import BirthPhaseDataReady
from lumina_core.birth.buffer_persist import clear_buffer
from lumina_core.birth.checkpoint import clear_checkpoint
from lumina_core.birth.curriculum import (
    CurriculumStage,
    filter_ticks_for_stage,
    ordered_stages,
    stage_trade_target,
)
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.purged_split import purged_validation_split
from lumina_core.birth.runway import micro_oos_probe
from lumina_core.birth.stage_scorecard import build_scorecard_payload
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.birth_phase_train_complete")


def run_curriculum_and_complete(
    host: Any,
    boot: BirthPhaseBootstrap,
    data: BirthPhaseDataReady,
) -> dict[str, Any]:
    cfg = boot.cfg
    training_mode = boot.training_mode
    practice_mode = boot.practice_mode
    prefer_real = boot.prefer_real
    ppo_steps_per_update = boot.ppo_steps_per_update
    checkpoint_state = boot.checkpoint_state
    split = data.split
    start_price = data.start_price
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
