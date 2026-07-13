"""Synchronous EventBus client for birth stage rollout choreography."""

from __future__ import annotations

import uuid
from typing import Any

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_choreography import publish_snapshot
from lumina_core.birth.birth_bus_serde import (
    deserialize_learning_snapshot,
    deserialize_meta_plan,
    serialize_learning_snapshot,
)
from lumina_core.birth.birth_handler_registry import BirthHandlerRegistry
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import (
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
    StallDetectionResult,
)
from lumina_core.birth.organism_autonomy import AutonomyDecision, RecoveryDispatch
from lumina_core.birth.plateau_escalator import PlateauState
from lumina_core.birth.phoenix_loop import PhoenixLoopState
from lumina_core.birth.stall_remediation import StallRemediationState


def _hold_plan(snap: LearningSnapshot | None = None) -> MetaActionPlan:
    return MetaActionPlan(
        primary=RecoveryStrategy.HOLD,
        snapshot=snap,
        rationale="bus_no_response",
    )


class BirthBusClient:
    """Facade used by stage rollout executor — no cross-module orchestration imports."""

    def __init__(
        self,
        event_bus: EventBus,
        curriculum_cfg: BirthCurriculumConfig,
        reward_cfg: BirthRewardConfig,
        *,
        registry: BirthHandlerRegistry | None = None,
    ) -> None:
        self.bus = event_bus
        self.cfg = curriculum_cfg
        self.registry = registry or BirthHandlerRegistry(
            event_bus, curriculum_cfg, reward_cfg
        )
        if not self.registry._attached:
            self.registry.attach_all()

    def emit(self, signal: str, stage: str | CurriculumStage, context: dict[str, Any]) -> str:
        cid = str(uuid.uuid4())
        stage_val = stage.value if isinstance(stage, CurriculumStage) else str(stage)
        publish_snapshot(
            self.bus,
            producer="birth.bus_client",
            correlation_id=cid,
            signal=signal,
            stage=stage_val,
            context=context,
        )
        return cid

    def _resp(self, cid: str) -> dict[str, Any]:
        return self.registry.pop_response(cid)

    @property
    def plateau_state(self) -> PlateauState:
        return self.registry.plateau.state

    @property
    def remediation_state(self) -> StallRemediationState:
        return self.registry.remediation.state

    @property
    def autonomy_state(self) -> Any:
        return self.registry.autonomy.state

    @property
    def phoenix_state(self) -> PhoenixLoopState:
        return self.registry.phoenix.state

    @property
    def meta_controller(self) -> Any:
        return self.registry.meta.controller

    @property
    def wall_adaptation_state(self) -> Any:
        return self.registry.wall_adaptation.state

    def restore_states(
        self,
        *,
        stage: CurriculumStage,
        stage_metrics: dict[str, Any] | None,
    ) -> None:
        metrics = stage_metrics if isinstance(stage_metrics, dict) else {}
        cid = self.emit("meta_restore_state", stage, {"metrics": metrics})
        self._resp(cid)
        cid = self.emit("plateau_restore_state", stage, {"metrics": metrics})
        self._resp(cid)
        cid = self.emit("remediation_restore_state", stage, {"metrics": metrics})
        self._resp(cid)
        cid = self.emit("autonomy_restore_state", stage, {"metrics": metrics})
        self._resp(cid)
        cid = self.emit("phoenix_restore_state", stage, {"metrics": metrics})
        self._resp(cid)
        cid = self.emit("wall_restore_state", stage, {"metrics": metrics})
        self._resp(cid)

    def wall_evaluate_trigger(self, stage: CurriculumStage, **ctx: Any) -> dict[str, Any] | None:
        cid = self.emit("wall_evaluate_trigger", stage, ctx)
        raw = self._resp(cid).get("trigger")
        return raw if isinstance(raw, dict) else None

    def adaptation_try_recovery(self, stage: CurriculumStage, **ctx: Any) -> dict[str, Any]:
        cid = self.emit("adaptation_try_recovery", stage, ctx)
        raw = self._resp(cid).get("adaptation")
        return raw if isinstance(raw, dict) else {"applied": False}

    def adaptation_never_stop(self, stage: CurriculumStage, **ctx: Any) -> dict[str, Any]:
        cid = self.emit("adaptation_never_stop", stage, ctx)
        raw = self._resp(cid).get("adaptation")
        return raw if isinstance(raw, dict) else {"applied": False}

    def adaptation_recovery_metrics(self, stage: CurriculumStage) -> dict[str, Any]:
        cid = self.emit("adaptation_metrics", stage, {})
        return dict(self._resp(cid).get("metrics", {}))

    def meta_observe(self, stage: CurriculumStage, **kwargs: Any) -> tuple[LearningSnapshot, StallDetectionResult]:
        context = dict(kwargs)
        context["stage"] = stage.value
        cid = self.emit("meta_observe", stage, context)
        resp = self._resp(cid)
        raw = resp.get("snapshot")
        snap = (
            deserialize_learning_snapshot(raw)
            if isinstance(raw, dict)
            else self._kwargs_to_snapshot(stage, kwargs)
        )
        stall_raw = resp.get("stall", {})
        if isinstance(stall_raw, dict) and stall_raw:
            stall = StallDetectionResult(**stall_raw)
        else:
            stall = StallDetectionResult(
                is_stalled=False,
                winrate_velocity=0.0,
                reward_velocity=0.0,
                combined_velocity=0.0,
                low_velocity_attempts=0,
                threshold=0,
            )
        return snap, stall

    def meta_metrics_payload(self, stage: CurriculumStage) -> dict[str, Any]:
        cid = self.emit("meta_metrics_payload", stage, {})
        return dict(self._resp(cid).get("metrics", {}))

    def meta_scorecard_fields(
        self, stage: CurriculumStage, plan: MetaActionPlan | None
    ) -> dict[str, Any]:
        from lumina_core.birth.birth_bus_serde import serialize_meta_plan

        cid = self.emit(
            "meta_scorecard_fields",
            stage,
            {"plan": serialize_meta_plan(plan) if plan else None},
        )
        return dict(self._resp(cid).get("scorecard", {}))

    def meta_decide(self, stage: CurriculumStage, snap: LearningSnapshot, *, trigger: str) -> MetaActionPlan:
        cid = self.emit(
            "meta_decide",
            stage,
            {"trigger": trigger, "snapshot": serialize_learning_snapshot(snap)},
        )
        resp = self._resp(cid)
        raw = resp.get("meta_plan")
        return deserialize_meta_plan(raw) if isinstance(raw, dict) else _hold_plan(snap)

    def meta_decide_pre_rollout(
        self, stage: CurriculumStage, snap: LearningSnapshot, **kwargs: Any
    ) -> MetaActionPlan:
        cid = self.emit(
            "meta_decide_pre_rollout",
            stage,
            {"snapshot": serialize_learning_snapshot(snap), **kwargs},
        )
        resp = self._resp(cid)
        raw = resp.get("meta_plan")
        return deserialize_meta_plan(raw) if isinstance(raw, dict) else _hold_plan(snap)

    def meta_decide_after_rollout(self, stage: CurriculumStage, snap: LearningSnapshot) -> MetaActionPlan:
        cid = self.emit(
            "meta_decide_after_rollout",
            stage,
            {"snapshot": serialize_learning_snapshot(snap)},
        )
        resp = self._resp(cid)
        raw = resp.get("meta_plan")
        return deserialize_meta_plan(raw) if isinstance(raw, dict) else _hold_plan(snap)

    def meta_decide_adaptation(self, stage: CurriculumStage, snap: LearningSnapshot, **kwargs: Any) -> MetaActionPlan:
        cid = self.emit(
            "meta_decide_adaptation",
            stage,
            {"snapshot": serialize_learning_snapshot(snap), **kwargs},
        )
        resp = self._resp(cid)
        raw = resp.get("meta_plan")
        return deserialize_meta_plan(raw) if isinstance(raw, dict) else _hold_plan(snap)

    def meta_decide_probe_rollout(self, stage: CurriculumStage, snap: LearningSnapshot) -> MetaActionPlan:
        cid = self.emit(
            "meta_decide_probe_rollout",
            stage,
            {"snapshot": serialize_learning_snapshot(snap)},
        )
        resp = self._resp(cid)
        raw = resp.get("meta_plan")
        return deserialize_meta_plan(raw) if isinstance(raw, dict) else _hold_plan(snap)

    def meta_decide_committed_rollout(self, stage: CurriculumStage, snap: LearningSnapshot) -> MetaActionPlan:
        cid = self.emit(
            "meta_decide_committed_rollout",
            stage,
            {"snapshot": serialize_learning_snapshot(snap)},
        )
        resp = self._resp(cid)
        raw = resp.get("meta_plan")
        return deserialize_meta_plan(raw) if isinstance(raw, dict) else _hold_plan(snap)

    def meta_on_probe_complete(
        self, stage: CurriculumStage, snap: LearningSnapshot, **kwargs: Any
    ) -> MetaActionPlan:
        cid = self.emit(
            "meta_on_probe_complete",
            stage,
            {"snapshot": serialize_learning_snapshot(snap), **kwargs},
        )
        resp = self._resp(cid)
        raw = resp.get("meta_plan")
        return deserialize_meta_plan(raw) if isinstance(raw, dict) else _hold_plan(snap)

    def meta_maybe_start_self_eval(self, stage: CurriculumStage, snap: LearningSnapshot, **kwargs: Any) -> None:
        cid = self.emit(
            "meta_maybe_start_self_eval",
            stage,
            {"snapshot": serialize_learning_snapshot(snap), **kwargs},
        )
        self._resp(cid)

    def meta_evaluate_provisional_fallback(
        self, stage: CurriculumStage, snap: LearningSnapshot, **kwargs: Any
    ) -> Any:
        cid = self.emit(
            "meta_evaluate_provisional_fallback",
            stage,
            {"snapshot": serialize_learning_snapshot(snap), **kwargs},
        )
        return self._resp(cid).get("provisional")

    def meta_apply_explore_multiplier(self, stage: CurriculumStage, explore_steps: int) -> int:
        cid = self.emit("meta_apply_explore_multiplier", stage, {"explore_steps": explore_steps})
        return int(self._resp(cid).get("explore_steps", explore_steps))

    def meta_record_inject(self, stage: CurriculumStage, **kwargs: Any) -> None:
        cid = self.emit("meta_record_inject", stage, kwargs)
        self._resp(cid)

    def meta_patch_state(self, stage: CurriculumStage, **kwargs: Any) -> None:
        cid = self.emit("meta_patch_state", stage, kwargs)
        self._resp(cid)

    def meta_format_self_eval_suffix(self, stage: CurriculumStage) -> str:
        cid = self.emit("meta_format_self_eval_suffix", stage, {})
        return str(self._resp(cid).get("suffix", ""))

    def meta_self_eval_state(self, stage: CurriculumStage) -> dict[str, Any]:
        cid = self.emit("meta_self_eval_state", stage, {})
        return dict(self._resp(cid).get("self_eval", {}))

    def detect_stall(self, stage: CurriculumStage, **kwargs: Any) -> StallDetectionResult:
        cid = self.emit("meta_detect_stall", stage, kwargs)
        raw = self._resp(cid).get("stall", {})
        if isinstance(raw, dict) and raw:
            return StallDetectionResult(**raw)
        return StallDetectionResult(
            is_stalled=False,
            winrate_velocity=0.0,
            reward_velocity=0.0,
            combined_velocity=0.0,
            low_velocity_attempts=0,
            threshold=0,
        )

    def plateau_detect_over_trading_trap(self, stage: CurriculumStage, **ctx: Any) -> bool:
        cid = self.emit("plateau_detect_over_trading_trap", stage, ctx)
        return bool(self._resp(cid).get("over_trading_trap", False))

    def plateau_check_enter(self, stage: CurriculumStage, **ctx: Any) -> bool:
        cid = self.emit("plateau_check_enter", stage, ctx)
        return bool(self._resp(cid).get("should_enter", False))

    def plateau_enter(self, stage: CurriculumStage, **ctx: Any) -> None:
        cid = self.emit("plateau_enter", stage, ctx)
        self._resp(cid)

    def plateau_should_trigger_evolution(self, stage: CurriculumStage, **ctx: Any) -> bool:
        cid = self.emit("plateau_should_trigger_evolution", stage, ctx)
        return bool(self._resp(cid).get("should_trigger", False))

    def plateau_begin_evolution_step(self, stage: CurriculumStage, **ctx: Any) -> str | None:
        cid = self.emit("plateau_begin_evolution_step", stage, ctx)
        return self._resp(cid).get("action")

    def plateau_increment_rollout(self, stage: CurriculumStage) -> None:
        cid = self.emit("plateau_increment_rollout", stage, {})
        self._resp(cid)

    def plateau_record_outcome(self, stage: CurriculumStage, **ctx: Any) -> None:
        cid = self.emit("plateau_record_outcome", stage, ctx)
        self._resp(cid)

    def remediation_should_run(self, stage: CurriculumStage, **ctx: Any) -> bool:
        cid = self.emit("remediation_should_run", stage, ctx)
        return bool(self._resp(cid).get("should_run", False))

    def remediation_can_start(self, stage: CurriculumStage) -> bool:
        cid = self.emit("remediation_can_start", stage, {})
        return bool(self._resp(cid).get("can_start", False))

    def remediation_is_exhausted(self, stage: CurriculumStage) -> bool:
        cid = self.emit("remediation_is_exhausted", stage, {})
        return bool(self._resp(cid).get("exhausted", False))

    def remediation_begin_cycle(self, stage: CurriculumStage, **ctx: Any) -> None:
        cid = self.emit("remediation_begin_cycle", stage, ctx)
        self._resp(cid)

    def remediation_begin_step(self, stage: CurriculumStage, **ctx: Any) -> str | None:
        cid = self.emit("remediation_begin_step", stage, ctx)
        return self._resp(cid).get("action")

    def remediation_should_advance(self, stage: CurriculumStage, **ctx: Any) -> bool:
        cid = self.emit("remediation_should_advance", stage, ctx)
        return bool(self._resp(cid).get("should_advance", False))

    def remediation_increment_rollout(self, stage: CurriculumStage) -> None:
        cid = self.emit("remediation_increment_rollout", stage, {})
        self._resp(cid)

    def remediation_record_outcome(self, stage: CurriculumStage, **ctx: Any) -> None:
        cid = self.emit("remediation_record_outcome", stage, ctx)
        self._resp(cid)

    def remediation_patch_state(self, stage: CurriculumStage, **ctx: Any) -> None:
        cid = self.emit("remediation_patch_state", stage, ctx)
        self._resp(cid)

    def autonomy_evaluate_terminal_stall(self, stage: CurriculumStage, **ctx: Any) -> AutonomyDecision:
        cid = self.emit("autonomy_evaluate_terminal_stall", stage, ctx)
        raw = self._resp(cid).get("autonomy", {})
        if isinstance(raw, dict) and raw:
            return AutonomyDecision(
                dispatch=RecoveryDispatch(str(raw.get("dispatch", "terminal_notify_only"))),
                needs_attention=bool(raw.get("needs_attention", False)),
                retryable=bool(raw.get("retryable", True)),
                stall_reason=str(raw.get("stall_reason", "")),
                recommended_action=str(raw.get("recommended_action", "")),
                checkpoint_patch=raw.get("checkpoint_patch"),
                autonomy_metrics=raw.get("autonomy_metrics"),
                message=str(raw.get("message", "")),
            )
        return AutonomyDecision(dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY, needs_attention=True)

    def phoenix_begin_cycle(self, stage: CurriculumStage, **ctx: Any) -> dict[str, Any] | None:
        cid = self.emit("phoenix_begin_cycle", stage, ctx)
        patch = self._resp(cid).get("patch")
        return patch if isinstance(patch, dict) else None

    @staticmethod
    def _kwargs_to_snapshot(stage: CurriculumStage, kwargs: dict[str, Any]) -> LearningSnapshot:
        return LearningSnapshot(
            winrate_history=tuple(kwargs.get("winrate_history", ())),
            reward_history=tuple(kwargs.get("reward_history", ())),
            stage_trades=int(kwargs.get("stage_trades", 0)),
            required_trades=int(kwargs.get("required_trades", 0)),
            patterns_mined=int(kwargs.get("patterns_mined", 0)),
            patterns_last_inject=int(kwargs.get("patterns_last_inject", 0)),
            oracle_wins_last_inject=int(kwargs.get("oracle_wins_last_inject", 0)),
            buffer_size=int(kwargs.get("buffer_size", 0)),
            escalation_level=int(kwargs.get("escalation_level", 0)),
            strong_recovery_mode=bool(kwargs.get("strong_recovery_mode", False)),
            strong_recovery_attempts=int(kwargs.get("strong_recovery_attempts", 0)),
            low_velocity_attempts=int(kwargs.get("low_velocity_attempts", 0)),
            data_exhausted=bool(kwargs.get("data_exhausted", False)),
            stage=stage,
            intra_hard_pct=kwargs.get("intra_hard_pct"),
            attempt=int(kwargs.get("attempt", 0)),
            range_flat_ratio=float(kwargs.get("range_flat_ratio", 0.0)),
            range_round_trips=int(kwargs.get("range_round_trips", 0)),
        )


__all__ = ["BirthBusClient"]
