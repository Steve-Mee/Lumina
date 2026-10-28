"""Request new hypotheses via HypothesisAgent. Never admits a live signal."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    REPLENISH_AGENT_ID,
    RESEARCH_REPLENISH_TOPIC,
    HypothesisProposed,
    ReplenishReason,
    ReplenishmentRequested,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.hypothesis import HypothesisAgent
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.monitoring.config import ContinuityConfig
from lumina_research.monitoring.registry import LiveSignalRegistry
from lumina_research.monitoring.report import log_decision
from lumina_research.monitoring.seal import accept_mac, canonical_replenish
from lumina_research.monitoring.types import ContinuityRefused


class ReplenishAgent(Frozen):
    """Emits a request and optionally runs HypothesisAgent. No registry writes."""

    _bus: EventBus
    _registry: LiveSignalRegistry
    _authority: ProvenanceAuthority
    _config: ContinuityConfig
    _log_path: Path
    _hypothesis: HypothesisAgent | None
    _blackboard: AgentBlackboard | None
    _evolution_log_dir: Path | None
    _requests: list[ReplenishmentRequested]
    _seq: list[int]
    _seen: set[str]

    def __init_subclass__(cls) -> None:
        raise TypeError("ReplenishAgent cannot be subclassed")

    def __init__(
        self,
        *,
        bus: EventBus,
        registry: LiveSignalRegistry,
        authority: ProvenanceAuthority,
        config: ContinuityConfig,
        experiment_log_path: Path,
        hypothesis: HypothesisAgent | None = None,
        blackboard: AgentBlackboard | None = None,
        evolution_log_dir: Path | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._authority = authority
        self._config = config
        self._log_path = experiment_log_path
        self._hypothesis = hypothesis
        self._blackboard = blackboard
        self._evolution_log_dir = evolution_log_dir
        self._requests = []
        self._seq = [0]
        self._seen = set()
        self._freeze()
        bus.register_topic_guard(RESEARCH_REPLENISH_TOPIC, self._guard)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_REPLENISH_TOPIC, self._guard_bb)

    def requests(self) -> tuple[ReplenishmentRequested, ...]:
        return tuple(self._requests)

    def shortcut_admit(self, signal_id: str) -> None:
        del signal_id
        raise ContinuityRefused("new signals only via Validation Gate")

    def maybe_request(
        self,
        *,
        seed: int,
        counts: Sequence[int] | None = None,
    ) -> tuple[ReplenishmentRequested, tuple[HypothesisProposed, ...]] | None:
        n_active = self._registry.n_active()
        capacity = self._registry.capacity_weight()
        reason: ReplenishReason | None = None
        floor = 0.0
        if n_active < self._config.min_active_signals:
            reason = "active_count"
            floor = float(self._config.min_active_signals)
        elif capacity < self._config.min_capacity_weight:
            reason = "capacity"
            floor = float(self._config.min_capacity_weight)
        if reason is None:
            return None
        event = self._emit(reason=reason, n_active=n_active, floor=floor)
        generated: tuple[HypothesisProposed, ...] = ()
        if self._hypothesis is not None:
            if counts is None:
                raise ContinuityRefused("generator counts required for replenishment")
            generated = self._hypothesis.generate(seed=seed, counts=tuple(int(item) for item in counts))
        return event, generated

    def _emit(self, *, reason: ReplenishReason, n_active: int, floor: float) -> ReplenishmentRequested:
        self._seq[0] += 1
        unsigned: dict[str, object] = {
            "schema_version": "research.replenishment.requested.v1",
            "request_id": f"repl-{self._seq[0]}",
            "agent_id": REPLENISH_AGENT_ID,
            "reason": reason,
            "n_active": n_active,
            "floor": floor,
            "n_requested": int(self._config.replenish_count),
        }
        mac = self._authority.mac(canonical_replenish(unsigned))
        event = ReplenishmentRequested.model_validate({**unsigned, "provenance_mac": mac})
        dumped = dump_json(event)
        self._bus.publish(topic=RESEARCH_REPLENISH_TOPIC, producer=REPLENISH_AGENT_ID, payload=dict(dumped))
        if self._blackboard is not None:
            self._blackboard.publish_sync(
                topic=RESEARCH_REPLENISH_TOPIC,
                producer=REPLENISH_AGENT_ID,
                payload=dict(dumped),
                confidence=1.0,
            )
        self._requests.append(event)
        log_decision(
            path=self._log_path,
            agent_id=REPLENISH_AGENT_ID,
            event="replenish",
            signal_id=event.request_id,
            metrics=dumped,
            evolution_log_dir=self._evolution_log_dir,
        )
        return event

    def _guard(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check(producer, payload, consume=True)

    def _guard_bb(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check(producer, payload, consume=False)

    def _check(self, producer: str, payload: dict[str, object], *, consume: bool) -> bool:
        if producer.strip() != REPLENISH_AGENT_ID:
            return False
        try:
            ReplenishmentRequested.model_validate(payload)
        except Exception:
            return False
        return accept_mac(
            self._authority,
            canonical_replenish(payload),
            payload.get("provenance_mac"),
            self._seen if consume else None,
        )
