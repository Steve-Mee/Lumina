"""Birth Foundation curriculum loop (ADR-0046) then complete_foundation_birth."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.birth_phase_bootstrap import BirthPhaseBootstrap
from lumina_core.birth.birth_phase_data_policy import BirthPhaseDataReady
from lumina_core.birth.curriculum import (
    ordered_stages,
    stage_trade_target,
)
from lumina_core.birth.progress import merge_birth_progress_extra, write_birth_progress
from lumina_core.birth.purged_split import purged_validation_split
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

    # Terminal freeze: do not re-enter hollow curriculum grind. Twin/operator must
    # resolve expand_data | accept_champion | wipe first (ADR-0024 / Twin-first Birth).
    try:
        from lumina_core.birth.terminal_freeze import (
            extract_terminal_freeze,
            freeze_attention_fields,
            freeze_blocks_curriculum_grind,
        )

        freeze = extract_terminal_freeze(
            getattr(host, "_terminal_freeze", None),
            getattr(host, "_active_stage_metrics", None),
            checkpoint_state if isinstance(checkpoint_state, dict) else None,
        )
        metrics_pending = dict(getattr(host, "_active_stage_metrics", None) or {})
        if freeze_blocks_curriculum_grind(freeze) and not bool(
            metrics_pending.get("pending_data_expand")
        ):
            frozen_stage = str((freeze or {}).get("curriculum_stage") or "stage_stalled")
            attn = freeze_attention_fields(freeze or {})
            write_birth_progress(
                host.workspace_root,
                stage="stage_stalled",
                phase="stage_stalled",
                message=str(
                    attn.get("attention_summary")
                    or "Terminal freeze — Twin/operator fork required"
                ),
                progress_pct=27.0 + (stage_index / max(1, total_stages)) * 53.0,
                cumulative_trades=host.cumulative_trades,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=host.birth_start_time,
                training_mode=training_mode,
                **merge_birth_progress_extra(
                    host._budget_progress_fields(
                        terminal_stall_reason=str((freeze or {}).get("reason") or "")
                    ),
                    host._constitution_progress_fields(),
                    attn,
                    {
                        "curriculum_stage": frozen_stage,
                        "stages_passed": list(host._stages_passed),
                    },
                ),
            )
            host._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=frozen_stage,
                policy_path=str(host.final_policy_path),
                phase="stage_stalled",
                stage_metrics=dict(metrics_pending),
            )
            logger.warning(
                "birth.terminal_freeze.block_curriculum reason=%s stage=%s next=%s",
                (freeze or {}).get("reason"),
                frozen_stage,
                (freeze or {}).get("next_action"),
            )
            return {
                "status": "stage_stalled",
                "failure_reason": str((freeze or {}).get("reason") or "terminal_freeze"),
                "total_trades": host.cumulative_trades,
                "ppo_steps": host.ppo_steps,
                "training_mode": training_mode,
            }
    except Exception as exc:
        logger.debug("birth.terminal_freeze.curriculum_gate_failed: %s", exc)

    val_split = purged_validation_split(
        list(split.train),
        validation_pct=float(cfg.curriculum.certificate_runway_validation_pct),
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

        if stage.value in host._stages_passed:
            if host._verify_stage_pass_receipt_for_skip(stage, training_mode=training_mode):
                stage_index += 1
                continue
            host._stages_passed = [
                s for s in host._stages_passed if s != stage.value
            ]

        from lumina_core.birth.foundation_stages import ticks_for_foundation_stage

        stage_ticks = ticks_for_foundation_stage(
            stage,
            train_ticks=list(split.train),
            validation_ticks=list(val_split.validation),
            holdout_ticks=list(split.holdout),
        )
        if not stage_ticks:
            logger.error("birth.foundation.empty_ticks_fail_closed stage=%s", stage.value)
            return {
                "status": "stage_failed",
                "failure_reason": f"empty_stage_ticks:{stage.value}",
                "total_trades": host.cumulative_trades,
                "training_mode": training_mode,
            }
        target = stage_trade_target(stage, cfg.curriculum)
        host._accumulate_constitution_violations_before_stage_reset()

        stage_progress_pct = 27.0 + (stage_index / total_stages) * 53.0
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

    from lumina_core.birth.foundation_complete import complete_foundation_birth

    return complete_foundation_birth(
        host,
        training_mode=training_mode,
        trade_budget_cap=cfg.trade_budget_cap,
        practice_mode=practice_mode,
    )
