"""Certificate Runway (MVR): post-curriculum stages S5–S7 + micro-OOS probes."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.certificate_evaluator import (
    evaluate_holdout_certificate,
    sharpe_from_pnl,
    max_drawdown_pct,
)
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, ordered_runway_stages
from lumina_core.birth.evolution_proof_gate import EvolutionProofConfig, evaluate_evolution_proof
from lumina_core.birth.remediation import filter_train_ticks_for_holdout_profile


def runway_stage_index(stage: CurriculumStage) -> int:
    stages = ordered_runway_stages()
    try:
        return stages.index(stage) + 5
    except ValueError:
        return 5


def ticks_for_runway_stage(
    stage: CurriculumStage,
    *,
    train_ticks: list[dict[str, Any]],
    holdout_ticks: list[dict[str, Any]],
    validation_ticks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if stage in {CurriculumStage.STAGE5_PROFIT_VAL, CurriculumStage.STAGE6_RISK_DISCIPLINE}:
        return list(validation_ticks) if validation_ticks else list(train_ticks)
    if stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
        matched = filter_train_ticks_for_holdout_profile(train_ticks, holdout_ticks)
        return matched if matched else list(train_ticks)
    return list(train_ticks)


def micro_oos_probe(
    *,
    runtime: Any,
    holdout_data: list[dict[str, Any]],
    policy: Any,
    real_data_pct: float,
    holdout_days: int,
    constitution_violations: int,
    workspace_root: Any,
    thresholds: Any,
    max_trades: int = 800,
) -> dict[str, Any]:
    """Read-only holdout eval (never trains on holdout). Multi-slice mean when data allows."""
    from lumina_core.birth.certificate_evaluator import evaluate_multi_slice_micro_oos

    if len(holdout_data or []) >= 90:
        return evaluate_multi_slice_micro_oos(
            runtime=runtime,
            holdout_data=holdout_data,
            policy=policy,
            real_data_pct=real_data_pct,
            holdout_days=holdout_days,
            constitution_violations=constitution_violations,
            workspace_root=workspace_root,
            thresholds=thresholds,
            max_trades=max_trades,
            slices=3,
        )
    return evaluate_holdout_certificate(
        runtime=runtime,
        holdout_data=holdout_data,
        policy=policy,
        real_data_pct=real_data_pct,
        holdout_days=holdout_days,
        constitution_violations=constitution_violations,
        workspace_root=workspace_root,
        thresholds=thresholds,
        max_trades=max_trades,
    )


def micro_oos_sanity_passed(
    probe: dict[str, Any],
    *,
    cfg: BirthCurriculumConfig,
    baseline_oos_winrate: float,
) -> tuple[bool, str]:
    wr = float(probe.get("oos_winrate", 0.0) or 0.0)
    floor = float(getattr(cfg, "runway_s6_oos_sanity_winrate_min", 0.35))
    if wr < floor:
        return False, f"oos_winrate {wr:.2%} < sanity floor {floor:.0%}"
    if baseline_oos_winrate > 0 and wr <= baseline_oos_winrate:
        return False, f"oos_winrate {wr:.2%} not above baseline {baseline_oos_winrate:.2%}"
    return True, f"oos_winrate {wr:.2%} above baseline"


def micro_oos_evolution_proof_passed(
    probe: dict[str, Any],
    *,
    birth_exit_winrate: float,
    cfg: BirthCurriculumConfig,
) -> tuple[bool, str]:
    proof_cfg = EvolutionProofConfig(
        min_trades=int(cfg.evolution_proof_min_trades),
        min_winrate_lift=float(cfg.evolution_proof_min_winrate_lift),
        polish_oos_winrate_min=float(cfg.evolution_proof_polish_oos_winrate_min),
    )
    result = evaluate_evolution_proof(
        birth_exit_winrate=float(birth_exit_winrate),
        polish_oos_winrate=float(probe.get("oos_winrate", 0.0) or 0.0),
        holdout_trades=int(probe.get("holdout_trades", 0) or 0),
        cfg=proof_cfg,
    )
    if result.passed:
        return True, "; ".join(result.reasons) if result.reasons else "evolution_proof_passed"
    return False, "; ".join(result.reasons) if result.reasons else "evolution_proof_failed"


def risk_metrics_from_pnl(pnl_series: list[float]) -> tuple[float, float]:
    return sharpe_from_pnl(pnl_series), max_drawdown_pct(pnl_series)
