"""Stage-2 expectancy stall: first-class quality trap (WR−0.50 below floor).

Occupancy may be in the 30–70% band while expectancy (≡ hygiene WR) fails.
Swarming without quality remediation burns into champion freeze. This module
detects the stall and recommends a bounded recovery ladder — never lowers floors.
"""

from __future__ import annotations

from typing import Any


def stage2_expectancy_live(
    *,
    stage_trades: int,
    stage_wins: int,
    rolling_winrate: float | None = None,
) -> float:
    """WR−0.50 proxy; prefer rolling when provided."""
    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    lifetime = float(wins) / float(max(1, trades)) if trades > 0 else 0.0
    if rolling_winrate is not None:
        return max(lifetime, float(rolling_winrate)) - 0.50
    return lifetime - 0.50


def detect_expectancy_stall(
    *,
    stage_is_range: bool,
    range_flat_ratio: float,
    range_total_signals: int,
    stage_trades: int,
    stage_wins: int,
    required: int,
    velocity_stall: bool = False,
    plateau_active: bool = False,
    trades_beyond_gate: int = 0,
    rolling_winrate: float | None = None,
    cfg: Any = None,
    stage_is_mixed: bool = False,
) -> bool:
    """True when volume/activity ok-ish but expectancy below stage2/3 floor.

    Stage-3: also fire on hygiene gap (WR≪35%) even when occupancy is broken
    (flat≪30%) — live forensics skipped quality with reason=no_stall while WR~22%.
    """
    if not stage_is_range and not stage_is_mixed:
        return False
    trades = int(stage_trades)
    req = max(1, int(required))
    # Stage-3: engage quality past 50% of gate (not only full volume).
    min_tr = req if stage_is_range else max(50, req // 2)
    if trades < min_tr:
        return False
    signals = int(range_total_signals)
    flat = float(range_flat_ratio)
    # Stage-2: activity near band. Stage-3: allow under-flat (over-trade) so quality runs.
    if stage_is_range and signals >= 50 and not (0.25 <= flat <= 0.75):
        return False
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        floor = float(stage2_expectancy_floor(cfg)) if cfg is not None else -0.15
    except Exception:
        floor = float(getattr(cfg, "stage2_expectancy_floor", -0.15) or -0.15) if cfg else -0.15
    exp = stage2_expectancy_live(
        stage_trades=trades,
        stage_wins=int(stage_wins),
        rolling_winrate=rolling_winrate,
    )
    if exp >= floor - 1e-12:
        # Stage-3 hygiene: WR floor may fail even if rolling exp proxy looks OK.
        if stage_is_mixed:
            wr = float(stage_wins) / float(max(1, trades))
            wr_floor = float(getattr(cfg, "stage3_winrate_floor", 0.35) or 0.35) if cfg else 0.35
            roll = float(rolling_winrate) if rolling_winrate is not None else wr
            if max(wr, roll) + 1e-12 < wr_floor:
                return True
            if signals >= 50:
                flat_min = (
                    float(getattr(cfg, "stage3_position_flat_min", 0.25) or 0.25)
                    if cfg
                    else 0.25
                )
                if flat + 1e-12 < flat_min:
                    return True
        return False
    # Pressure: beyond gate, plateau, velocity stall, or Stage-3 hygiene crisis.
    beyond = int(trades_beyond_gate)
    if beyond > 0 or plateau_active or velocity_stall or stage_is_mixed:
        return True
    # Soft: past gate with clear gap.
    return (exp + 0.05) < floor


def recommended_expectancy_recovery_action(
    *,
    range_flat_ratio: float,
    remediation_step: int = 0,
    edge_vs_random: float | None = None,
) -> str:
    """Ordered ladder action id for meta / plateau surfaces.

    When ``edge_vs_random < 0`` (worse than first-touch random), stay on the
    quality/mine path and **never** jump to swarm until edge recovers or quality
    steps are exhausted — beat-random first (truthful intermediate milestone).
    """
    step = max(0, int(remediation_step))
    flat = float(range_flat_ratio)
    anti_edge = edge_vs_random is not None and float(edge_vs_random) < -1e-12
    if step <= 0:
        return "policy_rollback"
    if step == 1:
        return "expectancy_quality_reward"
    if step == 2:
        # Over-trade edge: reduce explore; under-flat already needs quality not more noise.
        # Anti-edge: never flood inject — beat-random owns quality first.
        if anti_edge:
            return "expectancy_quality_reward"
        return "explore_reduce" if flat <= 0.40 else "pattern_inject"
    if step == 3:
        # Live forensics: step3 pattern_inject primary diluted buffer while edge < 0.
        if anti_edge:
            return "expectancy_quality_reward"
        return "pattern_inject"
    # Anti-edge: stay on quality/reward stack — never pattern flood or swarm theater.
    if anti_edge and step < 8:
        return "expectancy_quality_reward"
    return "swarm_after_quality"


def build_expectancy_quality_meta_fields(
    *,
    range_flat_ratio: float,
    remediation_step: int,
    base_explore_steps: int,
    exploration_steps: int,
    strong_recovery_explore_fraction: float = 0.35,
    edge_vs_random: float | None = None,
) -> dict[str, Any]:
    """SSOT map for pre/periodic/after_rollout when expectancy stall owns Stage-2.

    Never returns primary explore_boost — quality first. Beat-random gap locks
    mine+quality until edge recovers.
    """
    action_id = recommended_expectancy_recovery_action(
        range_flat_ratio=float(range_flat_ratio),
        remediation_step=int(remediation_step),
        edge_vs_random=edge_vs_random,
    )
    mapped = map_expectancy_action_to_meta(
        action_id,
        base_explore_steps=int(base_explore_steps),
        exploration_steps=int(exploration_steps),
        strong_recovery_explore_fraction=float(strong_recovery_explore_fraction),
    )
    primary = str(mapped.get("primary") or "explore_reduce")
    # Hard ban: explore_boost under expectancy quality ownership.
    if primary in {"explore_boost", "EXPLORE_BOOST"}:
        primary = "explore_reduce"
        mapped["primary"] = primary
    rationale = str(mapped.get("rationale") or f"stage2_expectancy_{action_id}")
    if edge_vs_random is not None and float(edge_vs_random) < -1e-12:
        rationale = f"{rationale}_beat_random"
        # Anti-edge: quality reward + light mine, NOT pattern_inject flood as primary.
        mapped["primary"] = "explore_reduce"
        primary = "explore_reduce"
        mapped["mine"] = True
        # Prefer reward shaping over inject; inject only as last secondary (capped).
        sec = ["reward_shaping_tweak", "pattern_inject"]
        mapped["secondary"] = tuple(sec)
    return {
        "action_id": action_id,
        "primary": primary,
        "secondary": tuple(mapped.get("secondary") or ()),
        "explore_steps": int(mapped.get("explore_steps") or base_explore_steps),
        "escalation_delta": int(mapped.get("escalation_delta") or 1),
        "mine": bool(mapped.get("mine")),
        "rationale": rationale,
        "edge_vs_random": float(edge_vs_random) if edge_vs_random is not None else None,
    }


def _stage_is_range(stage: Any) -> bool:
    stage_s = str(getattr(stage, "value", stage) or "").lower()
    if stage_s in {"stage2_range", "stage2"} or ("stage2" in stage_s and "range" in stage_s):
        return True
    try:
        from lumina_core.birth.curriculum import CurriculumStage

        return stage == CurriculumStage.STAGE2_RANGE
    except Exception:
        return False


def _stage_is_mixed(stage: Any) -> bool:
    stage_s = str(getattr(stage, "value", stage) or "").lower()
    if stage_s in {"stage3_mixed", "stage3"} or ("stage3" in stage_s and "mixed" in stage_s):
        return True
    try:
        from lumina_core.birth.curriculum import CurriculumStage

        return stage == CurriculumStage.STAGE3_MIXED
    except Exception:
        return False


def snapshot_expectancy_stall(
    snap: Any,
    *,
    cfg: Any = None,
) -> bool:
    """Detect Stage-2/3 expectancy stall from a LearningSnapshot-like object."""
    stage = getattr(snap, "stage", None)
    is_range = _stage_is_range(stage)
    is_mixed = _stage_is_mixed(stage)
    if not is_range and not is_mixed:
        return False
    stage_trades = int(getattr(snap, "stage_trades", 0) or 0)
    required = int(getattr(snap, "required_trades", 0) or (500 if is_mixed else 300))
    stage_wins = int(getattr(snap, "stage_wins", 0) or 0)
    if stage_wins <= 0 and stage_trades > 0:
        wr_hist = getattr(snap, "winrate_history", ()) or ()
        if wr_hist:
            stage_wins = int(round(float(wr_hist[-1]) * max(1, stage_trades)))
    flat = float(getattr(snap, "range_flat_ratio", 0.0) or 0.0)
    range_signals = int(getattr(snap, "range_total_signals", 0) or 0)
    if range_signals <= 0:
        range_signals = max(50, int(getattr(snap, "range_round_trips", 0) or 0) * 4)
    return detect_expectancy_stall(
        stage_is_range=is_range,
        stage_is_mixed=is_mixed,
        range_flat_ratio=flat,
        range_total_signals=range_signals,
        stage_trades=stage_trades,
        stage_wins=stage_wins,
        required=required,
        velocity_stall=bool(
            getattr(snap, "velocity_stall", False)
            or int(getattr(snap, "low_velocity_attempts", 0) or 0) > 0
        ),
        plateau_active=bool(getattr(snap, "plateau_active", False)),
        trades_beyond_gate=max(0, stage_trades - required),
        rolling_winrate=getattr(snap, "rolling_winrate", None),
        cfg=cfg,
    )


def loop_expectancy_stall(loop: Any, *, cfg: Any = None) -> bool:
    """SSOT stall detection from a stage-loop session object (Stage-2 and Stage-3)."""
    try:
        from lumina_core.birth.curriculum import CurriculumStage

        stage = getattr(loop, "stage", None)
        is_range = stage == CurriculumStage.STAGE2_RANGE or _stage_is_range(stage)
        is_mixed = stage == CurriculumStage.STAGE3_MIXED or _stage_is_mixed(stage)
        if not is_range and not is_mixed:
            return False
    except Exception:
        is_range = _stage_is_range(getattr(loop, "stage", None))
        is_mixed = _stage_is_mixed(getattr(loop, "stage", None))
        if not is_range and not is_mixed:
            return False
    trades = int(getattr(loop, "stage_trades", 0) or 0)
    required = int(getattr(loop, "required", 0) or (500 if is_mixed else 300))
    wins = int(getattr(loop, "stage_wins", 0) or 0)
    signals = int(getattr(loop, "stage_range_total_signals", 0) or 0)
    flat_bars = int(getattr(loop, "stage_range_flat_bars", 0) or 0)
    flat = float(flat_bars) / float(max(1, signals)) if signals > 0 else 0.5
    rolling = None
    try:
        rolling, _, _ = loop._rolling_winrate_meta()  # type: ignore[attr-defined]
    except Exception:
        rolling = None
    cur_cfg = cfg if cfg is not None else getattr(loop, "cur_cfg", None)
    plateau = bool(getattr(getattr(loop, "plateau_state", None), "active", False))
    low_v = int(getattr(loop, "low_velocity_attempts", 0) or 0)
    thr = int(getattr(cur_cfg, "velocity_stall_attempt_threshold", 32) or 32) if cur_cfg else 32
    return detect_expectancy_stall(
        stage_is_range=is_range,
        stage_is_mixed=is_mixed,
        range_flat_ratio=flat,
        range_total_signals=signals,
        stage_trades=trades,
        stage_wins=wins,
        required=required,
        velocity_stall=low_v >= thr,
        plateau_active=plateau,
        trades_beyond_gate=max(0, trades - required),
        rolling_winrate=float(rolling) if rolling is not None else None,
        cfg=cur_cfg,
    )


def stage2_quality_owns(
    *,
    snap: Any | None = None,
    loop: Any | None = None,
    cfg: Any = None,
) -> bool:
    """True when Stage-2 expectancy quality must own recovery (no explore thrash)."""
    if snap is not None:
        return snapshot_expectancy_stall(snap, cfg=cfg)
    if loop is not None:
        return loop_expectancy_stall(loop, cfg=cfg)
    return False


def plan_is_expectancy_thrash(plan: Any) -> bool:
    """Plans that fight Stage-2/3 quality learning when stall is active."""
    primary = str(getattr(getattr(plan, "primary", None), "value", getattr(plan, "primary", "")) or "")
    rationale = str(getattr(plan, "rationale", "") or "").lower()
    if primary in {"explore_boost", "EXPLORE_BOOST"}:
        return True
    if "periodic_declining_pattern_focus_explore" in rationale:
        return True
    if "periodic_declining_empty_patterns_explore" in rationale:
        return True
    if rationale.startswith("wall_budget_exhausted"):
        return True
    if "stage2_hold_stagnation" in rationale:
        return True
    if "stage2_under_activity_ban_hold" in rationale:
        return True
    if "hold_trap_forced_explore" in rationale:
        return True
    if "stage3_hold_recovery_explore" in rationale:
        return True
    if "stage3_wr_recovery_explore" in rationale:
        return True
    if "meta_exhausted_forced_explore" in rationale:
        return True
    if "over_trading" in rationale or "suppress_churn" in rationale:
        # Not thrash — occupancy quality path (do not rewrite further).
        return False
    return False


def coerce_meta_plan_under_expectancy_quality(
    plan: Any,
    *,
    snap: Any | None = None,
    loop: Any | None = None,
    cfg: Any = None,
    exploration_steps: int | None = None,
    strong_recovery_explore_fraction: float | None = None,
) -> Any:
    """Rewrite thrash plans to quality ladder when stall owns Stage-2.

    Fail-closed: never returns explore_boost under quality ownership.
    """
    owns = stage2_quality_owns(snap=snap, loop=loop, cfg=cfg)
    if not owns:
        return plan
    if plan is not None and not plan_is_expectancy_thrash(plan):
        # Already a non-thrash plan — keep, but strip any explore_boost secondary.
        primary = str(getattr(getattr(plan, "primary", None), "value", getattr(plan, "primary", "")) or "")
        if primary not in {"explore_boost", "EXPLORE_BOOST"}:
            if "stage2_expectancy" in str(getattr(plan, "rationale", "") or "").lower():
                try:
                    from dataclasses import replace

                    sec = tuple(
                        s
                        for s in (getattr(plan, "secondary", ()) or ())
                        if str(getattr(s, "value", s)) != "explore_boost"
                    )
                    if sec != getattr(plan, "secondary", ()):
                        return replace(plan, secondary=sec)
                except Exception:
                    pass
                return plan
            # Non-thrash but not quality (e.g. HOLD) — still force quality under stall.
            if primary in {"hold", "HOLD"} and snap is not None:
                pass  # fall through to build quality
            elif primary not in {"hold", "HOLD"}:
                try:
                    from dataclasses import replace

                    sec = tuple(
                        s
                        for s in (getattr(plan, "secondary", ()) or ())
                        if str(getattr(s, "value", s)) != "explore_boost"
                    )
                    if sec != getattr(plan, "secondary", ()):
                        return replace(plan, secondary=sec)
                except Exception:
                    pass
                return plan

    flat = 0.5
    quality_step = 0
    if snap is not None:
        flat = float(getattr(snap, "range_flat_ratio", 0.5) or 0.5)
        quality_step = int(getattr(snap, "expectancy_quality_step", 0) or 0)
        if quality_step <= 0:
            quality_step = max(0, int(getattr(snap, "escalation_level", 0) or 0))
    elif loop is not None:
        signals = int(getattr(loop, "stage_range_total_signals", 0) or 0)
        flat_bars = int(getattr(loop, "stage_range_flat_bars", 0) or 0)
        flat = float(flat_bars) / float(max(1, signals)) if signals > 0 else 0.5
        quality_step = int(getattr(loop, "expectancy_quality_step", 0) or 0)
        if quality_step <= 0:
            quality_step = max(0, int(getattr(loop, "escalation_level", 0) or 0))

    exp_steps = int(
        exploration_steps
        if exploration_steps is not None
        else getattr(cfg, "exploration_steps", 2000)
        if cfg is not None
        else 2000
    )
    frac = float(
        strong_recovery_explore_fraction
        if strong_recovery_explore_fraction is not None
        else getattr(cfg, "strong_recovery_explore_fraction", 0.35)
        if cfg is not None
        else 0.35
    )
    edge_vr = None
    if snap is not None:
        try:
            raw_e = getattr(snap, "edge_vs_random", None)
            edge_vr = float(raw_e) if raw_e is not None else None
        except (TypeError, ValueError):
            edge_vr = None
    elif loop is not None:
        try:
            raw_e = getattr(loop, "_edge_vs_random", None)
            edge_vr = float(raw_e) if raw_e is not None else None
        except (TypeError, ValueError):
            edge_vr = None
    fields = build_expectancy_quality_meta_fields(
        range_flat_ratio=flat,
        remediation_step=quality_step,
        base_explore_steps=exp_steps,
        exploration_steps=exp_steps,
        strong_recovery_explore_fraction=frac,
        edge_vs_random=edge_vr,
    )
    try:
        from lumina_core.birth.meta_controller_types import MetaActionPlan, RecoveryStrategy

        secondary: list[Any] = []
        for sec in fields.get("secondary") or ():
            try:
                secondary.append(RecoveryStrategy(str(sec)))
            except ValueError:
                continue
        # Strip explore_boost from secondary under quality ownership.
        secondary = [s for s in secondary if str(getattr(s, "value", s)) != "explore_boost"]
        return MetaActionPlan(
            primary=RecoveryStrategy(str(fields["primary"])),
            secondary=tuple(dict.fromkeys(secondary)),
            explore_steps=int(fields["explore_steps"]),
            mine=bool(fields.get("mine")),
            escalation_delta=int(fields.get("escalation_delta") or 1),
            explore_steps_multiplier=max(
                0.4,
                min(
                    1.0,
                    float(getattr(cfg, "meta_explore_decay_stall", 0.5) if cfg is not None else 0.5),
                ),
            ),
            rationale=str(fields.get("rationale") or "stage2_expectancy_coerced"),
            snapshot=snap if snap is not None else getattr(plan, "snapshot", None),
        )
    except Exception:
        return plan


def apply_pre_rollout_quality_coerce(
    plan: Any,
    *,
    loop: Any,
    cfg: Any = None,
    base_explore_steps: int = 2000,
) -> Any:
    """Rewrite hold_trap / stage3 / exhausted explore_boost after pre-rollout overwrites.

    Fail-closed: under quality ownership, never returns explore_boost. Explore
    budget follows the quality ladder, not 4× entropy dump.
    """
    snap = getattr(plan, "snapshot", None) if plan is not None else None
    exp_steps = int(base_explore_steps)
    frac = 0.35
    if cfg is not None:
        try:
            exp_steps = int(getattr(cfg, "exploration_steps", base_explore_steps) or base_explore_steps)
        except (TypeError, ValueError):
            exp_steps = int(base_explore_steps)
        try:
            frac = float(getattr(cfg, "strong_recovery_explore_fraction", 0.35) or 0.35)
        except (TypeError, ValueError):
            frac = 0.35
    return coerce_meta_plan_under_expectancy_quality(
        plan,
        loop=loop,
        snap=snap,
        cfg=cfg,
        exploration_steps=exp_steps,
        strong_recovery_explore_fraction=frac,
    )


def map_expectancy_action_to_meta(
    action_id: str,
    *,
    base_explore_steps: int,
    exploration_steps: int,
    strong_recovery_explore_fraction: float = 0.35,
) -> dict[str, Any]:
    """Map quality-ladder action id → meta RecoveryStrategy plan fields.

    Never lowers floors. ``policy_rollback`` is surface-only (plateau owns weights);
    meta applies explore_reduce + quality reward shaping as the concurrent stack.
    """
    aid = str(action_id or "").strip().lower()
    explore_floor = max(
        200,
        int(float(exploration_steps) * float(strong_recovery_explore_fraction)),
    )
    if aid in {"policy_rollback", "expectancy_quality_reward"}:
        return {
            "primary": "explore_reduce",
            "secondary": ("reward_shaping_tweak", "pattern_inject"),
            "explore_steps": explore_floor,
            "escalation_delta": 1,
            "mine": True,
            "rationale": f"stage2_expectancy_{aid}",
        }
    if aid == "explore_reduce":
        return {
            "primary": "explore_reduce",
            "secondary": ("reward_shaping_tweak",),
            "explore_steps": explore_floor,
            "escalation_delta": 1,
            "mine": False,
            "rationale": "stage2_expectancy_explore_reduce",
        }
    if aid == "pattern_inject":
        return {
            "primary": "pattern_inject",
            "secondary": ("explore_reduce", "reward_shaping_tweak"),
            "explore_steps": max(int(base_explore_steps), explore_floor),
            "escalation_delta": 1,
            "mine": True,
            "rationale": "stage2_expectancy_pattern_inject",
        }
    # swarm_after_quality: meta stays conservative; plateau owns swarm timing.
    return {
        "primary": "explore_reduce",
        "secondary": ("pattern_inject", "reward_shaping_tweak"),
        "explore_steps": explore_floor,
        "escalation_delta": 1,
        "mine": True,
        "rationale": "stage2_expectancy_swarm_after_quality",
    }


def stage2_should_defer_swarm_for_expectancy(
    *,
    expectancy_stall: bool,
    remediation_step: int,
    max_quality_steps: int = 4,
    evolution_step: int = 0,
    cfg: Any = None,
    edge_vs_random: float | None = None,
) -> bool:
    """Defer swarm while quality ladder still has budget (mirror flat-band defer).

    Also defers while ``edge_vs_random < 0`` (beat-random lock) until quality
    steps are exhausted — swarm must not claim lift on anti-edge policies.
    """
    if not expectancy_stall:
        return False
    max_steps = int(
        getattr(cfg, "stage2_expectancy_quality_max_steps", max_quality_steps)
        if cfg is not None
        else max_quality_steps
    )
    max_steps = max(1, min(12, max_steps))
    # Beat-random: never swarm while worse than first-touch random and quality budget left.
    if edge_vs_random is not None and float(edge_vs_random) < -1e-12:
        if int(remediation_step) < max_steps:
            return True
    # Allow swarm only after quality steps exhausted or evolution past defer window.
    defer_steps = int(
        getattr(cfg, "stage2_expectancy_swarm_defer_steps", 2) if cfg is not None else 2
    )
    if int(remediation_step) < max_steps and int(evolution_step) < max(1, defer_steps):
        return True
    return False


def should_stage2_early_quality_hard_stop(
    *,
    stage_is_range: bool,
    stage_trades: int,
    required: int,
    range_flat_ratio: float,
    stage_wins: int,
    rolling_winrate: float | None = None,
    range_total_signals: int = 0,
    cfg: Any = None,
) -> bool:
    """H1: stop Stage-2 overshoot when past gate and early-quality already dead.

    Does **not** lower floors. Fires well before trades-beyond-gate multiplier
    (audit: 900 trades past gate with flat 27% + exp −0.30).
    """
    if not stage_is_range:
        return False
    trades = int(stage_trades)
    req = max(1, int(required))
    if trades < req:
        return False
    beyond = trades - req
    min_beyond = int(
        getattr(cfg, "stage2_early_abort_min_beyond", 50) if cfg is not None else 50
    )
    min_beyond = max(0, min_beyond)
    if beyond < min_beyond:
        return False

    flat = float(range_flat_ratio)
    flat_out_of_band = not (0.30 <= flat <= 0.70)
    # Soft margin needs enough signals to trust flat ratio
    if int(range_total_signals) < 50:
        flat_out_of_band = False

    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        exp_floor = float(stage2_expectancy_floor(cfg)) if cfg is not None else -0.15
    except Exception:
        exp_floor = float(getattr(cfg, "stage2_expectancy_floor", -0.15) or -0.15) if cfg else -0.15

    exp = stage2_expectancy_live(
        stage_trades=trades,
        stage_wins=int(stage_wins),
        rolling_winrate=rolling_winrate,
    )
    expectancy_dead = exp < (exp_floor - 1e-12)

    hygiene_floor = float(
        getattr(cfg, "stage2_hygiene_wr_floor", 0.35) if cfg is not None else 0.35
    )
    lifetime_wr = float(stage_wins) / float(max(1, trades))
    wr = float(rolling_winrate) if rolling_winrate is not None else lifetime_wr
    hygiene_dead = wr + 1e-12 < hygiene_floor

    exp_stall = detect_expectancy_stall(
        stage_is_range=True,
        range_flat_ratio=flat,
        range_total_signals=int(range_total_signals),
        stage_trades=trades,
        stage_wins=int(stage_wins),
        required=req,
        trades_beyond_gate=beyond,
        rolling_winrate=rolling_winrate,
        cfg=cfg,
    )

    # Multi-metric: need at least two independent quality failures (or exp stall + flat).
    fails = sum(
        1
        for flag in (flat_out_of_band, expectancy_dead, hygiene_dead, exp_stall)
        if flag
    )
    return fails >= 2


__all__ = [
    "build_expectancy_quality_meta_fields",
    "coerce_meta_plan_under_expectancy_quality",
    "apply_pre_rollout_quality_coerce",
    "detect_expectancy_stall",
    "loop_expectancy_stall",
    "map_expectancy_action_to_meta",
    "plan_is_expectancy_thrash",
    "recommended_expectancy_recovery_action",
    "snapshot_expectancy_stall",
    "stage2_expectancy_live",
    "stage2_quality_owns",
    "stage2_should_defer_swarm_for_expectancy",
    "should_stage2_early_quality_hard_stop",
]
