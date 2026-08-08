"""meta_decide_adaptation."""
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


class MetaDecideAdaptationMixin:
    """decide_adaptation."""

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
