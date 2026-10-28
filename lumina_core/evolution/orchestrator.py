"""Thin EvolutionOrchestrator: promotion Event Bus wiring only (no Birth-v1 search)."""

from __future__ import annotations

import logging
import threading
from typing import Any

from lumina_core.agent_orchestration import EventBus

from .approval_twin_agent import ApprovalTwinAgent
from .dna_registry import DNARegistry
from .evolution_guard import EvolutionGuard
from .promotion_policy import PromotionPolicy
from .steve_values_registry import SteveValuesRegistry

logger = logging.getLogger(__name__)


class GenerationResult:
    """Placeholder kept for import compatibility. Birth-v1 generations are archived."""

    ok: bool = False
    reason: str = "BIRTH_V1_ARCHIVED"


class EvolutionOrchestrator:
    """Singleton that binds Approval Twin / PromotionPolicy to the Event Bus."""

    _instance: EvolutionOrchestrator | None = None
    _lock = threading.RLock()

    def __new__(cls) -> "EvolutionOrchestrator":
        with cls._lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._initialized = False  # type: ignore[attr-defined]
                cls._instance = obj
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._registry = DNARegistry()
        self._guard = EvolutionGuard()
        self._values_registry = SteveValuesRegistry()
        self._approval_twin = ApprovalTwinAgent(registry=self._values_registry, event_bus=None)
        self._market_data_service: Any | None = None
        self._promotion_policy: PromotionPolicy | None = None
        self._initialized = True

    def bind_promotion_event_bus(self, event_bus: EventBus | None) -> None:
        self._promotion_policy = PromotionPolicy(owner=self, logger=logger, event_bus=event_bus)
        twin = getattr(self, "_approval_twin", None)
        if twin is not None and hasattr(twin, "bind_event_bus"):
            twin.bind_event_bus(event_bus)

    def bind_market_data_service(self, market_data_service: Any | None) -> None:
        self._market_data_service = market_data_service
        self._sim_runner = None

    def bind_ppo_trainer(self, ppo_trainer: Any | None) -> None:
        del ppo_trainer

    def bind_vector_collection(self, collection: Any | None) -> None:
        del collection

    def run_nightly_evolution_cycle(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {
            "ok": False,
            "reason": "BIRTH_V1_ARCHIVED",
            "mutation_applied": False,
            "validation_gate": "blocked",
        }


__all__ = ["EvolutionOrchestrator", "GenerationResult"]
