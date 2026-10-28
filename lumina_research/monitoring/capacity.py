"""Per-signal, instrument, family, and correlation-cluster caps. Scale-back only."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, assert_never

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    CAPACITY_AGENT_ID,
    RESEARCH_CAPACITY_TOPIC,
    CapacityScaled,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.monitoring.config import ContinuityConfig
from lumina_research.monitoring.registry import LiveSignalRegistry
from lumina_research.monitoring.report import log_decision
from lumina_research.monitoring.seal import accept_mac, canonical_capacity
from lumina_research.monitoring.types import ContinuityRefused, LiveSignal


class CapacityController(Frozen):
    """Config-driven concentration caps. Never raises a signal's capacity_scale."""

    _bus: EventBus
    _registry: LiveSignalRegistry
    _authority: ProvenanceAuthority
    _config: ContinuityConfig
    _log_path: Path
    _blackboard: AgentBlackboard | None
    _evolution_log_dir: Path | None
    _events: list[CapacityScaled]
    _seen: set[str]

    def __init_subclass__(cls) -> None:
        raise TypeError("CapacityController cannot be subclassed")

    def __init__(
        self,
        *,
        bus: EventBus,
        registry: LiveSignalRegistry,
        authority: ProvenanceAuthority,
        config: ContinuityConfig,
        experiment_log_path: Path,
        blackboard: AgentBlackboard | None = None,
        evolution_log_dir: Path | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._authority = authority
        self._config = config
        self._log_path = experiment_log_path
        self._blackboard = blackboard
        self._evolution_log_dir = evolution_log_dir
        self._events = []
        self._seen = set()
        self._freeze()
        bus.register_topic_guard(RESEARCH_CAPACITY_TOPIC, self._guard)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_CAPACITY_TOPIC, self._guard_bb)

    def events(self) -> tuple[CapacityScaled, ...]:
        return tuple(self._events)

    def scale_up(self, signal_id: str, scale: float) -> None:
        del signal_id, scale
        raise ContinuityRefused("monitoring cannot increase exposure")

    def rebalance(self) -> tuple[LiveSignal, ...]:
        equity = float(self._config.equity)
        signals = [item for item in self._registry.signals() if item.stage != "retired"]
        instrument_sum = _sums(signals, "instrument")
        family_sum = _sums(signals, "family_id")
        cluster_sum = _sums(signals, "cluster_id")
        updated: list[LiveSignal] = []
        for signal in signals:
            notional = max(signal.effective_notional(), 1e-12)
            caps: list[tuple[str, float]] = [
                ("signal", _needed(signal.capacity_scale, notional, self._config.max_signal_notional_pct * equity)),
                (
                    "instrument",
                    _needed(
                        signal.capacity_scale,
                        max(instrument_sum.get(signal.instrument, notional), 1e-12),
                        self._config.max_instrument_notional_pct * equity,
                    ),
                ),
                (
                    "family",
                    _needed(
                        signal.capacity_scale,
                        max(family_sum.get(signal.family_id, notional), 1e-12),
                        self._config.max_family_notional_pct * equity,
                    ),
                ),
                (
                    "cluster",
                    _needed(
                        signal.capacity_scale,
                        max(cluster_sum.get(signal.cluster_id, notional), 1e-12),
                        self._config.max_cluster_notional_pct * equity,
                    ),
                ),
            ]
            reasons: list[str] = []
            proposed = signal.capacity_scale
            for name, scale in caps:
                if scale + 1e-12 < proposed:
                    proposed = scale
                    reasons.append(name)
            if proposed + 1e-12 >= signal.capacity_scale:
                continue
            previous = signal.capacity_scale
            changed = self._registry.apply_capacity_scale(signal.signal_id, proposed)
            self._emit(changed, previous_scale=previous, reasons=tuple(reasons))
            updated.append(changed)
        return tuple(updated)

    def _emit(self, signal: LiveSignal, *, previous_scale: float, reasons: tuple[str, ...]) -> None:
        if signal.capacity_scale > previous_scale:
            raise ContinuityRefused("monitoring cannot increase exposure")
        unsigned: dict[str, object] = {
            "schema_version": "research.capacity.scaled.v1",
            "signal_id": signal.signal_id,
            "instrument": signal.instrument,
            "family_id": signal.family_id,
            "cluster_id": signal.cluster_id,
            "agent_id": CAPACITY_AGENT_ID,
            "previous_scale": previous_scale,
            "new_scale": signal.capacity_scale,
            "reasons": list(reasons),
        }
        mac = self._authority.mac(canonical_capacity(unsigned))
        event = CapacityScaled.model_validate({**unsigned, "provenance_mac": mac})
        dumped = dump_json(event)
        self._bus.publish(topic=RESEARCH_CAPACITY_TOPIC, producer=CAPACITY_AGENT_ID, payload=dict(dumped))
        if self._blackboard is not None:
            self._blackboard.publish_sync(
                topic=RESEARCH_CAPACITY_TOPIC,
                producer=CAPACITY_AGENT_ID,
                payload=dict(dumped),
                confidence=1.0,
            )
        self._events.append(event)
        log_decision(
            path=self._log_path,
            agent_id=CAPACITY_AGENT_ID,
            event="capacity",
            signal_id=signal.signal_id,
            metrics=dumped,
            evolution_log_dir=self._evolution_log_dir,
        )

    def _guard(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check(producer, payload, consume=True)

    def _guard_bb(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check(producer, payload, consume=False)

    def _check(self, producer: str, payload: dict[str, object], *, consume: bool) -> bool:
        if producer.strip() != CAPACITY_AGENT_ID:
            return False
        try:
            parsed = CapacityScaled.model_validate(payload)
        except Exception:
            return False
        if parsed.new_scale > parsed.previous_scale:
            return False
        return accept_mac(
            self._authority,
            canonical_capacity(payload),
            payload.get("provenance_mac"),
            self._seen if consume else None,
        )


def _sums(signals: list[LiveSignal], attr: Literal["instrument", "family_id", "cluster_id"]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in signals:
        if attr == "instrument":
            key = str(item.instrument)
        elif attr == "family_id":
            key = item.family_id
        elif attr == "cluster_id":
            key = item.cluster_id
        else:
            assert_never(attr)
        out[key] = out.get(key, 0.0) + item.effective_notional()
    return out


def _needed(current_scale: float, current_notional: float, cap: float) -> float:
    if current_notional <= cap + 1e-12:
        return current_scale
    return max(0.0, current_scale * cap / current_notional)
