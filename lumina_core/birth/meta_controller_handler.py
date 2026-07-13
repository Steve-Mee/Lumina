"""MetaControllerHandler — EventBus owner for birth meta-controller decisions."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any
from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import (
    BirthMetaPlan,
    BirthPlateauTrapDetected,
    BirthStageRolloutSnapshot,
)
from lumina_core.birth.birth_bus_choreography import TOPIC_META_PLAN, TOPIC_SNAPSHOT
from lumina_core.birth.birth_bus_serde import (
    deserialize_learning_snapshot,
    deserialize_meta_plan,
    serialize_learning_snapshot,
    serialize_meta_plan,
)
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import (
    BirthMetaController,
    LearningSnapshot,
    MetaActionPlan,
    detect_stall,
)

logger = logging.getLogger("lumina.birth.meta_controller_handler")


class MetaControllerHandler:
    """Subscribes to rollout snapshots and plateau trap facts; publishes meta plans."""

    def __init__(
        self,
        event_bus: EventBus,
        cfg: BirthCurriculumConfig,
        reward: BirthRewardConfig,
        *,
        registry: Any | None = None,
    ) -> None:
        if event_bus is None:
            raise ValueError("MetaControllerHandler requires EventBus")
        self.bus = event_bus
        self.cfg = cfg
        self.controller = BirthMetaController(cfg, reward)
        self._registry = registry
        self._token: str | None = None
        self._trap_token: str | None = None
        self._over_trading_trap = False

    def attach(self) -> str:
        if self._token is None:
            self._token = self.bus.subscribe(TOPIC_SNAPSHOT, self._on_snapshot)
        if self._trap_token is None:
            self._trap_token = self.bus.subscribe(
                "birth.plateau.trap.detected", self._on_trap_detected
            )
        return self._token or ""

    def detach(self) -> None:
        for token in (self._token, self._trap_token):
            if token:
                try:
                    self.bus.unsubscribe(token)
                except Exception:
                    pass
        self._token = None
        self._trap_token = None

    def _on_trap_detected(self, event: DomainEvent) -> None:
        try:
            trap = event.typed_payload(BirthPlateauTrapDetected)
        except Exception:
            return
        self._over_trading_trap = bool(trap.detected)

    def _set_response(self, correlation_id: str, key: str, value: Any) -> None:
        if self._registry is not None and hasattr(self._registry, "set_response"):
            self._registry.set_response(correlation_id, key, value)

    def _publish_plan(self, correlation_id: str, plan: MetaActionPlan, trigger: str) -> None:
        payload = BirthMetaPlan(
            correlation_id=correlation_id,
            trigger=trigger,
            plan=serialize_meta_plan(plan),
        )
        self.bus.publish(
            topic=TOPIC_META_PLAN,
            producer="birth.meta_controller_handler",
            payload=payload.model_dump(mode="json"),
            metadata={"correlation_id": correlation_id},
        )
        self._set_response(correlation_id, "meta_plan", serialize_meta_plan(plan))

    def _on_snapshot(self, event: DomainEvent) -> None:
        try:
            snap_evt = event.typed_payload(BirthStageRolloutSnapshot)
        except Exception as exc:
            logger.warning("meta_handler.snapshot_schema_violation: %s", exc)
            return

        cid = snap_evt.correlation_id
        signal = snap_evt.signal
        ctx = snap_evt.context

        try:
            if signal == "meta_restore_state":
                self.controller.restore_state(ctx.get("metrics"))
                self._set_response(cid, "ok", True)
            elif signal == "meta_observe":
                observed, stall = self.controller.observe(
                    winrate_history=list(ctx.get("winrate_history", [])),
                    reward_history=list(ctx.get("reward_history", [])),
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    required_trades=int(ctx.get("required_trades", 0)),
                    patterns_mined=int(ctx.get("patterns_mined", 0)),
                    buffer_size=int(ctx.get("buffer_size", 0)),
                    escalation_level=int(ctx.get("escalation_level", 0)),
                    strong_recovery_mode=bool(ctx.get("strong_recovery_mode", False)),
                    strong_recovery_attempts=int(ctx.get("strong_recovery_attempts", 0)),
                    low_velocity_attempts=int(ctx.get("low_velocity_attempts", 0)),
                    data_exhausted=bool(ctx.get("data_exhausted", False)),
                    stage=CurriculumStage(str(ctx.get("stage", CurriculumStage.STAGE1_TREND.value))),
                    intra_hard_pct=ctx.get("intra_hard_pct"),
                    attempt=int(ctx.get("attempt", 0)),
                    range_flat_ratio=float(ctx.get("range_flat_ratio", 0.0)),
                    range_round_trips=int(ctx.get("range_round_trips", 0)),
                    oos_proxy_history=ctx.get("oos_proxy_history"),
                )
                self._set_response(cid, "snapshot", serialize_learning_snapshot(observed))
                self._set_response(cid, "stall", asdict(stall))
            elif signal == "meta_metrics_payload":
                self._set_response(cid, "metrics", self.controller.metrics_payload())
            elif signal == "meta_scorecard_fields":
                plan_raw = ctx.get("plan")
                plan = (
                    deserialize_meta_plan(plan_raw) if isinstance(plan_raw, dict) else None
                )
                self._set_response(cid, "scorecard", self.controller.scorecard_fields(plan))
            elif signal == "meta_decide":
                snap = self._build_snapshot(ctx.get("snapshot", {}))
                trigger = str(ctx.get("trigger", "periodic"))
                plan = self.controller.decide_review(snap, trigger=trigger)
                self._publish_plan(cid, plan, trigger)
            elif signal == "meta_decide_pre_rollout":
                snap = self._build_snapshot(ctx.get("snapshot", {}))
                plan = self.controller.decide_pre_rollout(
                    snap,
                    base_explore_steps=int(ctx.get("base_explore_steps", 0)),
                    wall_budget_exhausted=bool(ctx.get("wall_budget_exhausted", False)),
                    winrate_stagnation_count=int(ctx.get("winrate_stagnation_count", 0)),
                    hold_stagnation_count=int(ctx.get("hold_stagnation_count", 0)),
                    over_trading_trap=self._over_trading_trap,
                )
                self._publish_plan(cid, plan, "pre_rollout")
            elif signal == "meta_decide_after_rollout":
                snap = self._build_snapshot(ctx.get("snapshot", {}))
                plan = self.controller.decide_after_rollout(snap)
                self._publish_plan(cid, plan, "after_rollout")
            elif signal == "meta_decide_adaptation":
                snap = self._build_snapshot(ctx.get("snapshot", {}))
                plan = self.controller.decide_adaptation(
                    snap,
                    winrate=float(ctx.get("winrate", 0.0)),
                    escalation_level=int(ctx.get("escalation_level", 0)),
                    adaptation_tier=int(ctx.get("adaptation_tier", 0)),
                    retries_this_stage=int(ctx.get("retries_this_stage", 0)),
                    original_rollout_chunk=int(ctx.get("original_rollout_chunk", 0)),
                    failure_key=str(ctx.get("failure_key", "")),
                )
                self._publish_plan(cid, plan, "adaptation")
            elif signal == "meta_decide_probe_rollout":
                snap = self._build_snapshot(ctx.get("snapshot", {}))
                plan = self.controller.decide_probe_rollout(snap)
                self._publish_plan(cid, plan, "probe_rollout")
            elif signal == "meta_decide_committed_rollout":
                snap = self._build_snapshot(ctx.get("snapshot", {}))
                plan = self.controller.decide_committed_rollout(snap)
                self._publish_plan(cid, plan, "committed_rollout")
            elif signal == "meta_on_probe_complete":
                snap = self._build_snapshot(ctx.get("snapshot", {}))
                plan = self.controller.on_probe_rollout_complete(
                    snap,
                    probe_winrate=float(ctx.get("probe_winrate", 0.0)),
                    probe_trades=int(ctx.get("probe_trades", 0)),
                )
                self._publish_plan(cid, plan, "probe_complete")
            elif signal == "meta_maybe_start_self_eval":
                snap = self._build_snapshot(ctx.get("snapshot", {}))
                self.controller.maybe_start_self_eval(
                    snap,
                    strong_recovery_attempts=int(ctx.get("strong_recovery_attempts", 0)),
                    attempt=int(ctx.get("attempt", 0)),
                )
                self._set_response(cid, "ok", True)
            elif signal == "meta_evaluate_provisional_fallback":
                snap = self._build_snapshot(ctx.get("snapshot", {}))
                result = self.controller.evaluate_provisional_fallback(
                    snap,
                    constitution_violations=int(ctx.get("constitution_violations", 0)),
                )
                self._set_response(cid, "provisional", asdict(result))
            elif signal == "meta_apply_explore_multiplier":
                steps = int(ctx.get("explore_steps", 0))
                self._set_response(
                    cid, "explore_steps", self.controller.apply_explore_multiplier(steps)
                )
            elif signal == "meta_record_inject":
                self.controller.record_inject(
                    patterns=int(ctx.get("patterns", ctx.get("patterns_mined", 0))),
                    oracle_wins=int(ctx.get("oracle_wins", 0)),
                )
                self._set_response(cid, "ok", True)
            elif signal == "meta_patch_state":
                if "explore_multiplier" in ctx:
                    self.controller.explore_multiplier = float(ctx["explore_multiplier"])
                if "active_reward" in ctx and ctx["active_reward"] is not None:
                    from lumina_core.birth.config import BirthRewardConfig

                    raw = ctx["active_reward"]
                    if isinstance(raw, dict):
                        self.controller.active_reward = BirthRewardConfig(**raw)
                    else:
                        self.controller.active_reward = raw
                if ctx.get("increment_rollouts"):
                    self.controller.rollouts_since_review += 1
                self._set_response(cid, "ok", True)
            elif signal == "meta_format_self_eval_suffix":
                self._set_response(
                    cid, "suffix", self.controller.format_self_eval_suffix()
                )
            elif signal == "meta_self_eval_state":
                self._set_response(
                    cid,
                    "self_eval",
                    {
                        "active": self.controller.is_self_eval_active(),
                        "phase": str(self.controller.self_eval.phase.value),
                        "reward_tweak_active": self.controller.reward_tweak_active,
                        "active_reward": asdict(self.controller.active_reward),
                    },
                )
            elif signal == "meta_detect_stall":
                result = detect_stall(
                    winrate_history=list(ctx.get("winrate_history", [])),
                    reward_history=list(ctx.get("reward_history", [])),
                    low_velocity_attempts=int(ctx.get("low_velocity_attempts", 0)),
                    cfg=self.cfg,
                    oos_proxy_history=ctx.get("oos_proxy_history"),
                )
                self._set_response(cid, "stall", asdict(result))
        except Exception as exc:
            logger.warning("meta_handler.signal_failed signal=%s: %s", signal, exc)
            self._set_response(cid, "error", str(exc))

    @staticmethod
    def _build_snapshot(data: dict[str, Any]) -> LearningSnapshot:
        if not data:
            return LearningSnapshot(
                winrate_history=(),
                reward_history=(),
                stage_trades=0,
                required_trades=0,
                patterns_mined=0,
                patterns_last_inject=0,
                oracle_wins_last_inject=0,
                buffer_size=0,
                escalation_level=0,
                strong_recovery_mode=False,
                strong_recovery_attempts=0,
                low_velocity_attempts=0,
                data_exhausted=False,
                stage=CurriculumStage.STAGE1_TREND,
            )
        return deserialize_learning_snapshot(data)


__all__ = ["MetaControllerHandler"]
