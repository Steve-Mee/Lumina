"""ApplicationContainerServicesMixin (M5 extract)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.adaptive_intelligence import build_status_signature
from lumina_core.agent_orchestration.schemas import AdaptiveIntelligenceState
from lumina_core.logging_utils import get_logger
from lumina_core.monitoring import ObservabilityService

logger = get_logger("lumina.container")


class ApplicationContainerServicesMixin:
    def _init_services(self) -> None:
        """Initialize all services in dependency order."""
        from lumina_core.container.agent_wiring import (
            bind_evolution_promotion_event_bus,
            prepare_blackboard,
            wire_intelligence_agents,
            wire_swarm,
        )
        from lumina_core.container.engine_wiring import (
            validate_engine_attributes,
            wire_dashboard_cross_refs,
            wire_platform_services,
        )
        from lumina_core.container.risk_wiring import wire_risk_services

        prepare_blackboard(self)
        wire_platform_services(self)
        wire_intelligence_agents(self)
        wire_swarm(self)
        wire_risk_services(self)
        wire_dashboard_cross_refs(self)
        validate_engine_attributes(self)
        bind_evolution_promotion_event_bus(self)
        self.engine._sync_services_registry()
        self.logger.info("All services initialized successfully")

    def _bind_evolution_promotion_event_bus(self) -> None:
        from lumina_core.container.agent_wiring import bind_evolution_promotion_event_bus

        bind_evolution_promotion_event_bus(self)

    def bind_runtime_module(self, runtime_module: Any) -> None:
        """Bind the process entry module (__main__) as engine.app; attach legacy lumina_runtime API."""
        from lumina_core.bootstrap import attach_runtime_app_to_module

        attach_runtime_app_to_module(self, runtime_module)
        self.engine.bind_app(runtime_module)
        self.runtime_context.app = runtime_module

    def _init_observability(self) -> ObservabilityService:
        """Load config and start ObservabilityService (no-op if monitoring disabled)."""
        try:
            from lumina_core.config_loader import ConfigLoader

            full_cfg: dict[str, Any] = ConfigLoader.get()
            obs = ObservabilityService.from_config(full_cfg)
            obs.start()
            return obs
        except Exception as exc:
            self.logger.warning("ObservabilityService init failed (continuing): %s", exc)
            return ObservabilityService.from_config({})

    def _refresh_adaptive_intelligence(self, *, source: str, refresh_hardware: bool) -> dict[str, Any]:
        status_obj = self.adaptive_intelligence_manager.refresh(refresh_hardware=refresh_hardware)
        intelligence_status = status_obj.to_dict()
        self.local_inference_engine.apply_adaptive_intelligence(intelligence_status)
        self.engine.adaptive_intelligence = intelligence_status
        self._publish_adaptive_intelligence_state(intelligence_status, source=source)
        return intelligence_status

    def _publish_adaptive_intelligence_state(self, status: dict[str, Any], *, source: str) -> bool:
        signature = build_status_signature(status)
        previous = self._adaptive_intelligence_last_published_signature
        if previous == signature:
            return False
        transition = previous is not None
        transition_reason = "initial_publish" if previous is None else "status_signature_changed"
        self.event_bus.publish(
            topic="inference.adaptive_intelligence.state",
            producer="application_container",
            payload={
                **status,
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            metadata={
                "transition": transition,
                "transition_reason": transition_reason,
            },
            payload_model=AdaptiveIntelligenceState,
        )
        self._adaptive_intelligence_last_published_signature = signature
        return True


