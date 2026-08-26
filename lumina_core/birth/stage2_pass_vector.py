"""Stage-2 Pass Vector SSOT — multi-blocker gaps without floor theater.

Live forensics showed concurrent failures:
  - expectancy (WR ~27% vs 35% proxy)
  - occupancy (flat outside 30–70%)
  - edge_vs_random < 0 (worse than first-touch random)

This module unifies those gaps for meta/progress diagnostics. It never lowers
expectancy floors or widens the flat band.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

DominantGap = Literal[
    "none",
    "edge",
    "expectancy",
    "occupancy_over",  # flat too low → over-trading
    "occupancy_under",  # flat too high → under-activity
    "mixed_quality",  # edge/exp + occupancy
]

RemediationAction = Literal[
    "hold_pass_path",
    "selective_quality_open",  # under-activity + quality gap
    "suppress_churn",  # over-trading
    "beat_random_quality",  # edge < 0 owns ladder
    "expectancy_quality",  # exp gap only
]


@dataclass(frozen=True, slots=True)
class Stage2PassVector:
    """Truthful multi-blocker snapshot for Stage-2."""

    flat: float
    expectancy: float
    exp_floor: float
    edge_vs_random: float
    occupancy_over_gap: float
    occupancy_under_gap: float
    exp_gap: float
    edge_gap: float
    dominant: DominantGap
    action: RemediationAction
    in_flat_band: bool
    beat_random: bool

    def as_progress_fields(self) -> dict[str, Any]:
        return {
            "pass_vector_flat": round(float(self.flat), 4),
            "pass_vector_expectancy": round(float(self.expectancy), 4),
            "pass_vector_exp_floor": round(float(self.exp_floor), 4),
            "pass_vector_edge_vs_random": round(float(self.edge_vs_random), 4),
            "pass_vector_occupancy_over_gap": round(float(self.occupancy_over_gap), 4),
            "pass_vector_occupancy_under_gap": round(float(self.occupancy_under_gap), 4),
            "pass_vector_exp_gap": round(float(self.exp_gap), 4),
            "pass_vector_edge_gap": round(float(self.edge_gap), 4),
            "pass_vector_dominant": str(self.dominant),
            "pass_vector_action": str(self.action),
            "pass_vector_in_flat_band": bool(self.in_flat_band),
            "pass_vector_beat_random": bool(self.beat_random),
        }


def compute_stage2_pass_vector(
    *,
    range_flat_ratio: float,
    expectancy: float,
    exp_floor: float = -0.15,
    edge_vs_random: float = 0.0,
    band_lo: float = 0.30,
    band_hi: float = 0.70,
) -> Stage2PassVector:
    """Compute occupancy / expectancy / edge gaps and dominant remediation.

    ``range_flat_ratio`` = fraction of bars with position==0 (empty).
    Low flat → over-trading; high flat → under-activity.
    """
    flat = float(range_flat_ratio)
    lo = float(band_lo)
    hi = float(band_hi)
    if lo >= hi:
        lo, hi = 0.30, 0.70
    exp = float(expectancy)
    floor = float(exp_floor)
    edge = float(edge_vs_random)

    occ_over = max(0.0, lo - flat)  # need more empty time
    occ_under = max(0.0, flat - hi)  # need more market time
    exp_gap = max(0.0, floor - exp)
    edge_gap = max(0.0, -edge)
    in_band = lo - 1e-12 <= flat <= hi + 1e-12
    beat_random = edge >= -1e-12

    quality_pressure = exp_gap > 1e-12 or edge_gap > 1e-12
    occ_pressure = occ_over > 1e-12 or occ_under > 1e-12

    if not quality_pressure and not occ_pressure:
        dominant: DominantGap = "none"
        action: RemediationAction = "hold_pass_path"
    # PR-C gap fix: in-band + anti-edge → beat_random owns (not inject flood).
    # Live: flat OK + edge < 0 + exp gap → pattern_inject thrash while stop-magnet.
    elif in_band and edge_gap > 1e-12:
        dominant = "edge" if edge_gap + 1e-12 >= exp_gap else "mixed_quality"
        action = "beat_random_quality"
    elif quality_pressure and occ_pressure:
        dominant = "mixed_quality"
        if occ_under > occ_over:
            action = "selective_quality_open"
        elif occ_over > 0:
            action = "suppress_churn"
        else:
            action = "beat_random_quality" if edge_gap >= exp_gap else "expectancy_quality"
    elif edge_gap > 0 and edge_gap >= exp_gap:
        dominant = "edge"
        action = "beat_random_quality"
    elif exp_gap > 0:
        dominant = "expectancy"
        action = "expectancy_quality"
    elif occ_under > 0:
        dominant = "occupancy_under"
        action = "selective_quality_open"
    else:
        dominant = "occupancy_over"
        action = "suppress_churn"

    return Stage2PassVector(
        flat=flat,
        expectancy=exp,
        exp_floor=floor,
        edge_vs_random=edge,
        occupancy_over_gap=occ_over,
        occupancy_under_gap=occ_under,
        exp_gap=exp_gap,
        edge_gap=edge_gap,
        dominant=dominant,
        action=action,
        in_flat_band=in_band,
        beat_random=beat_random,
    )


def meta_fields_from_pass_vector(
    pv: Stage2PassVector,
    *,
    remediation_step: int = 0,
    base_explore_steps: int = 2000,
    exploration_steps: int = 2000,
    strong_recovery_explore_fraction: float = 0.35,
    meta_explore_decay_stall: float = 0.50,
) -> dict[str, Any]:
    """Map pass-vector action → meta RecoveryStrategy plan fields (single controller).

    Never returns explore_boost under quality pressure. Occupancy plant is SIM-side;
    meta only steers learning (mine / reduce / inject).
    """
    explore_floor = max(
        200,
        int(float(exploration_steps) * float(strong_recovery_explore_fraction)),
    )
    step = max(0, int(remediation_step))
    action = str(pv.action)

    if action == "hold_pass_path":
        return {
            "primary": "hold",
            "secondary": (),
            "explore_steps": int(base_explore_steps),
            "escalation_delta": 0,
            "mine": False,
            "rationale": "pass_vector_hold_pass_path",
            "explore_steps_multiplier": 1.0,
            "pass_vector_action": action,
            "pass_vector_dominant": str(pv.dominant),
        }

    if action == "suppress_churn":
        # Over-trading: less explore noise, quality mine, plant FORCE_FLAT handles rest.
        return {
            "primary": "explore_reduce",
            "secondary": ("reward_shaping_tweak", "pattern_inject"),
            "explore_steps": explore_floor,
            "escalation_delta": 1,
            "mine": True,
            "rationale": "pass_vector_suppress_churn",
            "explore_steps_multiplier": max(0.4, min(1.0, float(meta_explore_decay_stall))),
            "pass_vector_action": action,
            "pass_vector_dominant": str(pv.dominant),
        }

    if action == "selective_quality_open":
        # Under-activity + quality: mine net patterns; modest explore; no thrash boost.
        return {
            "primary": "pattern_inject",
            "secondary": ("explore_reduce", "reward_shaping_tweak"),
            "explore_steps": max(int(base_explore_steps), explore_floor),
            "escalation_delta": 1,
            "mine": True,
            "rationale": "pass_vector_selective_quality_open",
            "explore_steps_multiplier": max(0.5, min(1.0, float(meta_explore_decay_stall))),
            "pass_vector_action": action,
            "pass_vector_dominant": str(pv.dominant),
        }

    if action == "beat_random_quality":
        # Anti-edge owns the ladder until edge ≥ 0.
        from lumina_core.birth.expectancy_stall import build_expectancy_quality_meta_fields

        fields = build_expectancy_quality_meta_fields(
            range_flat_ratio=float(pv.flat),
            remediation_step=step,
            base_explore_steps=int(base_explore_steps),
            exploration_steps=int(exploration_steps),
            strong_recovery_explore_fraction=float(strong_recovery_explore_fraction),
            edge_vs_random=float(pv.edge_vs_random),
        )
        fields["rationale"] = f"pass_vector_beat_random_{fields.get('rationale', '')}"
        fields["pass_vector_action"] = action
        fields["pass_vector_dominant"] = str(pv.dominant)
        fields["explore_steps_multiplier"] = max(
            0.4, min(1.0, float(meta_explore_decay_stall))
        )
        return fields

    # expectancy_quality / default quality path
    from lumina_core.birth.expectancy_stall import build_expectancy_quality_meta_fields

    fields = build_expectancy_quality_meta_fields(
        range_flat_ratio=float(pv.flat),
        remediation_step=step,
        base_explore_steps=int(base_explore_steps),
        exploration_steps=int(exploration_steps),
        strong_recovery_explore_fraction=float(strong_recovery_explore_fraction),
        edge_vs_random=float(pv.edge_vs_random),
    )
    fields["rationale"] = f"pass_vector_expectancy_{fields.get('rationale', '')}"
    fields["pass_vector_action"] = action
    fields["pass_vector_dominant"] = str(pv.dominant)
    fields["explore_steps_multiplier"] = max(0.4, min(1.0, float(meta_explore_decay_stall)))
    # Near-miss finish: strip pattern_inject from secondary (caller may re-check state).
    return fields


def plan_stage2_from_snapshot(
    snap: Any,
    *,
    cfg: Any,
) -> dict[str, Any] | None:
    """Build pass-vector meta fields from a LearningSnapshot when Stage-2.

    Returns None when not Stage-2 or when pass path is clear and improving.
    """
    stage_s = str(getattr(getattr(snap, "stage", None), "value", getattr(snap, "stage", "")) or "")
    if "stage2" not in stage_s.lower() and "range" not in stage_s.lower():
        # Still allow explicit STAGE2 enum.
        try:
            from lumina_core.birth.curriculum import CurriculumStage

            if getattr(snap, "stage", None) != CurriculumStage.STAGE2_RANGE:
                return None
        except Exception:
            return None

    flat = float(getattr(snap, "range_flat_ratio", 0.5) or 0.5)
    trades = int(getattr(snap, "stage_trades", 0) or 0)
    wins = int(getattr(snap, "stage_wins", 0) or 0)
    # Prefer skill metric when snapshot carries it.
    skill_tr = getattr(snap, "skill_trades", None)
    skill_wn = getattr(snap, "skill_wins", None)
    if skill_tr is not None and int(skill_tr) > 0:
        trades = int(skill_tr)
        wins = int(skill_wn or 0)
    rolling = getattr(snap, "rolling_winrate", None)
    try:
        from lumina_core.birth.expectancy_stall import stage2_expectancy_live

        exp = stage2_expectancy_live(
            stage_trades=trades,
            stage_wins=wins,
            rolling_winrate=float(rolling) if rolling is not None else None,
        )
    except Exception:
        wr = float(wins) / float(max(1, trades)) if trades > 0 else 0.0
        exp = wr - 0.50
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        floor = float(stage2_expectancy_floor(cfg))
    except Exception:
        floor = float(getattr(cfg, "stage2_expectancy_floor", -0.15) or -0.15)
    edge = getattr(snap, "edge_vs_random", None)
    try:
        edge_f = float(edge) if edge is not None else 0.0
    except (TypeError, ValueError):
        edge_f = 0.0
    band_lo = float(getattr(cfg, "stage2_participation_band_lo", 0.30) or 0.30)
    band_hi = float(getattr(cfg, "stage2_participation_band_hi", 0.70) or 0.70)
    pv = compute_stage2_pass_vector(
        range_flat_ratio=flat,
        expectancy=exp,
        exp_floor=floor,
        edge_vs_random=edge_f,
        band_lo=band_lo,
        band_hi=band_hi,
    )
    # Clear path: let other improving logic run.
    if pv.dominant == "none" and bool(getattr(snap, "volume_gate_passed", False)):
        return None
    quality_step = int(getattr(snap, "expectancy_quality_step", 0) or 0)
    if quality_step <= 0:
        quality_step = max(0, int(getattr(snap, "escalation_level", 0) or 0))
    return meta_fields_from_pass_vector(
        pv,
        remediation_step=quality_step,
        base_explore_steps=int(getattr(cfg, "exploration_steps", 2000) or 2000),
        exploration_steps=int(getattr(cfg, "exploration_steps", 2000) or 2000),
        strong_recovery_explore_fraction=float(
            getattr(cfg, "strong_recovery_explore_fraction", 0.35) or 0.35
        ),
        meta_explore_decay_stall=float(getattr(cfg, "meta_explore_decay_stall", 0.50) or 0.50),
    )


def pass_vector_from_loop(loop: Any, *, cfg: Any = None) -> Stage2PassVector:
    """Build pass vector from a stage-loop session-like object."""
    signals = int(getattr(loop, "stage_range_total_signals", 0) or 0)
    flat_bars = int(getattr(loop, "stage_range_flat_bars", 0) or 0)
    flat = float(flat_bars) / float(max(1, signals)) if signals > 0 else 0.5
    trades = int(getattr(loop, "stage_trades", 0) or 0)
    wins = int(getattr(loop, "stage_wins", 0) or 0)
    rolling = None
    try:
        rolling, _, _ = loop._rolling_winrate_meta()  # type: ignore[attr-defined]
    except Exception:
        rolling = None
    try:
        from lumina_core.birth.expectancy_stall import stage2_expectancy_live

        exp = stage2_expectancy_live(
            stage_trades=trades,
            stage_wins=wins,
            rolling_winrate=float(rolling) if rolling is not None else None,
        )
    except Exception:
        wr = float(wins) / float(max(1, trades)) if trades > 0 else 0.0
        exp = wr - 0.50
    cur = cfg if cfg is not None else getattr(loop, "cur_cfg", None)
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        floor = float(stage2_expectancy_floor(cur)) if cur is not None else -0.15
    except Exception:
        floor = float(getattr(cur, "stage2_expectancy_floor", -0.15) or -0.15) if cur else -0.15
    edge = float(getattr(loop, "_edge_vs_random", 0.0) or 0.0)
    band_lo = float(getattr(cur, "stage2_participation_band_lo", 0.30) or 0.30) if cur else 0.30
    band_hi = float(getattr(cur, "stage2_participation_band_hi", 0.70) or 0.70) if cur else 0.70
    return compute_stage2_pass_vector(
        range_flat_ratio=flat,
        expectancy=exp,
        exp_floor=floor,
        edge_vs_random=edge,
        band_lo=band_lo,
        band_hi=band_hi,
    )


__all__ = [
    "DominantGap",
    "RemediationAction",
    "Stage2PassVector",
    "compute_stage2_pass_vector",
    "meta_fields_from_pass_vector",
    "pass_vector_from_loop",
    "plan_stage2_from_snapshot",
]
