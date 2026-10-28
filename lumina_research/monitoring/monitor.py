"""Live performance monitor: detect decay and apply staged de-weight / suspend / retire."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence, assert_never

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    MONITOR_AGENT_ID,
    RESEARCH_DECAY_TOPIC,
    RESEARCH_DEWEIGHT_TOPIC,
    RESEARCH_RETIRE_TOPIC,
    RESEARCH_SUSPEND_TOPIC,
    DecayDetected,
    SignalDeweighted,
    SignalRetired,
    SignalStage,
    SignalSuspended,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.monitoring.config import ContinuityConfig
from lumina_research.monitoring.registry import LiveSignalRegistry
from lumina_research.monitoring.report import log_decision
from lumina_research.monitoring.seal import (
    canonical_decay,
    canonical_deweight,
    canonical_retire,
    canonical_suspend,
    mac_ok,
)
from lumina_research.monitoring.statistics import assess_decay
from lumina_research.monitoring.types import ContinuityRefused, DecayAssessment, LiveSignal, stage_rank


class LivePerformanceMonitor(Frozen):
    """Compares rolling live metrics to the sealed OOS distribution. Exposure only falls."""

    _bus: EventBus
    _registry: LiveSignalRegistry
    _authority: ProvenanceAuthority
    _config: ContinuityConfig
    _log_path: Path
    _blackboard: AgentBlackboard | None
    _evolution_log_dir: Path | None
    _series: dict[str, list[float]]
    _decay: list[DecayDetected]
    _deweights: list[SignalDeweighted]
    _suspends: list[SignalSuspended]
    _retires: list[SignalRetired]

    def __init_subclass__(cls) -> None:
        raise TypeError("LivePerformanceMonitor cannot be subclassed")

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
        self._series = {}
        self._decay = []
        self._deweights = []
        self._suspends = []
        self._retires = []
        self._freeze()
        bus.register_topic_guard(RESEARCH_DECAY_TOPIC, self._guard_decay)
        bus.register_topic_guard(RESEARCH_DEWEIGHT_TOPIC, self._guard_deweight)
        bus.register_topic_guard(RESEARCH_SUSPEND_TOPIC, self._guard_suspend)
        bus.register_topic_guard(RESEARCH_RETIRE_TOPIC, self._guard_retire)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_DECAY_TOPIC, self._guard_decay)
            blackboard.register_topic_guard(RESEARCH_DEWEIGHT_TOPIC, self._guard_deweight)
            blackboard.register_topic_guard(RESEARCH_SUSPEND_TOPIC, self._guard_suspend)
            blackboard.register_topic_guard(RESEARCH_RETIRE_TOPIC, self._guard_retire)

    def series(self, signal_id: str) -> tuple[float, ...]:
        return tuple(self._series.get(signal_id, ()))

    def decay_events(self) -> tuple[DecayDetected, ...]:
        return tuple(self._decay)

    def deweight_events(self) -> tuple[SignalDeweighted, ...]:
        return tuple(self._deweights)

    def suspend_events(self) -> tuple[SignalSuspended, ...]:
        return tuple(self._suspends)

    def retire_events(self) -> tuple[SignalRetired, ...]:
        return tuple(self._retires)

    def increase_weight(self, signal_id: str, weight: float) -> None:
        self._registry.increase_weight(signal_id, weight)

    def observe(self, signal_id: str, metric: float) -> LiveSignal:
        if not isinstance(metric, (int, float)) or isinstance(metric, bool):
            raise ContinuityRefused("non-finite live metric")
        value = float(metric)
        if not math.isfinite(value):
            raise ContinuityRefused("non-finite live metric")
        signal = self._registry.require(signal_id)
        history = self._series.setdefault(signal_id, [])
        history.append(value)
        assessment = assess_decay(history, signal.oos_values, self._config)
        if not assessment.ready:
            return signal
        return self._apply(signal, assessment)

    def apply_guardian_suspend(self, signal_id: str, reason: str) -> LiveSignal:
        signal = self._registry.require(signal_id)
        dummy = DecayAssessment(
            method=self._config.method,
            severity=2,
            stage="suspended",
            statistic=0.0,
            threshold=0.0,
            live_mean=None,
            oos_mean=signal.oos_mean,
            oos_stdev=signal.oos_stdev,
            percentile=None,
            cusum=None,
            sprt_llr=None,
            window=self._config.window,
            votes_deweight=0,
            votes_suspend=1,
            votes_retire=0,
            ready=True,
        )
        return self._apply(signal, dummy, reason_override=reason)

    def _apply(
        self,
        signal: LiveSignal,
        assessment: DecayAssessment,
        *,
        reason_override: str | None = None,
    ) -> LiveSignal:
        target = assessment.stage
        if stage_rank(target) <= stage_rank(signal.stage):
            return signal
        current = signal
        for nxt in _intermediate(signal.stage, target):
            previous_weight = current.weight
            current = self._registry.apply_stage(current.signal_id, nxt)
            reason = reason_override if reason_override is not None else f"decay:{assessment.method}:{nxt}"
            self._emit_decay(current, assessment, nxt)
            self._emit_stage(current, previous_weight=previous_weight, stage=nxt, reason=reason)
        return current

    def _emit_decay(self, signal: LiveSignal, assessment: DecayAssessment, stage: SignalStage) -> None:
        unsigned: dict[str, object] = {
            "schema_version": "research.decay.detected.v1",
            "signal_id": signal.signal_id,
            "hypothesis_id": signal.hypothesis_id,
            "config_id": signal.config_id,
            "trial_id": signal.trial_id,
            "agent_id": MONITOR_AGENT_ID,
            "method": self._config.method,
            "statistic": float(assessment.statistic),
            "threshold": float(assessment.threshold),
            "window": int(assessment.window),
            "live_mean": assessment.live_mean,
            "oos_mean": assessment.oos_mean,
            "oos_stdev": assessment.oos_stdev,
            "percentile": assessment.percentile,
            "cusum": assessment.cusum,
            "sprt_llr": assessment.sprt_llr,
            "stage": stage,
        }
        mac = self._authority.mac(canonical_decay(unsigned))
        event = DecayDetected.model_validate({**unsigned, "provenance_mac": mac})
        self._publish(RESEARCH_DECAY_TOPIC, dump_json(event), MONITOR_AGENT_ID)
        self._decay.append(event)
        log_decision(
            path=self._log_path,
            agent_id=MONITOR_AGENT_ID,
            event="decay",
            signal_id=signal.signal_id,
            metrics=dump_json(event),
            evolution_log_dir=self._evolution_log_dir,
        )

    def _emit_stage(
        self,
        signal: LiveSignal,
        *,
        previous_weight: float,
        stage: SignalStage,
        reason: str,
    ) -> None:
        if signal.weight > previous_weight:
            raise ContinuityRefused("monitoring cannot increase exposure")
        unsigned: dict[str, object] = {
            "signal_id": signal.signal_id,
            "hypothesis_id": signal.hypothesis_id,
            "config_id": signal.config_id,
            "trial_id": signal.trial_id,
            "agent_id": MONITOR_AGENT_ID,
            "previous_weight": previous_weight,
            "new_weight": signal.weight,
            "reason": reason,
        }
        if stage == "deweighted":
            unsigned["schema_version"] = "research.signal.deweighted.v1"
            mac = self._authority.mac(canonical_deweight(unsigned))
            event = SignalDeweighted.model_validate({**unsigned, "provenance_mac": mac})
            self._publish(RESEARCH_DEWEIGHT_TOPIC, dump_json(event), MONITOR_AGENT_ID)
            self._deweights.append(event)
            name = "deweight"
            metrics = dump_json(event)
        elif stage == "suspended":
            unsigned["schema_version"] = "research.signal.suspended.v1"
            mac = self._authority.mac(canonical_suspend(unsigned))
            event = SignalSuspended.model_validate({**unsigned, "provenance_mac": mac})
            self._publish(RESEARCH_SUSPEND_TOPIC, dump_json(event), MONITOR_AGENT_ID)
            self._suspends.append(event)
            name = "suspend"
            metrics = dump_json(event)
        elif stage == "retired":
            unsigned["schema_version"] = "research.signal.retired.v1"
            mac = self._authority.mac(canonical_retire(unsigned))
            event = SignalRetired.model_validate({**unsigned, "provenance_mac": mac})
            self._publish(RESEARCH_RETIRE_TOPIC, dump_json(event), MONITOR_AGENT_ID)
            self._retires.append(event)
            name = "retire"
            metrics = dump_json(event)
        elif stage == "active":
            raise ContinuityRefused("cannot emit an active-stage reduction")
        else:
            assert_never(stage)
        log_decision(
            path=self._log_path,
            agent_id=MONITOR_AGENT_ID,
            event=name,
            signal_id=signal.signal_id,
            metrics=metrics,
            evolution_log_dir=self._evolution_log_dir,
        )

    def _publish(self, topic: str, payload: dict[str, object], producer: str) -> None:
        self._bus.publish(topic=topic, producer=producer, payload=dict(payload))
        if self._blackboard is not None:
            self._blackboard.publish_sync(topic=topic, producer=producer, payload=dict(payload), confidence=1.0)

    def _guard_decay(self, producer: str, payload: dict[str, object]) -> bool:
        if producer.strip() != MONITOR_AGENT_ID:
            return False
        try:
            DecayDetected.model_validate(payload)
        except Exception:
            return False
        return mac_ok(self._authority, canonical_decay(payload), payload.get("provenance_mac"))

    def _guard_deweight(self, producer: str, payload: dict[str, object]) -> bool:
        if producer.strip() != MONITOR_AGENT_ID:
            return False
        try:
            parsed = SignalDeweighted.model_validate(payload)
        except Exception:
            return False
        if parsed.new_weight >= parsed.previous_weight:
            return False
        return mac_ok(self._authority, canonical_deweight(payload), payload.get("provenance_mac"))

    def _guard_suspend(self, producer: str, payload: dict[str, object]) -> bool:
        if producer.strip() != MONITOR_AGENT_ID:
            return False
        try:
            parsed = SignalSuspended.model_validate(payload)
        except Exception:
            return False
        if parsed.new_weight != 0.0 or parsed.new_weight > parsed.previous_weight:
            return False
        return mac_ok(self._authority, canonical_suspend(payload), payload.get("provenance_mac"))

    def _guard_retire(self, producer: str, payload: dict[str, object]) -> bool:
        if producer.strip() != MONITOR_AGENT_ID:
            return False
        try:
            parsed = SignalRetired.model_validate(payload)
        except Exception:
            return False
        if parsed.new_weight != 0.0:
            return False
        return mac_ok(self._authority, canonical_retire(payload), payload.get("provenance_mac"))


def _intermediate(current: SignalStage, target: SignalStage) -> Sequence[SignalStage]:
    order: tuple[SignalStage, ...] = ("active", "deweighted", "suspended", "retired")
    start = order.index(current)
    end = order.index(target)
    if end <= start:
        return ()
    return order[start + 1 : end + 1]
