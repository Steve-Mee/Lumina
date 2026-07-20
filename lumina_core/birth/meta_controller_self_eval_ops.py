"""Meta-controller self-eval lifecycle ops (mixin)."""
from __future__ import annotations

from dataclasses import replace

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.birth.meta_controller_mixin_base import MetaControllerMixinBase
from lumina_core.birth.meta_controller_signals import _hold_plan, _recovery_from_str
from lumina_core.birth.meta_controller_types import (
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
)
from lumina_core.birth.meta_self_eval import (
    ProvisionalFallbackResult,
    SelfEvalPhase,
    SelfEvalState,
    StrategyProbeResult,
    build_probe_queue,
    score_probe_result,
    select_winner,
    should_start_self_eval,
)


class MetaControllerSelfEvalMixin(MetaControllerMixinBase):
    """Self-eval state machine methods for BirthMetaController."""

    def is_self_eval_active(self) -> bool:
        if not self.cfg.meta_self_eval_enabled:
            return False
        return self.self_eval.phase in (
            SelfEvalPhase.PROBING,
            SelfEvalPhase.COMMITTED,
            SelfEvalPhase.EXHAUSTED,
        )

    def maybe_start_self_eval(
        self,
        snap: LearningSnapshot,
        *,
        strong_recovery_attempts: int,
        attempt: int,
    ) -> bool:
        if not should_start_self_eval(
            snap,
            self.self_eval,
            self.cfg,
            strong_recovery_attempts=strong_recovery_attempts,
            attempt=attempt,
        ):
            return False
        queue = build_probe_queue(snap, self.cfg)
        if not queue:
            return False
        self.self_eval = SelfEvalState(
            phase=SelfEvalPhase.PROBING,
            probe_queue=list(queue),
            current_strategy=queue[0],
            rollouts_in_probe=0,
            velocity_at_probe_start=snap.combined_velocity,
        )
        self.self_eval_history.append(
            {
                "event": "started",
                "attempt": attempt,
                "queue": list(queue),
                "velocity": round(snap.combined_velocity, 6),
            }
        )
        if len(self.self_eval_history) > 20:
            self.self_eval_history = self.self_eval_history[-20:]
        return True

    def _plan_for_recovery_strategy(
        self,
        strategy: str,
        snap: LearningSnapshot,
        *,
        for_probe: bool = False,
    ) -> MetaActionPlan:
        primary = _recovery_from_str(strategy)
        mine = False
        mine_aggressive = False
        expand_data = False
        escalation_delta = 0
        explore_mult = self.explore_multiplier
        intra_delta: float | None = None
        reward_tweak: BirthRewardConfig | None = None
        rationale = f"self_eval_{strategy}"

        if primary == RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE:
            mine = True
            mine_aggressive = True
            rationale = "self_eval_pattern_inject_aggressive"
        elif primary == RecoveryStrategy.EXPLORE_BOOST:
            escalation_delta = 1
            explore_mult = 1.0
            rationale = "self_eval_explore_boost"
        elif primary == RecoveryStrategy.REWARD_SHAPING_TWEAK:
            reward_tweak = self._apply_reward_tweak(snap)
            if reward_tweak is None and snap.volume_gate_passed:
                step = float(self.cfg.meta_reward_tweak_step)
                cap = float(self.cfg.meta_max_expectancy_coeff)
                new_coeff = min(cap, self.active_reward.expectancy_coeff + step)
                if new_coeff > self.active_reward.expectancy_coeff:
                    self.active_reward = replace(
                        self.active_reward, expectancy_coeff=new_coeff
                    )
                    reward_tweak = replace(self.active_reward)
            rationale = "self_eval_reward_shaping_tweak"
        elif primary == RecoveryStrategy.DATA_EXPANSION:
            expand_data = True
            rationale = "self_eval_data_expansion"
        elif primary == RecoveryStrategy.INTRA_EASE:
            intra_delta = -float(self.cfg.intra_hard_pct_step)
            rationale = "self_eval_intra_ease"
        elif primary == RecoveryStrategy.EXPLORE_REDUCE:
            explore_mult = max(
                0.4,
                min(1.0, float(self.cfg.meta_explore_decay_stall)),
            )
            rationale = "self_eval_explore_reduce"

        if for_probe and primary == RecoveryStrategy.EXPLORE_REDUCE:
            explore_mult = max(0.4, min(1.0, float(self.cfg.meta_explore_decay_stall)))

        return MetaActionPlan(
            primary=primary,
            escalation_delta=escalation_delta,
            mine=mine,
            mine_aggressive=mine_aggressive,
            expand_data=expand_data,
            reward_tweak=reward_tweak,
            intra_hard_pct_delta=intra_delta,
            explore_steps_multiplier=explore_mult,
            rationale=rationale,
            snapshot=snap,
            self_eval_phase=self.self_eval.phase.value,
            committed_strategy=self.self_eval.committed_strategy,
        )

    def decide_probe_rollout(self, snap: LearningSnapshot) -> MetaActionPlan:
        if self.self_eval.phase != SelfEvalPhase.PROBING or not self.self_eval.current_strategy:
            return _hold_plan(snap, "self_eval_not_probing")
        plan = self._plan_for_recovery_strategy(
            self.self_eval.current_strategy,
            snap,
            for_probe=True,
        )
        self._record_plan(plan)
        return plan

    def on_probe_rollout_complete(
        self,
        snap: LearningSnapshot,
        *,
        attempt: int,
    ) -> MetaActionPlan | None:
        if self.self_eval.phase == SelfEvalPhase.COMMITTED:
            if snap.learning_health == LearningHealth.IMPROVING and snap.volume_gate_passed:
                self.self_eval = SelfEvalState(
                    cooldown_until_attempt=self.self_eval.cooldown_until_attempt,
                )
            return None

        if self.self_eval.phase == SelfEvalPhase.EXHAUSTED:
            return MetaActionPlan(
                primary=RecoveryStrategy.HOLD,
                suggest_provisional_pass=True,
                rationale="self_eval_exhausted",
                snapshot=snap,
                self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
            )

        if self.self_eval.phase != SelfEvalPhase.PROBING:
            return None

        self.self_eval.rollouts_in_probe += 1
        per_strategy = int(self.cfg.meta_self_eval_rollouts_per_strategy)
        if self.self_eval.rollouts_in_probe < per_strategy:
            return None

        completed = self.self_eval.current_strategy or ""
        delta = score_probe_result(
            velocity_start=self.self_eval.velocity_at_probe_start,
            velocity_end=snap.combined_velocity,
        )
        self.self_eval.probe_results.append(
            StrategyProbeResult(
                strategy=completed,
                rollouts=per_strategy,
                velocity_start=self.self_eval.velocity_at_probe_start,
                velocity_end=snap.combined_velocity,
                velocity_delta=delta,
                combined_at_end=snap.combined_velocity,
            )
        )
        self.self_eval_history.append(
            {
                "event": "probe_complete",
                "strategy": completed,
                "velocity_delta": round(delta, 6),
                "combined_at_end": round(snap.combined_velocity, 6),
            }
        )
        if len(self.self_eval_history) > 20:
            self.self_eval_history = self.self_eval_history[-20:]

        if self.self_eval.probe_queue and self.self_eval.probe_queue[0] == completed:
            self.self_eval.probe_queue = self.self_eval.probe_queue[1:]
        else:
            self.self_eval.probe_queue = [
                s for s in self.self_eval.probe_queue if s != completed
            ]

        if self.self_eval.probe_queue:
            self.self_eval.current_strategy = self.self_eval.probe_queue[0]
            self.self_eval.rollouts_in_probe = 0
            self.self_eval.velocity_at_probe_start = snap.combined_velocity
            return None

        winner = select_winner(self.self_eval.probe_results, self.cfg)
        if winner:
            self.self_eval.phase = SelfEvalPhase.COMMITTED
            self.self_eval.committed_strategy = winner
            self.self_eval.current_strategy = None
            self.self_eval.rollouts_in_probe = 0
            self.self_eval_history.append({"event": "committed", "strategy": winner})
            return self._plan_for_recovery_strategy(winner, snap)

        self.self_eval.phase = SelfEvalPhase.EXHAUSTED
        self.self_eval.pending_provisional = True
        self.self_eval.cooldown_until_attempt = attempt + int(
            self.cfg.meta_self_eval_cooldown_rollouts
        )
        self.self_eval.current_strategy = None
        self.self_eval_history.append({"event": "exhausted"})
        return MetaActionPlan(
            primary=RecoveryStrategy.HOLD,
            suggest_provisional_pass=True,
            rationale="self_eval_no_winner",
            snapshot=snap,
            self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
        )

    def decide_committed_rollout(self, snap: LearningSnapshot) -> MetaActionPlan:
        if (
            self.self_eval.phase != SelfEvalPhase.COMMITTED
            or not self.self_eval.committed_strategy
        ):
            return _hold_plan(snap, "self_eval_not_committed")
        plan = self._plan_for_recovery_strategy(
            self.self_eval.committed_strategy,
            snap,
        )
        plan = MetaActionPlan(
            primary=plan.primary,
            secondary=plan.secondary,
            explore_steps=plan.explore_steps,
            explore_fraction=plan.explore_fraction,
            chunk_target=plan.chunk_target,
            escalation_delta=plan.escalation_delta,
            mine=plan.mine,
            mine_aggressive=plan.mine_aggressive,
            expand_data=plan.expand_data,
            reward_tweak=plan.reward_tweak,
            intra_hard_pct_delta=plan.intra_hard_pct_delta,
            explore_steps_multiplier=plan.explore_steps_multiplier,
            rationale=plan.rationale,
            snapshot=snap,
            self_eval_phase=SelfEvalPhase.COMMITTED.value,
            committed_strategy=self.self_eval.committed_strategy,
        )
        self._record_plan(plan)
        return plan

    def evaluate_provisional_fallback(
        self,
        snap: LearningSnapshot,
        *,
        allow_provisional: bool,
        strong_recovery_attempts: int,
        stage_trades: int,
        required: int,
        attempt: int,
        patterns_mined: int,
        buffer_size: int,
        constitution_violations: int,
    ) -> ProvisionalFallbackResult:
        exhausted = self.self_eval.phase == SelfEvalPhase.EXHAUSTED
        if not exhausted and not self.self_eval.pending_provisional:
            return ProvisionalFallbackResult(
                should_grant=False,
                reason="",
                blocked_reason="self_eval_not_exhausted",
                safeguards={"self_eval_exhausted": False},
            )

        from lumina_core.birth.curriculum import should_gen0_soft_pass

        soft_pass_eligible = should_gen0_soft_pass(
            stage_trades=stage_trades,
            buffer_size=buffer_size,
            attempt=attempt,
            cfg=self.cfg,
        ) or (patterns_mined >= 100 and buffer_size >= 256)
        recovery_met = (
            strong_recovery_attempts >= self.cfg.strong_recovery_no_improvement_threshold
            or exhausted
        )
        safeguards = {
            "allow_provisional": allow_provisional,
            "constitution_clean": constitution_violations == 0,
            "volume_gate_passed": stage_trades >= required,
            "recovery_attempts_met": recovery_met,
            "velocity_still_low": snap.combined_velocity <= self.cfg.velocity_stall_epsilon,
            "soft_pass_eligible": soft_pass_eligible,
            "self_eval_exhausted": exhausted,
        }
        if not allow_provisional:
            return ProvisionalFallbackResult(
                should_grant=False,
                reason="",
                blocked_reason="certified_mode_strict",
                safeguards=safeguards,
            )
        if all(
            (
                safeguards["constitution_clean"],
                safeguards["volume_gate_passed"],
                safeguards["recovery_attempts_met"],
                safeguards["velocity_still_low"],
                safeguards["soft_pass_eligible"],
                safeguards["self_eval_exhausted"],
            )
        ):
            return ProvisionalFallbackResult(
                should_grant=True,
                reason="self_eval_exhausted_soft_pass",
                blocked_reason=None,
                safeguards=safeguards,
            )
        blocked_reason = next(
            (
                key
                for key, ok in (
                    ("constitution_clean", safeguards["constitution_clean"]),
                    ("volume_gate_passed", safeguards["volume_gate_passed"]),
                    ("recovery_attempts_met", safeguards["recovery_attempts_met"]),
                    ("velocity_still_low", safeguards["velocity_still_low"]),
                    ("soft_pass_eligible", safeguards["soft_pass_eligible"]),
                    ("self_eval_exhausted", safeguards["self_eval_exhausted"]),
                )
                if not ok
            ),
            "safeguard_failed",
        )
        return ProvisionalFallbackResult(
            should_grant=False,
            reason="",
            blocked_reason=blocked_reason,
            safeguards=safeguards,
        )

    def format_self_eval_suffix(self) -> str:
        se = self.self_eval
        if se.phase == SelfEvalPhase.IDLE:
            return ""
        per = int(self.cfg.meta_self_eval_rollouts_per_strategy)
        if se.phase == SelfEvalPhase.PROBING and se.current_strategy:
            delta = 0.0
            if se.probe_results:
                delta = se.probe_results[-1].velocity_delta
            return (
                f" · self-eval: probing {se.current_strategy} "
                f"({se.rollouts_in_probe}/{per}) · velocity Δ={delta:+.4f}"
            )
        if se.phase == SelfEvalPhase.COMMITTED and se.committed_strategy:
            return f" · self-eval: committed {se.committed_strategy}"
        if se.phase == SelfEvalPhase.EXHAUSTED:
            return " · self-eval: exhausted (provisional considered)"
        return ""
