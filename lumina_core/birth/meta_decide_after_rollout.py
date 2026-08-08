"""meta_decide_after_rollout."""
from __future__ import annotations


from lumina_core.birth.config import BirthRewardConfig
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


class MetaDecideAfterRolloutMixin:
    """decide_after_rollout."""

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
