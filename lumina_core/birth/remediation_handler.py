"""RemediationHandler — EventBus owner for stall remediation ladder."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import (
    BirthCertificateRemediationRequested,
    BirthStallRemediationCycle,
    BirthStallRemediationStep,
    BirthStageRolloutSnapshot,
)
from lumina_core.birth.birth_bus_choreography import TOPIC_CERT_REMEDIATION, TOPIC_SNAPSHOT
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.remediation import should_fast_path_remediation_from_state
from lumina_core.birth.stall_remediation import (
    StallRemediationAction,
    StallRemediationState,
    begin_remediation_cycle,
    begin_remediation_step,
    can_start_remediation,
    increment_remediation_rollout,
    is_remediation_exhausted,
    record_remediation_outcome,
    should_advance_remediation_step,
    should_run_remediation_instead_of_human_gate,
)

logger = logging.getLogger("lumina.birth.remediation_handler")


class RemediationHandler:
    """Subscribes to rollout snapshots; publishes remediation cycle/step facts."""

    def __init__(
        self,
        event_bus: EventBus,
        cfg: BirthCurriculumConfig,
        *,
        registry: Any | None = None,
    ) -> None:
        if event_bus is None:
            raise ValueError("RemediationHandler requires EventBus")
        self.bus = event_bus
        self.cfg = cfg
        self.state = StallRemediationState()
        self._registry = registry
        self._token: str | None = None
        self._cert_token: str | None = None

    def attach(self) -> str:
        if self._token is None:
            self._token = self.bus.subscribe(TOPIC_SNAPSHOT, self._on_snapshot)
        if self._cert_token is None:
            self._cert_token = self.bus.subscribe(
                TOPIC_CERT_REMEDIATION, self._on_certificate_remediation_requested
            )
        return self._token or ""

    def detach(self) -> None:
        for token in (self._token, self._cert_token):
            if token:
                try:
                    self.bus.unsubscribe(token)
                except Exception:
                    pass
        self._token = None
        self._cert_token = None

    def _on_certificate_remediation_requested(self, event: DomainEvent) -> None:
        if event.producer == "birth.remediation_handler":
            return
        try:
            req = event.typed_payload(BirthCertificateRemediationRequested)
        except Exception:
            return
        eligible = should_fast_path_remediation_from_state(
            req.progress_snapshot,
            req.checkpoint_state,
        )
        response = BirthCertificateRemediationRequested(
            progress_snapshot=req.progress_snapshot,
            checkpoint_state=req.checkpoint_state,
            fast_path_eligible=eligible,
        )
        self.bus.publish(
            topic=TOPIC_CERT_REMEDIATION,
            producer="birth.remediation_handler",
            payload=response.model_dump(mode="json"),
            metadata=dict(event.metadata),
        )

    def _set_response(self, correlation_id: str, key: str, value: Any) -> None:
        if self._registry is not None and hasattr(self._registry, "set_response"):
            self._registry.set_response(correlation_id, key, value)

    def _on_snapshot(self, event: DomainEvent) -> None:
        try:
            snap_evt = event.typed_payload(BirthStageRolloutSnapshot)
        except Exception as exc:
            logger.warning("remediation_handler.snapshot_schema_violation: %s", exc)
            return

        cid = snap_evt.correlation_id
        signal = snap_evt.signal
        ctx = snap_evt.context

        try:
            if signal == "remediation_restore_state":
                self.state = StallRemediationState.from_metrics(ctx.get("metrics"))
                self._set_response(cid, "ok", True)
            elif signal == "remediation_should_run":
                should = should_run_remediation_instead_of_human_gate(
                    self.state,
                    cfg=self.cfg,
                    plateau_exhausted=bool(ctx.get("plateau_exhausted", False)),
                )
                self._set_response(cid, "should_run", should)
            elif signal == "remediation_can_start":
                can = can_start_remediation(self.state, cfg=self.cfg)
                self._set_response(cid, "can_start", can)
            elif signal == "remediation_is_exhausted":
                exhausted = is_remediation_exhausted(self.state, cfg=self.cfg)
                self._set_response(cid, "exhausted", exhausted)
            elif signal == "remediation_begin_cycle":
                begin_remediation_cycle(
                    self.state,
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    stage_wins=int(ctx.get("stage_wins", 0)),
                )
                cycle_payload = BirthStallRemediationCycle(
                    correlation_id=cid,
                    cycle=int(self.state.remediation_cycle),
                    max_cycles=int(self.cfg.stall_remediation_max_cycles),
                    winrate_at_start=float(self.state.winrate_at_step_start),
                )
                self.bus.publish(
                    topic="birth.stall.remediation.cycle",
                    producer="birth.remediation_handler",
                    payload=cycle_payload.model_dump(mode="json"),
                    metadata={"correlation_id": cid},
                )
                self._set_response(cid, "cycle_started", True)
            elif signal == "remediation_begin_step":
                action = begin_remediation_step(
                    self.state,
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    stage_wins=int(ctx.get("stage_wins", 0)),
                )
                step_payload = BirthStallRemediationStep(
                    correlation_id=cid,
                    cycle=int(self.state.remediation_cycle),
                    step=int(self.state.remediation_step),
                    max_steps=int(self.cfg.stall_remediation_max_steps),
                    action=action.value if action else None,
                    detail=str(ctx.get("detail", "")),
                )
                self.bus.publish(
                    topic="birth.stall.remediation.step",
                    producer="birth.remediation_handler",
                    payload=step_payload.model_dump(mode="json"),
                    metadata={"correlation_id": cid},
                )
                self._set_response(
                    cid, "action", action.value if action else None
                )
            elif signal == "remediation_should_advance":
                should = should_advance_remediation_step(
                    self.state,
                    cfg=self.cfg,
                    current_winrate=float(ctx.get("current_winrate", 0.0)),
                )
                self._set_response(cid, "should_advance", should)
            elif signal == "remediation_increment_rollout":
                increment_remediation_rollout(self.state)
                self._set_response(cid, "ok", True)
            elif signal == "remediation_record_outcome":
                action_raw = ctx.get("action")
                action = (
                    StallRemediationAction(str(action_raw)) if action_raw else None
                )
                record_remediation_outcome(
                    self.state,
                    action=action,
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    stage_wins=int(ctx.get("stage_wins", 0)),
                    detail=str(ctx.get("detail", "")),
                )
                self._set_response(cid, "ok", True)
            elif signal == "remediation_patch_state":
                if "active" in ctx:
                    self.state.active = bool(ctx["active"])
                if "remediation_step" in ctx:
                    self.state.remediation_step = int(ctx["remediation_step"])
                if "remediation_rollouts_this_step" in ctx:
                    self.state.remediation_rollouts_this_step = int(
                        ctx["remediation_rollouts_this_step"]
                    )
                if "meta_sweep_index" in ctx:
                    self.state.meta_sweep_index = int(ctx["meta_sweep_index"])
                self._set_response(cid, "ok", True)
            elif signal == "remediation_get_state":
                self._set_response(cid, "state", self.state.to_metrics())
        except Exception as exc:
            logger.warning(
                "remediation_handler.signal_failed signal=%s: %s", signal, exc
            )
            self._set_response(cid, "error", str(exc))


__all__ = ["RemediationHandler", "StallRemediationState"]
