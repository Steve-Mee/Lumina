"""PhoenixHandler — EventBus owner for phoenix rebirth loops."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import (
    BirthAutonomyDecision,
    BirthPhoenixCycle,
    BirthStageRolloutSnapshot,
)
from lumina_core.birth.birth_bus_choreography import TOPIC_SNAPSHOT
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.phoenix_loop import (
    PhoenixLoopState,
    PhoenixNoveltyAction,
    begin_phoenix_cycle,
    build_phoenix_checkpoint_patch,
    can_start_phoenix,
    select_phoenix_novelty,
)

logger = logging.getLogger("lumina.birth.phoenix_handler")


class PhoenixHandler:
    """Subscribes to autonomy decisions and explicit phoenix triggers."""

    def __init__(
        self,
        event_bus: EventBus,
        cfg: BirthCurriculumConfig,
        *,
        registry: Any | None = None,
    ) -> None:
        if event_bus is None:
            raise ValueError("PhoenixHandler requires EventBus")
        self.bus = event_bus
        self.cfg = cfg
        self.state = PhoenixLoopState()
        self._registry = registry
        self._snapshot_token: str | None = None
        self._autonomy_token: str | None = None

    def attach(self) -> str:
        if self._snapshot_token is None:
            self._snapshot_token = self.bus.subscribe(TOPIC_SNAPSHOT, self._on_snapshot)
        if self._autonomy_token is None:
            self._autonomy_token = self.bus.subscribe(
                "birth.autonomy.decision", self._on_autonomy_decision
            )
        return self._snapshot_token or ""

    def detach(self) -> None:
        for token in (self._snapshot_token, self._autonomy_token):
            if token:
                try:
                    self.bus.unsubscribe(token)
                except Exception:
                    pass
        self._snapshot_token = None
        self._autonomy_token = None

    def _set_response(self, correlation_id: str, key: str, value: Any) -> None:
        if self._registry is not None and hasattr(self._registry, "set_response"):
            self._registry.set_response(correlation_id, key, value)

    def _publish_cycle(
        self,
        *,
        correlation_id: str,
        novelty: PhoenixNoveltyAction,
        stall_reason: str,
        checkpoint_patch: dict[str, Any] | None,
    ) -> None:
        cycle_payload = BirthPhoenixCycle(
            cycle=int(self.state.phoenix_count),
            reason=stall_reason,
            action=novelty.value,
            preserve_cache=True,
            checkpoint_patch=checkpoint_patch,
        )
        self.bus.publish(
            topic="birth.phoenix.cycle",
            producer="birth.phoenix_handler",
            payload=cycle_payload.model_dump(mode="json"),
            metadata={"correlation_id": correlation_id},
        )

    def _on_autonomy_decision(self, event: DomainEvent) -> None:
        try:
            decision = event.typed_payload(BirthAutonomyDecision)
        except Exception:
            return
        if decision.dispatch != "phoenix_resume":
            return
        cid = str(decision.correlation_id or event.metadata.get("correlation_id", ""))
        if not can_start_phoenix(self.state, cfg=self.cfg):
            return
        novelty_raw = str(
            (decision.autonomy_metrics or {}).get("phoenix_novelty", "")
        )
        novelty = (
            PhoenixNoveltyAction(novelty_raw)
            if novelty_raw
            else select_phoenix_novelty(self.state, cfg=self.cfg)
        )
        begin_phoenix_cycle(
            self.state,
            novelty=novelty,
            stall_reason=decision.stall_reason or "phoenix_cycle",
        )
        patch = decision.checkpoint_patch or build_phoenix_checkpoint_patch(
            novelty=novelty,
            curriculum_stage=str(
                (decision.autonomy_metrics or {}).get("curriculum_stage", "")
            ),
            cfg=self.cfg,
        )
        self._publish_cycle(
            correlation_id=cid,
            novelty=novelty,
            stall_reason=decision.stall_reason,
            checkpoint_patch=patch,
        )

    def _on_snapshot(self, event: DomainEvent) -> None:
        try:
            snap_evt = event.typed_payload(BirthStageRolloutSnapshot)
        except Exception as exc:
            logger.warning("phoenix_handler.snapshot_schema_violation: %s", exc)
            return

        cid = snap_evt.correlation_id
        signal = snap_evt.signal
        ctx = snap_evt.context

        try:
            if signal == "phoenix_restore_state":
                self.state = PhoenixLoopState.from_metrics(ctx.get("metrics"))
                self._set_response(cid, "ok", True)
            elif signal == "phoenix_can_start":
                can = can_start_phoenix(self.state, cfg=self.cfg)
                self._set_response(cid, "can_start", can)
            elif signal == "phoenix_select_novelty":
                novelty = select_phoenix_novelty(
                    self.state,
                    cfg=self.cfg,
                    circuit_breaker=bool(ctx.get("circuit_breaker", False)),
                )
                self._set_response(cid, "novelty", novelty.value)
            elif signal == "phoenix_begin_cycle":
                novelty = PhoenixNoveltyAction(str(ctx.get("novelty", "expand_data")))
                stall_reason = str(ctx.get("stall_reason", "phoenix_cycle"))
                begin_phoenix_cycle(
                    self.state, novelty=novelty, stall_reason=stall_reason
                )
                patch = build_phoenix_checkpoint_patch(
                    novelty=novelty,
                    curriculum_stage=snap_evt.stage,
                    cfg=self.cfg,
                )
                self._publish_cycle(
                    correlation_id=cid,
                    novelty=novelty,
                    stall_reason=stall_reason,
                    checkpoint_patch=patch,
                )
                self._set_response(cid, "patch", patch)
            elif signal == "phoenix_get_state":
                self._set_response(cid, "state", self.state.to_metrics())
        except Exception as exc:
            logger.warning("phoenix_handler.signal_failed signal=%s: %s", signal, exc)
            self._set_response(cid, "error", str(exc))


__all__ = ["PhoenixHandler", "PhoenixLoopState"]
