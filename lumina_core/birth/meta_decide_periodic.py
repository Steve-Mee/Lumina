"""meta_decide_periodic."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage, graduation_requires_clean_constitution
from lumina_core.birth.meta_controller_mixin_base import MetaControllerMixinBase
from lumina_core.birth.meta_controller_signals import (
    get_adaptation_decision,
    _hold_plan,
)
from lumina_core.birth.meta_controller_types import (
    AdaptationDecision,
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
    _with_trigger,
)


class MetaDecidePeriodicMixin:
    """decide_periodic_review."""

    def decide_periodic_review(self, snap: LearningSnapshot) -> MetaActionPlan:
        if not self.enabled:
            return _hold_plan(snap, "meta_controller_disabled")

        constitution_plan = self._constitution_remediation_plan(snap)
        if constitution_plan is not None:
            return constitution_plan

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
            # Anti-thrash: pattern inject with zero mined patterns is a dead button.
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
            primary = (
                RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE
                if mine_aggressive
                else RecoveryStrategy.PATTERN_INJECT
            )
            reward_tweak = self._apply_reward_tweak(snap)
            secondary: list[RecoveryStrategy] = [RecoveryStrategy.EXPLORE_BOOST]
            if reward_tweak is not None:
                secondary.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
            # Declining: explore UP (was left at 0.65 after improving decay — inverted).
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
