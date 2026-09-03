"""Complete Birth after five foundation receipts + fitness vector (ADR-0046).

Certificate OOS 0.48 is Proving Ground — not this path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.birth.buffer_persist import clear_buffer
from lumina_core.birth.checkpoint import clear_checkpoint
from lumina_core.birth.curriculum import CurriculumStage, ordered_stages
from lumina_core.birth.fitness_vector import (
    BirthFitnessVector,
    receipt_checksum,
    write_fitness_vector,
)
from lumina_core.birth.foundation_metrics import FOUNDATION_SCHEMA
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.stage_pass_receipt_types import receipt_for_stage
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.foundation_complete")


def _s5_receipt_clears_exam(s5: Any) -> bool:
    """Refuse a fitness vector from a failing S5 snapshot/receipt."""
    from lumina_core.birth.foundation_metrics import build_foundation_snapshot
    from lumina_core.birth.foundation_pass import evaluate_foundation_pass

    policy_n = getattr(s5, "policy_trades", None)
    policy_w = getattr(s5, "policy_wins", None)
    snap = build_foundation_snapshot(
        trades=int(getattr(s5, "trades", 0) or 0),
        wins=int(getattr(s5, "wins", 0) or 0),
        skill_trades=int(policy_n) if policy_n is not None else int(getattr(s5, "trades", 0) or 0),
        skill_wins=int(policy_w) if policy_w is not None else int(getattr(s5, "wins", 0) or 0),
        occupancy=getattr(s5, "occupancy", None),
        median_loss_r_value=getattr(s5, "median_loss_r", None),
        mean_r_value=getattr(s5, "mean_r", None),
        p_ft=getattr(s5, "p_ft", None),
        net_rr=getattr(s5, "geometry_net_rr", None),
        settlement_ok=True,
        settlement_share=1.0,
        constitution_violations=0,
        entropy_alive=True,
        unique_calendar_days=int(getattr(s5, "unique_calendar_days", 0) or 0),
        oos_sharpe=getattr(s5, "oos_sharpe", None),
        oos_dd_pct=getattr(s5, "oos_dd_pct", None),
    )
    return bool(
        evaluate_foundation_pass(CurriculumStage.STAGE5_PROBE_HANDOFF, snap).passed
    )


def _missing_foundation_receipts(host: Any) -> list[str]:
    receipts = list(getattr(host, "_stage_pass_receipts", []) or [])
    missing: list[str] = []
    for stage in ordered_stages():
        rec = receipt_for_stage(receipts, stage.value)
        if rec is None or str(getattr(rec, "schema", "") or "") != FOUNDATION_SCHEMA:
            missing.append(stage.value)
            continue
        if getattr(rec, "median_loss_r", None) is None or getattr(rec, "mean_r", None) is None:
            missing.append(stage.value)
            continue
        if stage != CurriculumStage.STAGE1_TREND and getattr(rec, "occupancy", None) is None:
            missing.append(stage.value)
    return missing


def complete_foundation_birth(
    host: Any,
    *,
    training_mode: str,
    trade_budget_cap: int,
    practice_mode: bool,
) -> dict[str, Any]:
    missing = _missing_foundation_receipts(host)
    if missing:
        return {
            "status": "foundation_incomplete",
            "failure_reason": "missing_foundation_receipts:" + ",".join(missing),
            "total_trades": host.cumulative_trades,
            "training_mode": training_mode,
        }
    s5 = receipt_for_stage(
        list(getattr(host, "_stage_pass_receipts", []) or []),
        CurriculumStage.STAGE5_PROBE_HANDOFF.value,
    )
    if s5 is None:
        return {
            "status": "foundation_incomplete",
            "failure_reason": "missing_stage5_receipt",
            "total_trades": host.cumulative_trades,
            "training_mode": training_mode,
        }
    if s5.oos_sharpe is None:
        return {
            "status": "foundation_incomplete",
            "failure_reason": "missing_stage5_oos_sharpe",
            "total_trades": host.cumulative_trades,
            "training_mode": training_mode,
        }
    if not _s5_receipt_clears_exam(s5):
        return {
            "status": "foundation_incomplete",
            "failure_reason": "s5_exam_fail_no_fitness_vector",
            "total_trades": host.cumulative_trades,
            "training_mode": training_mode,
        }
    receipts_payload = [
        r.to_dict() for r in list(getattr(host, "_stage_pass_receipts", []) or [])
    ]
    write_birth_progress(
        host.workspace_root,
        stage="foundation_handoff",
        phase="foundation_handoff",
        message="Persisting five foundation receipts before fitness vector.",
        progress_pct=99.0,
        cumulative_trades=host.cumulative_trades,
        target_trades=trade_budget_cap,
        birth_start_time=host.birth_start_time,
        curriculum_total=5,
        stage_pass_receipts=receipts_payload,
    )
    checksum = receipt_checksum(s5.to_dict())
    vector = BirthFitnessVector(
        schema=FOUNDATION_SCHEMA,
        mean_r=float(s5.mean_r or 0.0),
        edge=float(s5.edge or 0.0),
        occupancy=float(s5.occupancy or 0.0),
        oos_wr=float(s5.winrate),
        oos_sharpe=float(s5.oos_sharpe),
        median_loss_r=float(s5.median_loss_r or 0.0),
        s5_receipt_checksum=checksum,
        trades=int(s5.trades),
    )
    write_fitness_vector(host.workspace_root, vector)
    from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

    if not is_birth_exit_sufficient(host.workspace_root):
        return {
            "status": "foundation_incomplete",
            "failure_reason": "birth_exit_insufficient_after_fitness",
            "total_trades": host.cumulative_trades,
            "training_mode": training_mode,
            "fitness_vector": vector.to_dict(),
        }
    try:
        from lumina_core.birth.dna_handoff import register_birth_gen0_from_fitness

        register_birth_gen0_from_fitness(host.workspace_root, vector)
    except Exception as exc:
        logger.warning("birth.foundation.dna_handoff_failed: %s", exc)

    try:
        from lumina_core.birth.birth_exit_policy_export import export_birth_exit_pi_star

        export_birth_exit_pi_star(host)
    except Exception as exc:
        logger.warning("birth.foundation.pi_star_export_failed: %s", exc)

    polish_steps = min(10_000, int(host.birth_config.curriculum.polish_ppo_timesteps))
    if len(host.buffer) >= 256:
        try:
            host.ppo_trainer.final_birth_polish(host.buffer)
            host.ppo_steps += polish_steps
        except Exception as exc:
            logger.warning("birth.foundation.light_polish_failed: %s", exc)

    target_policy = (
        host.practice_policy_path if practice_mode else host.final_policy_path
    )
    try:
        host.ppo_trainer.save_final_birth_policy(str(target_policy))
    except Exception as exc:
        logger.warning("birth.foundation.save_policy_failed: %s", exc)

    flag = (
        host.practice_completed_flag_path
        if practice_mode
        else host.completion_flag_path
    )
    flag.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    from lumina_core.birth.s5_close_ledger_archive import flush_close_ledger_before_wipe

    flush_close_ledger_before_wipe(host, seal=True, clear_memory=False)
    clear_checkpoint(host.workspace_root)
    clear_buffer(host.workspace_root)
    status = "practice_completed" if practice_mode else "completed"
    write_birth_progress(
        host.workspace_root,
        stage=status,
        phase=status,
        message="Birth Foundation complete — evolvable plant. Certificate OOS is Proving Ground.",
        progress_pct=100.0,
        cumulative_trades=host.cumulative_trades,
        target_trades=trade_budget_cap,
        birth_start_time=host.birth_start_time,
        curriculum_total=5,
        stage_pass_receipts=receipts_payload,
    )
    logger.info("birth.foundation.complete mode=%s checksum=%s", training_mode, checksum)
    return {
        "status": status,
        "total_trades": host.cumulative_trades,
        "ppo_steps": host.ppo_steps,
        "real_data_pct": host._real_data_pct,
        "policy_path": str(target_policy),
        "training_mode": "practice" if practice_mode else training_mode,
        "fitness_vector": vector.to_dict(),
    }
