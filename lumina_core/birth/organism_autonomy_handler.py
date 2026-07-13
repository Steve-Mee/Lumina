"""OrganismAutonomyHandler — EventBus owner for never-stop recovery decisions."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import BirthAutonomyDecision, BirthStageRolloutSnapshot
from lumina_core.birth.birth_bus_choreography import TOPIC_SNAPSHOT
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.death_spiral_guard import DeathSpiralState
from lumina_core.birth.organism_autonomy import (
    OrganismAutonomyState,
    RecoveryDispatch,
    evaluate_terminal_stall,
)
from lumina_core.birth.phoenix_loop import PhoenixLoopState

logger = logging.getLogger("lumina.birth.organism_autonomy_handler")


class OrganismAutonomyHandler:
    """Subscribes to terminal stall snapshots; publishes autonomy decisions."""

    def __init__(
        self,
        event_bus: EventBus,
        cfg: BirthCurriculumConfig,
        *,
        registry: Any | None = None,
    ) -> None:
        if event_bus is None:
            raise ValueError("OrganismAutonomyHandler requires EventBus")
        self.bus = event_bus
        self.cfg = cfg
        self.state = OrganismAutonomyState(
            phoenix=PhoenixLoopState(),
            death_spiral=DeathSpiralState(),
        )
        self._registry = registry
        self._token: str | None = None

    def attach(self) -> str:
        if self._token is None:
            self._token = self.bus.subscribe(TOPIC_SNAPSHOT, self._on_snapshot)
        return self._token or ""

    def detach(self) -> None:
        if self._token:
            try:
                self.bus.unsubscribe(self._token)
            except Exception:
                pass
            self._token = None

    def _set_response(self, correlation_id: str, key: str, value: Any) -> None:
        if self._registry is not None and hasattr(self._registry, "set_response"):
            self._registry.set_response(correlation_id, key, value)

    def _publish_decision(self, correlation_id: str, decision: Any) -> None:
        payload = BirthAutonomyDecision(
            correlation_id=correlation_id,
            dispatch=decision.dispatch.value,
            needs_attention=bool(decision.needs_attention),
            retryable=bool(decision.retryable),
            stall_reason=str(decision.stall_reason),
            recommended_action=str(decision.recommended_action),
            checkpoint_patch=decision.checkpoint_patch,
            autonomy_metrics=decision.autonomy_metrics or {},
            message=str(decision.message),
        )
        self.bus.publish(
            topic="birth.autonomy.decision",
            producer="birth.organism_autonomy_handler",
            payload=payload.model_dump(mode="json"),
            metadata={"correlation_id": correlation_id},
        )
        self._set_response(
            correlation_id,
            "autonomy",
            {
                "dispatch": decision.dispatch.value,
                "needs_attention": decision.needs_attention,
                "retryable": decision.retryable,
                "stall_reason": decision.stall_reason,
                "recommended_action": decision.recommended_action,
                "checkpoint_patch": decision.checkpoint_patch,
                "autonomy_metrics": decision.autonomy_metrics,
                "message": decision.message,
            },
        )

    def _on_snapshot(self, event: DomainEvent) -> None:
        try:
            snap_evt = event.typed_payload(BirthStageRolloutSnapshot)
        except Exception as exc:
            logger.warning("autonomy_handler.snapshot_schema_violation: %s", exc)
            return

        cid = snap_evt.correlation_id
        signal = snap_evt.signal
        ctx = snap_evt.context

        try:
            if signal == "autonomy_restore_state":
                self.state = OrganismAutonomyState.from_metrics(ctx.get("metrics"))
                self._set_response(cid, "ok", True)
            elif signal == "autonomy_evaluate_terminal_stall":
                pending = ctx.get("pending", {})
                if not isinstance(pending, dict):
                    pending = {}
                decision = evaluate_terminal_stall(
                    cfg=self.cfg,
                    autonomy_state=self.state,
                    pending=pending,
                    curriculum_stage=snap_evt.stage,
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    required=int(ctx.get("required", 0)),
                    constitution_violations=int(ctx.get("constitution_violations", 0)),
                    fitness_signal=float(ctx.get("fitness_signal", 0.0)),
                    recommended_recovery_action=str(
                        ctx.get("recommended_recovery_action", "")
                    ),
                    remediation_cycles_exhausted=bool(
                        ctx.get("remediation_cycles_exhausted", False)
                    ),
                    plateau_exhausted=bool(ctx.get("plateau_exhausted", False)),
                )
                self._publish_decision(cid, decision)
            elif signal == "autonomy_get_state":
                self._set_response(cid, "state", self.state.to_metrics())
            elif signal == "autonomy_patch_state":
                if "last_recommended_action" in ctx:
                    self.state.last_recommended_action = str(
                        ctx["last_recommended_action"]
                    )
                if "autonomous_recovery_count" in ctx:
                    self.state.autonomous_recovery_count = int(
                        ctx["autonomous_recovery_count"]
                    )
                self._set_response(cid, "ok", True)
        except Exception as exc:
            logger.warning("autonomy_handler.signal_failed signal=%s: %s", signal, exc)
            self._set_response(cid, "error", str(exc))


__all__ = ["OrganismAutonomyHandler", "OrganismAutonomyState", "RecoveryDispatch"]
