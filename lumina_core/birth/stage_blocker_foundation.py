"""Foundation HUD blockers (process-R). EdgeScore remains diagnostic theater."""

from __future__ import annotations

from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_metrics import (
    S1_MIN_TRADES,
    S2_MIN_TRADES,
    S3_MIN_TRADES,
    S4_MIN_TRADES,
    S5_MIN_TRADES,
    build_foundation_snapshot,
)
from lumina_core.birth.foundation_pass import evaluate_foundation_pass
from lumina_core.birth.foundation_stages import is_foundation_stage


def _min_trades(stage: CurriculumStage) -> int:
    return {
        CurriculumStage.STAGE1_TREND: S1_MIN_TRADES,
        CurriculumStage.STAGE2_RANGE: S2_MIN_TRADES,
        CurriculumStage.STAGE3_MIXED: S3_MIN_TRADES,
        CurriculumStage.STAGE4_VIABLE_PLANT: S4_MIN_TRADES,
        CurriculumStage.STAGE5_PROBE_HANDOFF: S5_MIN_TRADES,
    }.get(stage, 50)


def _metric_from_blocker(text: str) -> tuple[str, float]:
    raw = str(text or "")
    low = raw.lower()
    if "policy_sample" in low:
        return "policy_sample", 0.0
    if "occupancy" in low:
        return "occupancy", 0.0
    if "median_loss_r" in low:
        return "median_loss_r", 0.0
    if "mean_r" in low or "e_mech" in low:
        return "mean_r", 0.0
    if "edge" in low:
        return "edge", 0.0
    if "settlement" in low:
        return "settlement", 0.0
    if "entropy" in low:
        return "entropy", 0.0
    if "constitution" in low:
        return "constitution_violations", 0.0
    if "replay" in low:
        return "replay_cap", 0.0
    if "round_trips" in low:
        return "round_trips", 0.0
    if "sharpe" in low:
        return "oos_sharpe", 0.0
    if "oos_dd" in low or "dd=" in low:
        return "oos_dd", 0.0
    if "net_rr" in low:
        return "net_rr", 0.0
    if "trades" in low:
        return "trades", 0.0
    return "foundation", 0.0


def compute_foundation_hud_blocker(
    stage: CurriculumStage,
    *,
    trades: int,
    wins: int,
    required: int,
    constitution_violations: int,
    occupancy: float | None = None,
    median_loss_r: float | None = None,
    mean_r: float | None = None,
    first_touch_hit_rate: float | None = None,
    geometry_net_rr: float | None = None,
    unique_calendar_days: int | None = None,
    oos_sharpe: float | None = None,
    oos_dd_pct: float | None = None,
    range_round_trips: int = 0,
    settlement_ok: bool = True,
    settlement_share: float = 1.0,
    entropy_alive: bool = True,
    pnl_series: list[float] | None = None,
    r_series: list[float] | None = None,
    stop_pct: float | None = None,
    ref_price: float | None = None,
    skill_trades: int | None = None,
    skill_wins: int | None = None,
) -> tuple[str | None, float | None, str | None] | None:
    """Process-R blocker for Foundation stages.

    Returns ``None`` when this path should defer to EdgeScore/legacy HUD.
    Returns ``(None, None, None)`` when trades are still below the gate.
    """
    if not is_foundation_stage(stage):
        return None
    floor = max(int(required), _min_trades(stage))
    if int(trades) < floor:
        return (None, None, None)
    # Missing process-R after the volume gate is a blocker, not EdgeScore theater.
    snap = build_foundation_snapshot(
        trades=int(trades),
        wins=int(wins),
        skill_trades=skill_trades,
        skill_wins=skill_wins,
        pnl_series=list(pnl_series) if pnl_series else None,
        r_series=list(r_series) if r_series is not None else None,
        stop_pct=stop_pct,
        ref_price=ref_price,
        median_loss_r_value=median_loss_r,
        mean_r_value=mean_r,
        occupancy=occupancy,
        net_rr=geometry_net_rr,
        p_ft=first_touch_hit_rate,
        settlement_ok=bool(settlement_ok),
        settlement_share=float(settlement_share),
        constitution_violations=int(constitution_violations),
        entropy_alive=bool(entropy_alive),
        unique_calendar_days=int(unique_calendar_days or 0),
        oos_sharpe=oos_sharpe,
        oos_dd_pct=oos_dd_pct,
    )
    decision = evaluate_foundation_pass(
        stage,
        snap,
        round_trips=int(range_round_trips),
        required_round_trips=max(3, floor // 10),
    )
    if decision.passed:
        return (None, None, None)
    first = decision.blockers[0] if decision.blockers else "foundation_fail"
    metric, _ = _metric_from_blocker(first)
    value = _blocker_value(snap, metric)
    return (metric, value, decision.message)


def _blocker_value(snap: object, metric: str) -> float | None:
    """HUD value must be the blocked physics field, never skill WR as a stand-in."""
    attr = {
        "occupancy": "occupancy",
        "median_loss_r": "median_loss_r",
        "mean_r": "mean_r",
        "edge": "edge",
        "settlement": "settlement_share",
        "constitution_violations": "constitution_violations",
        "oos_sharpe": "oos_sharpe",
        "oos_dd": "oos_dd_pct",
        "net_rr": "net_rr",
        "trades": "trades",
        "policy_sample": "skill_trades",
        "replay_cap": "unique_calendar_days",
        "round_trips": None,
        "entropy": None,
    }.get(metric, metric)
    if attr is None:
        return None
    raw = getattr(snap, attr, None)
    if raw is None:
        return None
    try:
        return round(float(raw), 4)
    except (TypeError, ValueError):
        return None


__all__ = ["compute_foundation_hud_blocker"]
