"""meta_controller_decisions core residual methods."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.birth.curriculum import graduation_requires_clean_constitution
from lumina_core.birth.meta_controller_signals import (
    _hold_plan,
)
from lumina_core.birth.meta_controller_types import (
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
    _with_trigger,
)


class MetaControllerDecisionsCore:
    """Residual decide/helpers."""

    def _constitution_remediation_plan(self, snap: LearningSnapshot) -> MetaActionPlan | None:
        if snap.constitution_violations <= 0 or not snap.volume_gate_passed:
            return None
        if not graduation_requires_clean_constitution(snap.stage):
            return None
        reward_tweak = self._apply_reward_tweak(snap)
        if reward_tweak is None:
            step = float(self.cfg.meta_reward_tweak_step)
            cap = float(self.cfg.meta_max_expectancy_coeff)
            new_coeff = min(cap, self.active_reward.expectancy_coeff + step)
            if new_coeff > self.active_reward.expectancy_coeff:
                reward_tweak = replace(self.active_reward, expectancy_coeff=new_coeff)
        explore_steps = max(
            200,
            int(self.cfg.exploration_steps * self.cfg.strong_recovery_explore_fraction),
        )
        return MetaActionPlan(
            primary=RecoveryStrategy.EXPLORE_REDUCE,
            secondary=(RecoveryStrategy.REWARD_SHAPING_TWEAK,),
            explore_steps=explore_steps,
            reward_tweak=reward_tweak,
            rationale="constitution_remediation",
            snapshot=snap,
        )
    def _apply_reward_tweak(self, snap: LearningSnapshot) -> BirthRewardConfig | None:
        if snap.learning_health == LearningHealth.IMPROVING:
            if self.reward_tweak_active:
                self.active_reward = replace(self.baseline_reward)
                return replace(self.baseline_reward)
            return None
        if (
            snap.learning_health == LearningHealth.DECLINING
            and snap.reward_velocity < 0.0
            and snap.volume_gate_passed
        ):
            step = float(self.cfg.meta_reward_tweak_step)
            cap = float(self.cfg.meta_max_expectancy_coeff)
            new_coeff = min(cap, self.active_reward.expectancy_coeff + step)
            if new_coeff > self.active_reward.expectancy_coeff:
                self.active_reward = replace(self.active_reward, expectancy_coeff=new_coeff)
                return replace(self.active_reward)
        return None
    def decide_review(
        self,
        snap: LearningSnapshot,
        *,
        trigger: str,
        base_explore_steps: int = 0,
        wall_budget_exhausted: bool = False,
        winrate_stagnation_count: int = 0,
        hold_stagnation_count: int = 0,
    ) -> MetaActionPlan:
        self.last_review_trigger = str(trigger)
        self.rollouts_since_review = 0
        if trigger == "pre_rollout":
            plan = self.decide_pre_rollout(
                snap,
                base_explore_steps=base_explore_steps,
                wall_budget_exhausted=wall_budget_exhausted,
                winrate_stagnation_count=winrate_stagnation_count,
                hold_stagnation_count=hold_stagnation_count,
            )
            return _with_trigger(plan, trigger)
        if trigger == "stall":
            if snap.is_stalled or snap.strong_recovery_mode:
                plan = self.decide_after_rollout(snap)
            else:
                plan = self.decide_periodic_review(snap)
            return _with_trigger(plan, trigger)
        if trigger == "adaptation":
            return _hold_plan(snap, "adaptation_handled_separately")
        plan = self.decide_periodic_review(snap)
        return _with_trigger(plan, trigger)
    def format_decision_log(plan: MetaActionPlan, *, trigger: str = "") -> dict[str, Any]:
        snap = plan.snapshot
        return {
            "trigger": trigger or plan.trigger,
            "primary": plan.primary.value,
            "secondary": [s.value for s in plan.secondary],
            "rationale": plan.rationale,
            "learning_health": snap.learning_health.value if snap else LearningHealth.FLAT.value,
            "combined_velocity": round(snap.combined_velocity, 6) if snap else 0.0,
            "winrate_velocity": round(snap.winrate_velocity, 6) if snap else 0.0,
            "reward_velocity": round(snap.reward_velocity, 6) if snap else 0.0,
            "pattern_quality": snap.pattern_quality if snap else 0.0,
            "is_stalled": bool(snap.is_stalled) if snap else False,
            "actions": {
                "mine": plan.mine,
                "mine_aggressive": plan.mine_aggressive,
                "expand_data": plan.expand_data,
                "enter_strong_recovery": plan.enter_strong_recovery,
                "exit_strong_recovery": plan.exit_strong_recovery,
                "explore_steps_multiplier": round(plan.explore_steps_multiplier, 4),
                "intra_hard_pct_delta": plan.intra_hard_pct_delta,
                "escalation_delta": plan.escalation_delta,
            },
        }
    def apply_explore_multiplier(self, explore_steps: int) -> int:
        mult = max(0.4, min(1.0, float(self.explore_multiplier)))
        return max(200, int(explore_steps * mult))
    def scorecard_fields(self, plan: MetaActionPlan | None = None) -> dict[str, Any]:
        snap = plan.snapshot if plan and plan.snapshot else None
        primary = plan.primary.value if plan else RecoveryStrategy.HOLD.value
        # Stage2 over-flat: HOLD is anti-participation theater — surface explore.
        try:
            if (
                snap is not None
                and getattr(snap, "stage", None) is not None
                and str(getattr(snap.stage, "value", snap.stage)) == "stage2_range"
                and float(getattr(snap, "range_flat_ratio", 0.0) or 0.0) > 0.70
                and primary == RecoveryStrategy.HOLD.value
            ):
                primary = RecoveryStrategy.EXPLORE_BOOST.value
        except Exception:
            pass
        return {
            **self.metrics_payload(),
            "meta_primary_strategy": primary,
            "meta_learning_health": (
                snap.learning_health.value if snap else LearningHealth.FLAT.value
            ),
            "meta_pattern_quality": snap.pattern_quality if snap else 0.0,
            "meta_explore_multiplier": round(float(self.explore_multiplier), 4),
            "meta_review_trigger": str(self.last_review_trigger),
        }
