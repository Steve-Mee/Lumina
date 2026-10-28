"""ReflectorAgent: propose only. The deterministic gate admits or rejects."""

from __future__ import annotations

from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    MUTATION_SCHEMA_VERSION,
    REFLECTOR_AGENT_ID,
    RESEARCH_MUTATION_TOPIC,
    EconomicRationale,
    MutationKind,
    MutationProposed,
    ParameterGenome,
    SignedReview,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.experiment_log import log_experiment
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.evolution.seal import canonical_mutation
from lumina_research.evolution.types import MutationRefused, require_feasible
from lumina_research.validation.trial_registry import TrialRegistry


class ReflectorRefused(ValueError):
    """Reflector tried to apply, promote, or skip the gate."""


class ReflectorAgent(Frozen):
    """Every propose() records a TrialRegistry trial. Apply/promote paths raise."""

    _bus: EventBus
    _registry: TrialRegistry
    _authority: ProvenanceAuthority
    _log_path: Path
    _blackboard: AgentBlackboard | None
    _proposed: list[MutationProposed]

    def __init_subclass__(cls) -> None:
        raise TypeError("ReflectorAgent cannot be subclassed")

    def __init__(
        self,
        *,
        bus: EventBus,
        registry: TrialRegistry,
        authority: ProvenanceAuthority,
        experiment_log_path: Path,
        blackboard: AgentBlackboard | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._authority = authority
        self._log_path = experiment_log_path
        self._blackboard = blackboard
        self._proposed = []
        self._freeze()
        bus.register_topic_guard(RESEARCH_MUTATION_TOPIC, self._guard)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_MUTATION_TOPIC, self._guard)

    def proposed(self) -> tuple[MutationProposed, ...]:
        return tuple(self._proposed)

    def apply(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ReflectorRefused("reflector can only propose")

    def emit_candidate(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ReflectorRefused("reflector can only propose")

    def set_thresholds(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ReflectorRefused("reflector cannot mutate gate thresholds")

    def set_risk_limits(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ReflectorRefused("reflector cannot mutate Risk Core")

    def skip_trial(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ReflectorRefused("every mutation must be counted in TrialRegistry")

    def propose(
        self,
        *,
        kind: MutationKind,
        target: str,
        genome: ParameterGenome,
        rationale: EconomicRationale,
        seed: int,
        parent_config_id: str,
        config_id: str,
        adr_path: str = "",
        review: SignedReview | None = None,
    ) -> MutationProposed:
        if not config_id.strip():
            raise MutationRefused("config_id is required")
        if not target.strip():
            raise MutationRefused("target is required")
        if kind in {"parameter_tune", "open_window", "noise"}:
            require_feasible(genome)
        trial_id = self._registry.record(
            config_id=config_id,
            agent_id=REFLECTOR_AGENT_ID,
            metrics={"phase": "mutate", "kind": kind, "target": target, "parent_config_id": parent_config_id},
        )
        unsigned: dict[str, object] = {
            "schema_version": MUTATION_SCHEMA_VERSION,
            "mutation_id": f"mut-{config_id}",
            "parent_config_id": parent_config_id,
            "config_id": config_id,
            "trial_id": trial_id,
            "agent_id": REFLECTOR_AGENT_ID,
            "kind": kind,
            "target": target,
            "seed": int(seed),
            "genome": dump_json(genome),
            "rationale": dump_json(rationale),
            "adr_path": adr_path,
            "review": dump_json(review) if review is not None else None,
        }
        mac = self._authority.mac(canonical_mutation(unsigned))
        payload = MutationProposed.model_validate({**unsigned, "provenance_mac": mac})
        dumped = dump_json(payload)
        self._bus.publish(
            topic=RESEARCH_MUTATION_TOPIC,
            producer=REFLECTOR_AGENT_ID,
            payload=dict(dumped),
        )
        if self._blackboard is not None:
            self._blackboard.publish_sync(
                topic=RESEARCH_MUTATION_TOPIC,
                producer=REFLECTOR_AGENT_ID,
                payload=dict(dumped),
                confidence=1.0,
            )
        self._proposed.append(payload)
        log_experiment(
            path=self._log_path,
            agent_id=REFLECTOR_AGENT_ID,
            event="mutation",
            hypothesis_id=payload.mutation_id,
            rationale=dump_json(rationale),
            metrics={
                "trial_id": trial_id,
                "kind": kind,
                "target": target,
                "config_id": config_id,
                "n_trials": self._registry.n_trials,
                "genome": dump_json(genome),
            },
            reject_reason=None,
            failed_checks=(),
        )
        return payload

    def _guard(self, producer: str, payload: dict[str, object]) -> bool:
        if producer.strip() != REFLECTOR_AGENT_ID:
            return False
        try:
            MutationProposed.model_validate(payload)
        except Exception:
            return False
        mac = payload.get("provenance_mac")
        if not isinstance(mac, str):
            return False
        return self._authority.mac_ok(canonical_mutation(payload), mac)
