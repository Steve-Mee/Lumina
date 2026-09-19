"""Stage-scoped periodic quality plans (S2 expectancy vs S3 occupancy taxi)."""

from __future__ import annotations

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller_types import (
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.meta_decide_stage_quality")


def maybe_stage3_occupancy_plan(ctrl: object, snap: LearningSnapshot) -> MetaActionPlan | None:
    from lumina_core.birth.stage3_occupancy_meta import (
        stage3_occupancy_meta_fields,
        stage3_occupancy_taxi_needed,
    )

    if not stage3_occupancy_taxi_needed(
        stage=snap.stage,
        occupancy=float(getattr(snap, "range_flat_ratio", 0.0) or 0.0),
        occupancy_exam_armed=getattr(snap, "occupancy_exam_armed", None),
        range_flat_ratio=float(getattr(snap, "range_flat_ratio", 0.0) or 0.0),
        range_total_signals=int(getattr(snap, "range_total_signals", 0) or 0),
    ):
        return None
    cfg = getattr(ctrl, "cfg")
    occ_f = stage3_occupancy_meta_fields(
        exploration_steps=int(cfg.exploration_steps),
        strong_recovery_explore_fraction=float(cfg.strong_recovery_explore_fraction),
    )
    plan = MetaActionPlan(
        primary=RecoveryStrategy.EXPLORE_REDUCE,
        secondary=(RecoveryStrategy.REWARD_SHAPING_TWEAK,),
        explore_steps=int(occ_f["explore_steps"]),
        mine=False,
        escalation_delta=int(occ_f["escalation_delta"]),
        explore_steps_multiplier=max(
            0.4, min(1.0, float(cfg.meta_explore_decay_stall))
        ),
        rationale=str(occ_f["rationale"]),
        snapshot=snap,
    )
    setattr(ctrl, "explore_multiplier", plan.explore_steps_multiplier)
    record = getattr(ctrl, "_record_plan", None)
    if callable(record):
        record(plan)
    return plan


def build_stage2_expectancy_quality_plan(
    ctrl: object, snap: LearningSnapshot
) -> MetaActionPlan | None:
    """Quality ladder when stall owns Stage-2; never silent-fail to thrash."""
    from lumina_core.birth.expectancy_stall import (
        build_expectancy_quality_meta_fields,
        snapshot_expectancy_stall,
    )
    from lumina_core.birth.runtime_diagnostics import log_meta_decision_trace

    if snap.stage != CurriculumStage.STAGE2_RANGE:
        return None
    cfg = getattr(ctrl, "cfg")
    if not snapshot_expectancy_stall(snap, cfg=cfg):
        logger.warning(
            "birth.meta.expectancy_quality path=skip trigger=periodic reason=no_stall "
            "trades=%s wins=%s wr_hist=%s flat=%.3f signals=%s",
            int(getattr(snap, "stage_trades", 0) or 0),
            int(getattr(snap, "stage_wins", 0) or 0),
            float((getattr(snap, "winrate_history", ()) or (0.0,))[-1])
            if getattr(snap, "winrate_history", None)
            else 0.0,
            float(getattr(snap, "range_flat_ratio", 0.0) or 0.0),
            int(getattr(snap, "range_total_signals", 0) or 0),
        )
        return None
    quality_step = int(getattr(snap, "expectancy_quality_step", 0) or 0)
    if quality_step <= 0:
        quality_step = max(0, int(getattr(snap, "escalation_level", 0) or 0))
    edge_vr = getattr(snap, "edge_vs_random", None)
    try:
        edge_vr_f = float(edge_vr) if edge_vr is not None else None
    except (TypeError, ValueError):
        edge_vr_f = None
    fields = build_expectancy_quality_meta_fields(
        range_flat_ratio=float(getattr(snap, "range_flat_ratio", 0.5) or 0.5),
        remediation_step=quality_step,
        base_explore_steps=int(cfg.exploration_steps),
        exploration_steps=int(cfg.exploration_steps),
        strong_recovery_explore_fraction=float(cfg.strong_recovery_explore_fraction),
        edge_vs_random=edge_vr_f,
    )
    secondary: list[RecoveryStrategy] = []
    for sec in fields.get("secondary") or ():
        try:
            s = RecoveryStrategy(str(sec))
        except ValueError:
            continue
        if s == RecoveryStrategy.EXPLORE_BOOST:
            continue
        secondary.append(s)
    apply_tweak = getattr(ctrl, "_apply_reward_tweak", None)
    reward_tweak = apply_tweak(snap) if callable(apply_tweak) else None
    if reward_tweak is not None and RecoveryStrategy.REWARD_SHAPING_TWEAK not in secondary:
        secondary.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
    plan = MetaActionPlan(
        primary=RecoveryStrategy(str(fields["primary"])),
        secondary=tuple(dict.fromkeys(secondary)),
        explore_steps=int(fields["explore_steps"]),
        mine=bool(fields.get("mine")),
        reward_tweak=reward_tweak,
        escalation_delta=int(fields.get("escalation_delta") or 1),
        explore_steps_multiplier=max(
            0.4, min(1.0, float(cfg.meta_explore_decay_stall))
        ),
        rationale=str(fields.get("rationale") or "stage2_expectancy_periodic"),
        snapshot=snap,
    )
    log_meta_decision_trace(
        trigger="periodic",
        primary=plan.primary.value,
        rationale=plan.rationale,
        secondary=[s.value for s in plan.secondary],
        stage=str(getattr(snap.stage, "value", snap.stage)),
        stage_trades=int(snap.stage_trades),
        stage_wins=int(getattr(snap, "stage_wins", 0) or 0),
        flat=float(getattr(snap, "range_flat_ratio", 0.0) or 0.0),
        stall=True,
        coerced=False,
        source="decide_periodic_quality",
    )
    return plan
