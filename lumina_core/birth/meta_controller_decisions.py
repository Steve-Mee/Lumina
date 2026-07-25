"""Meta-controller recovery decision trees (mixin)."""
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


class MetaControllerDecisionsMixin(MetaControllerMixinBase):
    """Decision methods for BirthMetaController (expects controller attributes on self)."""

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

    def decide_pre_rollout(
        self,
        snap: LearningSnapshot,
        *,
        base_explore_steps: int,
        wall_budget_exhausted: bool,
        winrate_stagnation_count: int,
        hold_stagnation_count: int,
        over_trading_trap: bool = False,
    ) -> MetaActionPlan:
        if not self.enabled:
            return MetaActionPlan(
                primary=RecoveryStrategy.HOLD,
                explore_steps=base_explore_steps,
                snapshot=snap,
            )

        constitution_plan = self._constitution_remediation_plan(snap)
        if constitution_plan is not None:
            return constitution_plan

        explore_steps = base_explore_steps
        explore_fraction: float | None = None
        escalation_delta = 0
        primary = RecoveryStrategy.HOLD
        secondary: list[RecoveryStrategy] = []
        rationale = "default_rollout"

        if snap.strong_recovery_mode:
            explore_fraction = float(self.cfg.strong_recovery_explore_fraction)
            explore_steps = max(
                200,
                int(self.cfg.exploration_steps * explore_fraction),
            )
            primary = RecoveryStrategy.EXPLORE_REDUCE
            rationale = "strong_recovery_exploit"
        elif wall_budget_exhausted:
            explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
            primary = RecoveryStrategy.EXPLORE_BOOST
            escalation_delta = 1
            rationale = "wall_budget_exhausted"
        elif (
            snap.stage == CurriculumStage.STAGE2_RANGE
            and snap.volume_gate_passed
            and hold_stagnation_count >= self.cfg.stage2_hold_stagnation_rollouts
        ):
            explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
            primary = RecoveryStrategy.EXPLORE_BOOST
            escalation_delta = 1
            rationale = "stage2_hold_stagnation"
        elif snap.stage == CurriculumStage.STAGE2_RANGE and snap.volume_gate_passed:
            if over_trading_trap:
                explore_steps = max(
                    200,
                    int(self.cfg.exploration_steps * self.cfg.strong_recovery_explore_fraction),
                )
                primary = RecoveryStrategy.EXPLORE_REDUCE
                escalation_delta = 1
                rationale = "stage2_over_trading"
        elif (
            snap.stage == CurriculumStage.STAGE1_TREND
            and snap.volume_gate_passed
            and winrate_stagnation_count >= self.cfg.stage1_winrate_stagnation_rollouts
        ):
            explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
            primary = RecoveryStrategy.EXPLORE_BOOST
            secondary.append(RecoveryStrategy.PATTERN_INJECT)
            escalation_delta = 1
            rationale = "stage1_winrate_stagnation"

        if snap.learning_health == LearningHealth.IMPROVING and not snap.strong_recovery_mode:
            escalation_delta = min(escalation_delta, -1)

        return MetaActionPlan(
            primary=primary,
            secondary=tuple(secondary),
            explore_steps=explore_steps,
            explore_fraction=explore_fraction,
            escalation_delta=escalation_delta,
            mine=RecoveryStrategy.PATTERN_INJECT in secondary,
            rationale=rationale,
            snapshot=snap,
        )

    def decide_after_rollout(self, snap: LearningSnapshot) -> MetaActionPlan:
        if not self.enabled:
            return _hold_plan(snap, "meta_controller_disabled")

        constitution_plan = self._constitution_remediation_plan(snap)
        if constitution_plan is not None:
            return constitution_plan

        # Proactive twin call (primary auto-approval layer) — best effort.
        # Triggers TwinDecisionEvent on bus when a usable DNA-like context exists.
        # In birth we synthesize a minimal PolicyDNA proxy from snapshot for scoring.
        if self.approval_twin is not None:
            try:
                from lumina_core.evolution.dna_registry import PolicyDNA
                proxy_content = {
                    "birth_stage": getattr(snap, "stage", None),
                    "winrate": float(getattr(snap, "winrate_velocity", 0.0) or 0.0),
                    "trades": int(getattr(snap, "stage_trades", 0) or 0),
                }
                proxy_dna = PolicyDNA.create(
                    prompt_id="birth_meta_proxy",
                    version="birth",
                    content=proxy_content,
                    fitness_score=float(snap.winrate_velocity or 0.5),
                    generation=0,
                    mutation_rate=0.05,
                    lineage_hash="birth",
                )
                _ = self.approval_twin.evaluate_dna_promotion(proxy_dna)
                # Twin signal only. Real DNA paths always enforce via ConstitutionalGuard + sandbox (see ADR-0032 + constitution invariant 1).
            except Exception:
                pass  # never break meta decision

        if snap.learning_health == LearningHealth.IMPROVING and snap.volume_gate_passed:
            reward_tweak = self._apply_reward_tweak(snap)
            if snap.strong_recovery_mode:
                return MetaActionPlan(
                    primary=RecoveryStrategy.HOLD,
                    exit_strong_recovery=True,
                    chunk_target=max(
                        self.cfg.exploration_chunk_size,
                        self.cfg.rollout_chunk_trades,
                    ),
                    reward_tweak=reward_tweak,
                    rationale="velocity_recovered",
                    snapshot=snap,
                )
            return MetaActionPlan(
                primary=RecoveryStrategy.HOLD,
                reward_tweak=reward_tweak,
                rationale="improving_learning",
                snapshot=snap,
            )

        if not snap.is_stalled:
            return _hold_plan(snap)

        primary = RecoveryStrategy.EXPLORE_BOOST
        secondary: list[RecoveryStrategy] = []
        mine = False
        mine_aggressive = False
        expand_data = False
        enter_strong = False
        escalation_delta = 0
        chunk_target: int | None = None
        intra_delta: float | None = None
        reward_tweak: BirthRewardConfig | None = None
        rationale = "velocity_stall"

        if snap.thin_buffer and not snap.data_exhausted:
            primary = RecoveryStrategy.DATA_EXPANSION
            expand_data = True
            rationale = "stall_thin_buffer_expand_data"
        elif (
            snap.pattern_quality < float(self.cfg.meta_pattern_yield_floor)
            and int(getattr(snap, "patterns_mined", 0) or 0) <= 0
            and int(snap.stage_trades) >= max(1, int(snap.required_trades))
        ):
            # Anti-thrash: low pattern yield with zero mined patterns = dead inject button.
            if not snap.data_exhausted:
                primary = RecoveryStrategy.DATA_EXPANSION
                expand_data = True
                secondary.append(RecoveryStrategy.INTRA_EASE)
                rationale = "stall_empty_patterns_expand"
            else:
                primary = RecoveryStrategy.EXPLORE_BOOST
                secondary.append(RecoveryStrategy.INTRA_EASE)
                rationale = "stall_empty_patterns_explore"
        elif snap.pattern_quality < float(self.cfg.meta_pattern_yield_floor):
            primary = RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE
            mine = True
            mine_aggressive = True
            rationale = "stall_low_pattern_yield"
        elif snap.volume_gate_passed:
            primary = RecoveryStrategy.EXPLORE_REDUCE
            enter_strong = True
            escalation_delta = int(self.cfg.strong_recovery_escalation_boost)
            chunk_target = max(
                self.cfg.exploration_chunk_size,
                self.cfg.exploration_chunk_size * 2,
            )
            mine = True
            mine_aggressive = True
            rationale = "stall_enter_strong_recovery"
        else:
            primary = RecoveryStrategy.EXPLORE_BOOST
            secondary.append(RecoveryStrategy.PATTERN_INJECT)
            mine = True
            escalation_delta = 1
            rationale = "stall_pre_volume_gate"

        if (
            snap.pattern_quality >= float(self.cfg.meta_pattern_yield_floor)
            and snap.winrate_velocity <= 0.0
        ):
            secondary.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
            reward_tweak = self._apply_reward_tweak(snap)

        if (
            snap.learning_health == LearningHealth.FLAT
            and snap.volume_gate_passed
            and snap.stage == CurriculumStage.STAGE1_TREND
            and snap.intra_hard_pct is not None
            and snap.intra_hard_pct > self.cfg.intra_initial_hard_pct
        ):
            intra_delta = -float(self.cfg.intra_hard_pct_step)
            secondary.append(RecoveryStrategy.INTRA_EASE)

        if snap.strong_recovery_mode:
            expand_every = int(self.cfg.strong_recovery_expand_every_attempts)
            if snap.strong_recovery_attempts > 0 and snap.strong_recovery_attempts % expand_every == 0:
                expand_data = True
                mine = True
                mine_aggressive = True
                if RecoveryStrategy.DATA_EXPANSION not in secondary:
                    secondary.append(RecoveryStrategy.DATA_EXPANSION)

        plan = MetaActionPlan(
            primary=primary,
            secondary=tuple(dict.fromkeys(secondary)),
            chunk_target=chunk_target,
            escalation_delta=escalation_delta,
            mine=mine,
            mine_aggressive=mine_aggressive,
            expand_data=expand_data,
            reward_tweak=reward_tweak,
            intra_hard_pct_delta=intra_delta,
            enter_strong_recovery=enter_strong and not snap.strong_recovery_mode,
            explore_steps_multiplier=1.0 if enter_strong else self.explore_multiplier,
            rationale=rationale,
            snapshot=snap,
        )
        if enter_strong and not snap.strong_recovery_mode:
            self.explore_multiplier = max(
                0.4,
                min(1.0, float(self.cfg.meta_explore_decay_stall)),
            )
        self._record_plan(plan)
        return plan

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
            secondary: list[RecoveryStrategy] = []
            if reward_tweak is not None:
                secondary.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
            plan = MetaActionPlan(
                primary=primary,
                secondary=tuple(secondary),
                mine=mine,
                mine_aggressive=mine_aggressive,
                reward_tweak=reward_tweak,
                rationale="periodic_declining_pattern_focus",
                snapshot=snap,
            )
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

    @staticmethod
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

    def decide_adaptation(
        self,
        snap: LearningSnapshot,
        *,
        winrate: float,
        escalation_level: int,
        adaptation_tier: int,
        retries_this_stage: int,
        original_rollout_chunk: int,
        failure_key: str,
    ) -> MetaActionPlan:
        adaptation = get_adaptation_decision(
            stage_trades=snap.stage_trades,
            required=snap.required_trades,
            winrate=winrate,
            winrate_history=list(snap.winrate_history),
            escalation_level=escalation_level,
            cfg=self.cfg,
        )
        if not adaptation.should_retry and adaptation_tier == 0 and retries_this_stage == 0:
            adaptation = AdaptationDecision(
                should_retry=True,
                reason="stall_escalation",
                new_chunk_target=max(
                    self.cfg.exploration_chunk_size,
                    min(self.cfg.rollout_chunk_trades * 2, original_rollout_chunk),
                ),
                escalation_increase=1,
                log_message="Escalation ladder: forced recovery at stall boundary",
            )
        if not adaptation.should_retry and adaptation_tier >= 1:
            adaptation = AdaptationDecision(
                should_retry=True,
                reason="persistent_recovery",
                new_chunk_target=max(
                    self.cfg.exploration_chunk_size,
                    self.cfg.rollout_chunk_trades,
                ),
                escalation_increase=0,
                log_message=(
                    f"Persistent recovery tier {adaptation_tier + 1}/"
                    f"{self.cfg.max_adaptation_tiers}"
                ),
            )

        mine = adaptation_tier >= 1
        expand_data = adaptation_tier >= 2 and self.cfg.auto_expand_on_adaptation
        secondary: list[RecoveryStrategy] = [RecoveryStrategy.ADAPTATION_RETRY]
        if mine:
            secondary.append(RecoveryStrategy.PATTERN_INJECT)
        if expand_data:
            secondary.append(RecoveryStrategy.DATA_EXPANSION)

        plan = MetaActionPlan(
            primary=RecoveryStrategy.ADAPTATION_RETRY,
            secondary=tuple(secondary),
            chunk_target=adaptation.new_chunk_target if adaptation.should_retry else None,
            escalation_delta=adaptation.escalation_increase if adaptation.should_retry else 0,
            mine=mine,
            expand_data=expand_data,
            adaptation=adaptation if adaptation.should_retry else None,
            rationale=f"adaptation_{failure_key}",
            snapshot=snap,
        )
        if adaptation.should_retry:
            self._record_plan(plan)
        return plan

    def scorecard_fields(self, plan: MetaActionPlan | None = None) -> dict[str, Any]:
        snap = plan.snapshot if plan and plan.snapshot else None
        return {
            **self.metrics_payload(),
            "meta_primary_strategy": (
                plan.primary.value if plan else RecoveryStrategy.HOLD.value
            ),
            "meta_learning_health": (
                snap.learning_health.value if snap else LearningHealth.FLAT.value
            ),
            "meta_pattern_quality": snap.pattern_quality if snap else 0.0,
            "meta_explore_multiplier": round(float(self.explore_multiplier), 4),
            "meta_review_trigger": str(self.last_review_trigger),
        }
