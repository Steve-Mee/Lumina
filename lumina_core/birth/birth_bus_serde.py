"""Serialize/deserialize birth handler payloads for EventBus choreography."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import (
    AdaptationDecision,
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
)


def _enum_val(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def serialize_learning_snapshot(snap: LearningSnapshot) -> dict[str, Any]:
    return {
        "winrate_history": list(snap.winrate_history),
        "reward_history": list(snap.reward_history),
        "stage_trades": snap.stage_trades,
        "required_trades": snap.required_trades,
        "patterns_mined": snap.patterns_mined,
        "patterns_last_inject": snap.patterns_last_inject,
        "oracle_wins_last_inject": snap.oracle_wins_last_inject,
        "buffer_size": snap.buffer_size,
        "escalation_level": snap.escalation_level,
        "strong_recovery_mode": snap.strong_recovery_mode,
        "strong_recovery_attempts": snap.strong_recovery_attempts,
        "low_velocity_attempts": snap.low_velocity_attempts,
        "data_exhausted": snap.data_exhausted,
        "stage": snap.stage.value,
        "intra_hard_pct": snap.intra_hard_pct,
        "attempt": snap.attempt,
        "winrate_velocity": snap.winrate_velocity,
        "reward_velocity": snap.reward_velocity,
        "combined_velocity": snap.combined_velocity,
        "is_stalled": snap.is_stalled,
        "pattern_quality": snap.pattern_quality,
        "learning_health": snap.learning_health.value,
        "volume_gate_passed": snap.volume_gate_passed,
        "range_flat_ratio": snap.range_flat_ratio,
        "range_round_trips": snap.range_round_trips,
    }


def deserialize_learning_snapshot(data: dict[str, Any]) -> LearningSnapshot:
    return LearningSnapshot(
        winrate_history=tuple(float(x) for x in data.get("winrate_history", ())),
        reward_history=tuple(float(x) for x in data.get("reward_history", ())),
        stage_trades=int(data.get("stage_trades", 0)),
        required_trades=int(data.get("required_trades", 0)),
        patterns_mined=int(data.get("patterns_mined", 0)),
        patterns_last_inject=int(data.get("patterns_last_inject", 0)),
        oracle_wins_last_inject=int(data.get("oracle_wins_last_inject", 0)),
        buffer_size=int(data.get("buffer_size", 0)),
        escalation_level=int(data.get("escalation_level", 0)),
        strong_recovery_mode=bool(data.get("strong_recovery_mode", False)),
        strong_recovery_attempts=int(data.get("strong_recovery_attempts", 0)),
        low_velocity_attempts=int(data.get("low_velocity_attempts", 0)),
        data_exhausted=bool(data.get("data_exhausted", False)),
        stage=CurriculumStage(str(data.get("stage", CurriculumStage.STAGE1_TREND.value))),
        intra_hard_pct=data.get("intra_hard_pct"),
        attempt=int(data.get("attempt", 0)),
        winrate_velocity=float(data.get("winrate_velocity", 0.0)),
        reward_velocity=float(data.get("reward_velocity", 0.0)),
        combined_velocity=float(data.get("combined_velocity", 0.0)),
        is_stalled=bool(data.get("is_stalled", False)),
        pattern_quality=float(data.get("pattern_quality", 0.0)),
        learning_health=LearningHealth(str(data.get("learning_health", LearningHealth.FLAT.value))),
        volume_gate_passed=bool(data.get("volume_gate_passed", False)),
        range_flat_ratio=float(data.get("range_flat_ratio", 0.0)),
        range_round_trips=int(data.get("range_round_trips", 0)),
    )


def serialize_meta_plan(plan: MetaActionPlan) -> dict[str, Any]:
    adaptation = plan.adaptation
    reward = plan.reward_tweak
    snap = plan.snapshot
    return {
        "primary": _enum_val(plan.primary),
        "secondary": [_enum_val(s) for s in plan.secondary],
        "explore_steps": plan.explore_steps,
        "explore_fraction": plan.explore_fraction,
        "chunk_target": plan.chunk_target,
        "escalation_delta": plan.escalation_delta,
        "mine": plan.mine,
        "mine_aggressive": plan.mine_aggressive,
        "expand_data": plan.expand_data,
        "reward_tweak": asdict(reward) if reward is not None else None,
        "intra_hard_pct_delta": plan.intra_hard_pct_delta,
        "enter_strong_recovery": plan.enter_strong_recovery,
        "exit_strong_recovery": plan.exit_strong_recovery,
        "adaptation": {
            "should_retry": adaptation.should_retry,
            "reason": adaptation.reason,
            "new_chunk_target": adaptation.new_chunk_target,
            "escalation_increase": adaptation.escalation_increase,
            "log_message": adaptation.log_message,
        }
        if adaptation is not None
        else None,
        "explore_steps_multiplier": plan.explore_steps_multiplier,
        "trigger": plan.trigger,
        "rationale": plan.rationale,
        "suggest_provisional_pass": plan.suggest_provisional_pass,
        "self_eval_phase": plan.self_eval_phase,
        "committed_strategy": plan.committed_strategy,
        "snapshot": serialize_learning_snapshot(snap) if snap is not None else None,
    }


def deserialize_meta_plan(data: dict[str, Any]) -> MetaActionPlan:
    adaptation_raw = data.get("adaptation")
    adaptation: AdaptationDecision | None = None
    if isinstance(adaptation_raw, dict):
        adaptation = AdaptationDecision(
            should_retry=bool(adaptation_raw.get("should_retry", False)),
            reason=str(adaptation_raw.get("reason", "")),
            new_chunk_target=int(adaptation_raw.get("new_chunk_target", 0)),
            escalation_increase=int(adaptation_raw.get("escalation_increase", 1)),
            log_message=str(adaptation_raw.get("log_message", "")),
        )
    reward_raw = data.get("reward_tweak")
    reward: BirthRewardConfig | None = None
    if isinstance(reward_raw, dict):
        reward = BirthRewardConfig(**reward_raw)
    snap_raw = data.get("snapshot")
    snap = deserialize_learning_snapshot(snap_raw) if isinstance(snap_raw, dict) else None
    return MetaActionPlan(
        primary=RecoveryStrategy(str(data.get("primary", RecoveryStrategy.HOLD.value))),
        secondary=tuple(
            RecoveryStrategy(str(v)) for v in data.get("secondary", ())
        ),
        explore_steps=data.get("explore_steps"),
        explore_fraction=data.get("explore_fraction"),
        chunk_target=data.get("chunk_target"),
        escalation_delta=int(data.get("escalation_delta", 0)),
        mine=bool(data.get("mine", False)),
        mine_aggressive=bool(data.get("mine_aggressive", False)),
        expand_data=bool(data.get("expand_data", False)),
        reward_tweak=reward,
        intra_hard_pct_delta=data.get("intra_hard_pct_delta"),
        enter_strong_recovery=bool(data.get("enter_strong_recovery", False)),
        exit_strong_recovery=bool(data.get("exit_strong_recovery", False)),
        adaptation=adaptation,
        explore_steps_multiplier=float(data.get("explore_steps_multiplier", 1.0)),
        trigger=str(data.get("trigger", "")),
        rationale=str(data.get("rationale", "")),
        suggest_provisional_pass=bool(data.get("suggest_provisional_pass", False)),
        self_eval_phase=str(data.get("self_eval_phase", "")),
        committed_strategy=data.get("committed_strategy"),
        snapshot=snap,
    )


__all__ = [
    "deserialize_learning_snapshot",
    "deserialize_meta_plan",
    "serialize_learning_snapshot",
    "serialize_meta_plan",
]
