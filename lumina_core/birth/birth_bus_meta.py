"""Meta-controller façade methods for BirthBusClient (global residual)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import (
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
    StallDetectionResult,
)
from lumina_core.birth.birth_bus_serde import (
    deserialize_learning_snapshot,
    deserialize_meta_plan,
    serialize_learning_snapshot,
)


def _hold_plan(snap: LearningSnapshot | None = None) -> MetaActionPlan:
    return MetaActionPlan(
        primary=RecoveryStrategy.HOLD,
        snapshot=snap,
        rationale="bus_no_response",
    )

class BirthBusMetaMixin:
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
