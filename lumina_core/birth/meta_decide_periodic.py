"""meta_decide_periodic."""
from __future__ import annotations

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller_signals import (
    _hold_plan,
)
from lumina_core.birth.meta_controller_types import (
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.meta_decide_periodic")


class MetaDecidePeriodicMixin:
    """decide_periodic_review."""

    def _stage2_expectancy_quality_plan(self, snap: LearningSnapshot) -> MetaActionPlan | None:
        """Return quality ladder plan when stall owns Stage-2; never silent-fail to thrash."""
        from lumina_core.birth.expectancy_stall import (
            build_expectancy_quality_meta_fields,
            snapshot_expectancy_stall,
        )

        from lumina_core.birth.runtime_diagnostics import log_meta_decision_trace

        if not snapshot_expectancy_stall(snap, cfg=self.cfg):
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
            base_explore_steps=int(self.cfg.exploration_steps),
            exploration_steps=int(self.cfg.exploration_steps),
            strong_recovery_explore_fraction=float(self.cfg.strong_recovery_explore_fraction),
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
        reward_tweak = self._apply_reward_tweak(snap)
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
                0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
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

    def decide_periodic_review(self, snap: LearningSnapshot) -> MetaActionPlan:
        if not self.enabled:
            return _hold_plan(snap, "meta_controller_disabled")

        constitution_plan = self._constitution_remediation_plan(snap)
        if constitution_plan is not None:
            return constitution_plan

        # Stage-1 foundation pressure (learning target, not survival pass floor).
        try:
            if (
                snap.stage == CurriculumStage.STAGE1_TREND
                and bool(getattr(snap, "volume_gate_passed", False))
                and bool(getattr(self.cfg, "stage1_foundation_pressure_enabled", True))
            ):
                from lumina_core.birth.stage1_foundation import (
                    compute_stage1_foundation,
                    stage1_foundation_meta_fields,
                )

                s1 = compute_stage1_foundation(
                    stage_trades=int(getattr(snap, "stage_trades", 0) or 0),
                    stage_wins=int(getattr(snap, "stage_wins", 0) or 0),
                    required=int(getattr(snap, "required_trades", 200) or 200),
                    survival_wr_floor=float(
                        getattr(self.cfg, "birth_survival_wr_floor", 0.20) or 0.20
                    ),
                    foundation_target_wr=float(
                        getattr(self.cfg, "stage1_foundation_target_wr", 0.30) or 0.30
                    ),
                    anti_thrash_wr=float(
                        getattr(self.cfg, "stage1_anti_thrash_wr", 0.25) or 0.25
                    ),
                    edge_vs_random=getattr(snap, "edge_vs_random", None),
                    rolling_winrate=getattr(snap, "rolling_winrate", None),
                )
                s1f = stage1_foundation_meta_fields(
                    s1,
                    exploration_steps=int(self.cfg.exploration_steps),
                    strong_recovery_explore_fraction=float(
                        self.cfg.strong_recovery_explore_fraction
                    ),
                    median_loss_r=getattr(snap, "median_loss_r", None),
                )
                if s1f is not None:
                    secondary_s1: list[RecoveryStrategy] = []
                    for sec in s1f.get("secondary") or ():
                        try:
                            s = RecoveryStrategy(str(sec))
                        except ValueError:
                            continue
                        if s == RecoveryStrategy.EXPLORE_BOOST:
                            continue
                        secondary_s1.append(s)
                    plan_s1 = MetaActionPlan(
                        primary=RecoveryStrategy(
                            str(s1f.get("primary") or "explore_reduce")
                        ),
                        secondary=tuple(dict.fromkeys(secondary_s1)),
                        explore_steps=int(
                            s1f.get("explore_steps") or self.cfg.exploration_steps
                        ),
                        mine=bool(s1f.get("mine")),
                        escalation_delta=int(s1f.get("escalation_delta") or 1),
                        explore_steps_multiplier=max(
                            0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                        ),
                        rationale=str(
                            s1f.get("rationale") or "stage1_foundation_periodic"
                        ),
                        snapshot=snap,
                    )
                    self._record_plan(plan_s1)
                    return plan_s1
        except Exception as s1_exc:
            logger.debug("birth.meta.stage1_foundation periodic skip: %s", s1_exc)

        # Stage-2 pass-vector single controller, then expectancy quality.
        try:
            from lumina_core.birth.stage2_pass_vector import plan_stage2_from_snapshot

            pv_fields = plan_stage2_from_snapshot(snap, cfg=self.cfg)
            if pv_fields is not None and str(pv_fields.get("primary") or "") not in {
                "",
                "hold",
            }:
                secondary_pv: list[RecoveryStrategy] = []
                for sec in pv_fields.get("secondary") or ():
                    try:
                        s = RecoveryStrategy(str(sec))
                    except ValueError:
                        continue
                    if s == RecoveryStrategy.EXPLORE_BOOST:
                        continue
                    secondary_pv.append(s)
                primary_s = str(pv_fields.get("primary") or "explore_reduce")
                if primary_s in {"explore_boost", "EXPLORE_BOOST"}:
                    primary_s = "explore_reduce"
                plan_pv = MetaActionPlan(
                    primary=RecoveryStrategy(primary_s),
                    secondary=tuple(dict.fromkeys(secondary_pv)),
                    explore_steps=int(
                        pv_fields.get("explore_steps") or self.cfg.exploration_steps
                    ),
                    mine=bool(pv_fields.get("mine")),
                    escalation_delta=int(pv_fields.get("escalation_delta") or 1),
                    explore_steps_multiplier=float(
                        pv_fields.get("explore_steps_multiplier")
                        or max(0.4, min(1.0, float(self.cfg.meta_explore_decay_stall)))
                    ),
                    rationale=str(pv_fields.get("rationale") or "pass_vector_periodic"),
                    snapshot=snap,
                )
                self.explore_multiplier = max(
                    0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                )
                self._record_plan(plan_pv)
                return plan_pv
        except Exception as pv_exc:
            logger.debug("birth.meta.pass_vector periodic skip: %s", pv_exc)

        # Stage-2 expectancy stall owns recovery: never explore_boost thrash.
        try:
            quality_plan = self._stage2_expectancy_quality_plan(snap)
            if quality_plan is not None:
                self.explore_multiplier = max(
                    0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                )
                self._record_plan(quality_plan)
                return quality_plan
        except Exception as exc:
            logger.warning(
                "birth.meta.expectancy_quality path=error trigger=periodic err=%s — fail-closed quality",
                exc,
            )
            # Fail-closed: still try a minimal quality plan rather than declining thrash.
            try:
                from lumina_core.birth.expectancy_stall import build_expectancy_quality_meta_fields

                fields = build_expectancy_quality_meta_fields(
                    range_flat_ratio=float(getattr(snap, "range_flat_ratio", 0.5) or 0.5),
                    remediation_step=max(0, int(getattr(snap, "escalation_level", 0) or 0)),
                    base_explore_steps=int(self.cfg.exploration_steps),
                    exploration_steps=int(self.cfg.exploration_steps),
                    strong_recovery_explore_fraction=float(
                        self.cfg.strong_recovery_explore_fraction
                    ),
                )
                plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_REDUCE,
                    secondary=(RecoveryStrategy.REWARD_SHAPING_TWEAK,),
                    explore_steps=int(fields["explore_steps"]),
                    mine=True,
                    rationale="stage2_expectancy_failclosed",
                    snapshot=snap,
                    explore_steps_multiplier=max(
                        0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                    ),
                )
                self._record_plan(plan)
                return plan
            except Exception as exc2:
                logger.error("birth.meta.expectancy_quality failclosed_failed: %s", exc2)

        if snap.learning_health == LearningHealth.IMPROVING:
            secondary: list[RecoveryStrategy] = []
            intra_delta: float | None = None
            decay = max(
                0.4,
                min(1.0, float(self.cfg.meta_explore_decay_improving)),
            )
            rationale = "periodic_improving_explore_decay"
            if (
                self.cfg.meta_intra_ramp_on_improving
                and snap.stage == CurriculumStage.STAGE1_TREND
                and snap.intra_hard_pct is not None
                and snap.intra_hard_pct < self.cfg.intra_max_hard_pct
            ):
                intra_delta = float(self.cfg.intra_hard_pct_step)
                secondary.append(RecoveryStrategy.INTRA_RAMP)
                rationale = "periodic_improving_ramp_and_decay"
            plan = MetaActionPlan(
                primary=RecoveryStrategy.EXPLORE_REDUCE,
                secondary=tuple(secondary),
                explore_steps_multiplier=decay,
                intra_hard_pct_delta=intra_delta,
                rationale=rationale,
                snapshot=snap,
            )
            self.explore_multiplier = decay
            self._record_plan(plan)
            return plan

        if snap.learning_health == LearningHealth.DECLINING:
            # Stage-2 with volume past gate but stall not flagged: still ban explore thrash
            # when flat in band and WR clearly under quality floor.
            try:
                from lumina_core.birth.expectancy_stall import stage2_expectancy_live

                if (
                    snap.stage == CurriculumStage.STAGE2_RANGE
                    and snap.volume_gate_passed
                    and 0.25 <= float(snap.range_flat_ratio or 0.0) <= 0.75
                ):
                    exp = stage2_expectancy_live(
                        stage_trades=int(snap.stage_trades),
                        stage_wins=int(getattr(snap, "stage_wins", 0) or 0),
                        rolling_winrate=getattr(snap, "rolling_winrate", None),
                    )
                    if exp < -0.15:
                        q = self._stage2_expectancy_quality_plan(snap)
                        if q is not None:
                            self._record_plan(q)
                            return q
            except Exception:
                pass

            empty_patterns = int(getattr(snap, "patterns_mined", 0) or 0) <= 0
            past_gate = int(snap.stage_trades) >= max(1, int(snap.required_trades))
            if empty_patterns and past_gate and not snap.data_exhausted:
                plan = MetaActionPlan(
                    primary=RecoveryStrategy.DATA_EXPANSION,
                    secondary=(RecoveryStrategy.INTRA_EASE,),
                    expand_data=True,
                    intra_hard_pct_delta=-float(self.cfg.intra_hard_pct_step),
                    rationale="periodic_declining_empty_patterns_expand",
                    snapshot=snap,
                )
                self._record_plan(plan)
                return plan
            if empty_patterns and past_gate:
                # Prefer reduce+mine over explore_boost on Stage-2/3 quality path.
                if snap.stage in (
                    CurriculumStage.STAGE2_RANGE,
                    CurriculumStage.STAGE3_MIXED,
                ):
                    plan = MetaActionPlan(
                        primary=RecoveryStrategy.EXPLORE_REDUCE,
                        secondary=(RecoveryStrategy.PATTERN_INJECT,),
                        mine=True,
                        explore_steps_multiplier=max(
                            0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                        ),
                        rationale="stage2_declining_empty_patterns_quality"
                        if snap.stage == CurriculumStage.STAGE2_RANGE
                        else "stage3_declining_empty_patterns_quality",
                        snapshot=snap,
                    )
                else:
                    plan = MetaActionPlan(
                        primary=RecoveryStrategy.EXPLORE_BOOST,
                        secondary=(RecoveryStrategy.INTRA_EASE,),
                        explore_steps_multiplier=min(1.5, float(self.explore_multiplier) * 1.2),
                        intra_hard_pct_delta=-float(self.cfg.intra_hard_pct_step),
                        rationale="periodic_declining_empty_patterns_explore",
                        snapshot=snap,
                    )
                self._record_plan(plan)
                return plan
            mine = True
            mine_aggressive = snap.pattern_quality < float(self.cfg.meta_pattern_yield_floor)
            if (
                (
                    snap.stage == CurriculumStage.STAGE2_RANGE
                    and snap.volume_gate_passed
                )
                or snap.stage == CurriculumStage.STAGE3_MIXED
            ):
                # Never secondary explore_boost on Stage-2/3 past quality gate.
                primary = (
                    RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE
                    if mine_aggressive
                    else RecoveryStrategy.PATTERN_INJECT
                )
                reward_tweak = self._apply_reward_tweak(snap)
                secondary_s2: list[RecoveryStrategy] = [RecoveryStrategy.EXPLORE_REDUCE]
                if reward_tweak is not None:
                    secondary_s2.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
                plan = MetaActionPlan(
                    primary=primary,
                    secondary=tuple(secondary_s2),
                    mine=mine,
                    mine_aggressive=mine_aggressive,
                    reward_tweak=reward_tweak,
                    explore_steps_multiplier=max(
                        0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                    ),
                    rationale="stage3_declining_pattern_quality_focus"
                    if snap.stage == CurriculumStage.STAGE3_MIXED
                    else "stage2_declining_pattern_quality_focus",
                    snapshot=snap,
                )
                self.explore_multiplier = max(
                    0.4, min(1.0, float(self.cfg.meta_explore_decay_stall))
                )
                self._record_plan(plan)
                return plan
            flat_pd = float(getattr(snap, "range_flat_ratio", 0.5) or 0.5)
            signals_pd = int(getattr(snap, "range_total_signals", 0) or 0)
            # Over-trading: never inject+explore_boost thrash (Stage-2/3 occupancy).
            if signals_pd >= 50 and flat_pd < 0.25:
                reward_tweak = self._apply_reward_tweak(snap)
                secondary_ot: list[RecoveryStrategy] = []
                if reward_tweak is not None:
                    secondary_ot.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
                plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_REDUCE,
                    secondary=tuple(secondary_ot),
                    mine=False,
                    mine_aggressive=False,
                    reward_tweak=reward_tweak,
                    explore_steps_multiplier=min(
                        1.0, max(0.35, float(self.explore_multiplier) * 0.85)
                    ),
                    rationale=(
                        "periodic_over_trading_suppress_churn"
                        if "stage3" in str(getattr(snap.stage, "value", snap.stage)).lower()
                        else "periodic_over_trading_suppress_churn"
                    ),
                    snapshot=snap,
                )
                self._record_plan(plan)
                return plan
            primary = (
                RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE
                if mine_aggressive
                else RecoveryStrategy.PATTERN_INJECT
            )
            reward_tweak = self._apply_reward_tweak(snap)
            secondary = [RecoveryStrategy.EXPLORE_BOOST]
            if reward_tweak is not None:
                secondary.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
            explore_mult = min(1.5, max(1.15, float(self.explore_multiplier) * 1.25))
            plan = MetaActionPlan(
                primary=primary,
                secondary=tuple(secondary),
                mine=mine,
                mine_aggressive=mine_aggressive,
                reward_tweak=reward_tweak,
                explore_steps_multiplier=explore_mult,
                rationale="periodic_declining_pattern_focus_explore",
                snapshot=snap,
            )
            self.explore_multiplier = min(1.0, max(0.85, float(self.explore_multiplier) * 1.15))
            try:
                from lumina_core.birth.runtime_diagnostics import log_meta_decision_trace

                log_meta_decision_trace(
                    trigger="periodic",
                    primary=plan.primary.value,
                    rationale=plan.rationale,
                    secondary=[s.value for s in plan.secondary],
                    stage=str(getattr(snap.stage, "value", snap.stage)),
                    stage_trades=int(snap.stage_trades),
                    stage_wins=int(getattr(snap, "stage_wins", 0) or 0),
                    flat=float(getattr(snap, "range_flat_ratio", 0.0) or 0.0),
                    stall=False,
                    coerced=False,
                    source="decide_periodic_declining_thrash",
                )
            except Exception:
                pass
            self._record_plan(plan)
            return plan

        if (
            snap.learning_health == LearningHealth.FLAT
            and snap.stage == CurriculumStage.STAGE1_TREND
            and snap.intra_hard_pct is not None
            and snap.intra_hard_pct > self.cfg.intra_initial_hard_pct
        ):
            plan = MetaActionPlan(
                primary=RecoveryStrategy.INTRA_EASE,
                intra_hard_pct_delta=-float(self.cfg.intra_hard_pct_step),
                rationale="periodic_flat_intra_ease",
                snapshot=snap,
            )
            self._record_plan(plan)
            return plan

        if snap.thin_buffer and not snap.data_exhausted:
            plan = MetaActionPlan(
                primary=RecoveryStrategy.DATA_EXPANSION,
                expand_data=True,
                rationale="periodic_thin_buffer_expand",
                snapshot=snap,
            )
            self._record_plan(plan)
            return plan

        return _hold_plan(snap, "periodic_no_action_needed")
