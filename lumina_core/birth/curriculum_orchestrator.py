"""Thin CurriculumOrchestrator (<300 LOC).

Only emits/receives via central EventBus (ADR-0001).
Fail-closed on constitution violation.
Curriculum / plateau / remediation / phoenix / intra logic belong in dedicated handlers.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import (
    BirthCurriculumStageAborted,
    BirthCurriculumStageCompleted,
    BirthCurriculumStageRequested,
    BirthCurriculumStarted,
    ConstitutionViolation,
)

logger = logging.getLogger("lumina.birth.curriculum_orchestrator")

# Topics (canonical, lower-cased by bus)
TOPIC_CURRICULUM_STARTED = "birth.curriculum.started"
TOPIC_STAGE_REQUESTED = "birth.curriculum.stage.requested"
TOPIC_STAGE_STARTED = "birth.curriculum.stage.started"
TOPIC_STAGE_COMPLETED = "birth.curriculum.stage.completed"
TOPIC_STAGE_ABORTED = "birth.curriculum.aborted"
TOPIC_CONSTITUTION_VIOLATION = "safety.constitution.violation"


@dataclass(slots=True)
class CurriculumRunState:
    """Minimal orchestrator-owned state (no business logic)."""

    curriculum_id: str = ""
    stages: list[str] = field(default_factory=list)
    current_index: int = 0
    aborted: bool = False
    abort_reason: str | None = None
    constitution_violations_seen: int = 0
    completed_stages: list[str] = field(default_factory=list)


class CurriculumOrchestrator:
    """Thin event-only orchestrator.

    - Publishes curriculum facts and stage requests.
    - Subscribes to completions + violations.
    - Sequences or aborts.
    - Fail-closed on constitution violation.
    Zero domain algorithms.
    """

    def __init__(self, event_bus: EventBus, *, producer: str = "birth.curriculum_orchestrator") -> None:
        if event_bus is None:
            raise ValueError("CurriculumOrchestrator requires a central EventBus")
        self.bus = event_bus
        self.producer = str(producer)
        self.state = CurriculumRunState()
        self._tokens: list[str] = []
        self._completion_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._abort_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._wire_subscriptions()

    def _wire_subscriptions(self) -> None:
        self._tokens.append(
            self.bus.subscribe(TOPIC_CONSTITUTION_VIOLATION, self._handle_constitution_violation)
        )
        self._tokens.append(
            self.bus.subscribe(TOPIC_STAGE_COMPLETED, self._handle_stage_completed)
        )
        self._tokens.append(
            self.bus.subscribe(TOPIC_STAGE_ABORTED, self._handle_stage_aborted)
        )

    def _handle_constitution_violation(self, event: DomainEvent) -> None:
        """Fail-closed on hard violations only; soft (warning) counts without abort spam."""
        try:
            payload = event.typed_payload(ConstitutionViolation)
        except Exception:
            payload = ConstitutionViolation(
                principle_name="birth_constitution_guard",
                severity="critical",
                description="untyped_violation",
                detail=str(event.payload),
                mode="birth",
            )

        is_birth = (payload.mode or "").lower() == "birth" or "birth" in str(payload.detail or "").lower()
        if not is_birth:
            return

        self.state.constitution_violations_seen += 1
        severity = str(payload.severity or "critical").strip().lower()
        # Match ConstitutionEnforcer: warning/info are training feedback, not terminal.
        if severity in {"warning", "info", "soft"}:
            if self.state.constitution_violations_seen <= 3 or self.state.constitution_violations_seen % 100 == 0:
                logger.warning(
                    "birth.curriculum soft_constitution_violation principle=%s count=%s",
                    payload.principle_name,
                    self.state.constitution_violations_seen,
                )
            return

        # Hard abort at most once (true fail-closed; host stop via abort callbacks).
        if self.state.aborted:
            return
        self.state.aborted = True
        self.state.abort_reason = "constitution_violation"

        abort = BirthCurriculumStageAborted(
            stage=self.state.stages[self.state.current_index] if self.state.stages and self.state.current_index < len(self.state.stages) else None,
            reason="constitution_violation",
            detail={
                "principle": payload.principle_name,
                "description": payload.description,
                "severity": payload.severity,
            },
            violations=self.state.constitution_violations_seen,
        )
        self.bus.publish_validated(
            topic=TOPIC_STAGE_ABORTED,
            producer=self.producer,
            payload=abort.model_dump(mode="json"),
        )
        logger.error(
            "birth.curriculum ABORT (fail-closed) constitution_violation=%s violations=%s",
            payload.principle_name,
            self.state.constitution_violations_seen,
        )
        self._invoke_abort_callbacks(abort.model_dump(mode="json"))

    def _handle_stage_completed(self, event: DomainEvent) -> None:
        if self.state.aborted:
            return
        try:
            payload = event.typed_payload(BirthCurriculumStageCompleted)
        except Exception as exc:
            # Fail-closed on contract violation for critical topic
            self._abort_due_to_bad_event("stage_completed_schema_violation", {"error": str(exc)})
            return

        stage = payload.stage
        if self._is_expected_stage(stage):
            self.state.completed_stages.append(stage)
            self.state.current_index += 1

        if payload.passed or True:  # handlers decide pass; orchestrator just sequences
            logger.info("birth.curriculum.stage.completed stage=%s passed=%s", stage, payload.passed)

        if self.state.current_index >= len(self.state.stages):
            # Curriculum finished
            logger.info("birth.curriculum completed stages=%s", self.state.completed_stages)
            self._invoke_completion_callbacks({"completed": list(self.state.completed_stages)})
        else:
            # Request next stage via the bus (handlers react)
            self._request_current_stage()

    def _handle_stage_aborted(self, event: DomainEvent) -> None:
        try:
            payload = event.typed_payload(BirthCurriculumStageAborted)
        except Exception:
            payload = BirthCurriculumStageAborted(reason="unknown", detail=event.payload)
        # Idempotent: violation handler may already have aborted + invoked callbacks.
        if self.state.aborted:
            if not self.state.abort_reason:
                self.state.abort_reason = payload.reason
            return
        self.state.aborted = True
        self.state.abort_reason = payload.reason
        self._invoke_abort_callbacks(payload.model_dump(mode="json"))

    def _is_expected_stage(self, stage: str) -> bool:
        if not self.state.stages or self.state.current_index >= len(self.state.stages):
            return False
        return self.state.stages[self.state.current_index] == stage

    def _abort_due_to_bad_event(self, reason: str, detail: dict[str, Any]) -> None:
        self.state.aborted = True
        self.state.abort_reason = reason
        abort = BirthCurriculumStageAborted(
            stage=self._safe_current_stage(),
            reason=reason,
            detail=detail,
            violations=self.state.constitution_violations_seen,
        )
        self.bus.publish_validated(
            topic=TOPIC_STAGE_ABORTED,
            producer=self.producer,
            payload=abort.model_dump(mode="json"),
        )
        self._invoke_abort_callbacks(abort.model_dump(mode="json"))

    def _safe_current_stage(self) -> str | None:
        if self.state.stages and 0 <= self.state.current_index < len(self.state.stages):
            return self.state.stages[self.state.current_index]
        return None

    def start_curriculum(
        self,
        *,
        stages: list[str],
        target_trades_cap: int,
        practice_mode: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Entry point. Publishes the start fact and requests first stage.

        Returns the curriculum_id. All further coordination is event-driven.
        """
        if not stages:
            raise ValueError("curriculum requires at least one stage")
        if self.state.curriculum_id:
            logger.warning("birth.curriculum restart requested while previous active")

        curriculum_id = str(uuid.uuid4())
        self.state = CurriculumRunState(
            curriculum_id=curriculum_id,
            stages=list(stages),
            current_index=0,
            aborted=False,
            abort_reason=None,
            constitution_violations_seen=0,
            completed_stages=[],
        )

        started = BirthCurriculumStarted(
            curriculum_id=curriculum_id,
            stages=list(stages),
            target_trades_cap=int(target_trades_cap),
            practice_mode=bool(practice_mode),
        )
        self.bus.publish_validated(
            topic=TOPIC_CURRICULUM_STARTED,
            producer=self.producer,
            payload=started.model_dump(mode="json"),
        )

        # Kick off first stage request (dedicated handlers react to this)
        self._request_current_stage()
        return curriculum_id

    def _request_current_stage(self) -> None:
        if self.state.aborted or self.state.current_index >= len(self.state.stages):
            return
        stage = self.state.stages[self.state.current_index]
        req = BirthCurriculumStageRequested(
            stage=stage,
            stage_index=self.state.current_index,
            target=0,  # target resolved by handler/config
            stage_progress_pct=0.0,
            training_mode="practice" if False else "certified",  # resolved by handler from cfg
            prefer_real=True,
        )
        self.bus.publish_validated(
            topic=TOPIC_STAGE_REQUESTED,
            producer=self.producer,
            payload=req.model_dump(mode="json"),
        )

    def on_curriculum_completed(self, cb: Callable[[dict[str, Any]], None]) -> None:
        self._completion_callbacks.append(cb)

    def on_curriculum_aborted(self, cb: Callable[[dict[str, Any]], None]) -> None:
        self._abort_callbacks.append(cb)

    def _invoke_completion_callbacks(self, result: dict[str, Any]) -> None:
        for cb in list(self._completion_callbacks):
            try:
                cb(result)
            except Exception:
                logger.exception("completion callback failed")

    def _invoke_abort_callbacks(self, abort: dict[str, Any]) -> None:
        for cb in list(self._abort_callbacks):
            try:
                cb(abort)
            except Exception:
                logger.exception("abort callback failed")

    def is_aborted(self) -> bool:
        return self.state.aborted

    def current_stage(self) -> str | None:
        return self._safe_current_stage()

    def shutdown(self) -> None:
        for token in self._tokens:
            try:
                self.bus.unsubscribe(token)
            except Exception:
                pass
        self._tokens.clear()


def register_stage_execution_handler(
    bus: EventBus, handler_fn: Callable[[DomainEvent], None]
) -> str:
    """Wire a dedicated handler (curriculum/plateau/etc) to stage requests."""
    return bus.subscribe(TOPIC_STAGE_REQUESTED, handler_fn)


__all__ = [
    "CurriculumOrchestrator",
    "CurriculumRunState",
    "register_stage_execution_handler",
    "TOPIC_CURRICULUM_STARTED",
    "TOPIC_STAGE_REQUESTED",
    "TOPIC_STAGE_STARTED",
    "TOPIC_STAGE_COMPLETED",
    "TOPIC_STAGE_ABORTED",
]
