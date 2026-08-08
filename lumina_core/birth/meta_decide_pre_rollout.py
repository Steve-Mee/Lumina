"""meta_decide_pre_rollout."""
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


class MetaDecidePreRolloutMixin:
    """decide_pre_rollout."""

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
            else:
                # Under-activity / chronic flat: never default to HOLD.
                flat = float(getattr(snap, "range_flat_ratio", 0.0) or 0.0)
                if flat > 0.70:
                    explore_steps = max(explore_steps, self.cfg.exploration_steps * 3)
                    primary = RecoveryStrategy.EXPLORE_BOOST
                    escalation_delta = max(escalation_delta, 1)
                    rationale = "stage2_under_activity_ban_hold"
                else:
                    # In/near band: expectancy quality stack (WR−0.50 floor).
                    from lumina_core.birth.expectancy_stall import detect_expectancy_stall

                    exp_stall = detect_expectancy_stall(
                        stage_is_range=True,
                        range_flat_ratio=flat,
                        range_total_signals=int(
                            getattr(snap, "range_total_signals", 0) or 0
                        ),
                        stage_trades=int(getattr(snap, "stage_trades", 0) or 0),
                        stage_wins=int(getattr(snap, "stage_wins", 0) or 0),
                        required=int(getattr(snap, "required", 300) or 300),
                        velocity_stall=bool(getattr(snap, "velocity_stall", False)),
                        plateau_active=bool(getattr(snap, "plateau_active", False)),
                        trades_beyond_gate=int(
                            getattr(snap, "trades_beyond_gate", 0) or 0
                        ),
                        rolling_winrate=getattr(snap, "rolling_winrate", None),
                        cfg=self.cfg,
                    )
                    if exp_stall or flat <= 0.40:
                        explore_steps = max(
                            200,
                            int(
                                self.cfg.exploration_steps
                                * float(self.cfg.strong_recovery_explore_fraction)
                            ),
                        )
                        primary = RecoveryStrategy.EXPLORE_REDUCE
                        secondary.append(RecoveryStrategy.PATTERN_INJECT)
                        escalation_delta = max(escalation_delta, 1)
                        rationale = "stage2_expectancy_quality"
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
