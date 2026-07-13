"""CurriculumStageHandler — thin EventBus adapter for stage execution."""

from __future__ import annotations

from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import (
    BirthCurriculumStageAborted,
    BirthCurriculumStageRequested,
    BirthCurriculumStageStarted,
)
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_rollout_executor import run_stage_research_loop

TOPIC_REQUESTED = "birth.curriculum.stage.requested"
TOPIC_STARTED = "birth.curriculum.stage.started"
TOPIC_ABORTED = "birth.curriculum.aborted"


class CurriculumStageHandler:
    """Subscribes to stage requests and announces stage start on the bus."""

    def __init__(self, event_bus: EventBus | None = None, host_factory: Any | None = None) -> None:
        self.bus = event_bus
        self.host_factory = host_factory
        self._token: str | None = None

    def attach(self) -> str:
        if self.bus is None:
            return ""
        if self._token is None:
            self._token = self.bus.subscribe(TOPIC_REQUESTED, self._on_stage_requested)
        return self._token or ""

    def detach(self) -> None:
        if self.bus and self._token:
            try:
                self.bus.unsubscribe(self._token)
            except Exception:
                pass
            self._token = None

    def _on_stage_requested(self, event: DomainEvent) -> None:
        try:
            req = event.typed_payload(BirthCurriculumStageRequested)
        except Exception as exc:
            self._publish_abort(None, "stage_request_schema_violation", {"error": str(exc)})
            return

        stage_name = req.stage
        try:
            stage = CurriculumStage(stage_name)
        except ValueError:
            self._publish_abort(stage_name, "unknown_stage", {"stage": stage_name})
            return

        started = BirthCurriculumStageStarted(
            stage=stage.value, stage_index=int(req.stage_index), required_trades=0
        )
        if self.bus:
            self.bus.publish(
                topic=TOPIC_STARTED,
                producer="birth.curriculum_stage_handler",
                payload=started.model_dump(mode="json"),
            )

    def _publish_abort(self, stage: str | None, reason: str, detail: dict[str, Any]) -> None:
        abort = BirthCurriculumStageAborted(stage=stage, reason=reason, detail=detail)
        if self.bus:
            self.bus.publish_validated(
                topic=TOPIC_ABORTED,
                producer="birth.curriculum_stage_handler",
                payload=abort.model_dump(mode="json"),
            )


def create_and_attach_stage_handler(bus: EventBus, host: Any) -> CurriculumStageHandler:
    handler = CurriculumStageHandler(bus, host_factory=host)
    handler.attach()
    return handler


__all__ = [
    "CurriculumStageHandler",
    "create_and_attach_stage_handler",
    "run_stage_research_loop",
]

# Monkeypatch compat: re-export rollout symbols from stage_training_loop when patched.
try:
    import lumina_core.birth.stage_training_loop as _shim_mod

    if hasattr(_shim_mod, "run_policy_rollout"):
        from lumina_core.birth.stage_training_loop import run_policy_rollout  # noqa: F401
    if hasattr(_shim_mod, "mine_winning_patterns"):
        from lumina_core.birth.stage_training_loop import mine_winning_patterns  # noqa: F401
    if hasattr(_shim_mod, "expand_birth_data"):
        from lumina_core.birth.stage_training_loop import expand_birth_data  # noqa: F401
except Exception:
    pass
