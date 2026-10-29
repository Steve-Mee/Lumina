"""ValidationAgent: full Phase 1 pipeline, no shortcut. Always publishes a ValidationResult."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas_research import (
    RESEARCH_HYPOTHESIS_TOPIC,
    RESEARCH_VALIDATION_TOPIC,
    VALIDATION_AGENT_ID,
    HypothesisProposed,
    ValidationResult,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.experiment_log import log_experiment
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.payloads import (
    dsr_payload,
    dump_json,
    integrity_fields,
    json_float,
    oos_payload,
    pbo_payload,
    regime_payload,
    report_metric_fields,
    wfe_payload,
)
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.agents.synthetic import materialize
from lumina_research.validation.cost_model import MarketSnapshot, apply_costs
from lumina_research.validation.pipeline import CandidateEvaluation, evaluate_candidate, missing_evaluation
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import GateReport

_Evaluate = Callable[..., CandidateEvaluation]
Tape = tuple[tuple[float, ...], tuple[float, ...], tuple[MarketSnapshot, ...]]
Materializer = Callable[[HypothesisProposed], Tape]


class ValidationAgent(Frozen):
    """Buffers HypothesisProposed events, then runs evaluate_candidate for every variant."""

    _bus: EventBus
    _registry: TrialRegistry
    _authority: ProvenanceAuthority
    _log_path: Path
    _blackboard: AgentBlackboard | None
    _audit_path: Path
    _pending: list[HypothesisProposed]
    _evaluate: _Evaluate
    _equity: float
    _evaluations: list[CandidateEvaluation]
    _materialize: Materializer | None

    def __init_subclass__(cls) -> None:
        raise TypeError("ValidationAgent cannot be subclassed")

    def __init__(
        self,
        *,
        bus: EventBus,
        registry: TrialRegistry,
        authority: ProvenanceAuthority,
        experiment_log_path: Path,
        blackboard: AgentBlackboard | None = None,
        audit_path: Path | None = None,
        equity: float = 100_000.0,
        materializer: Materializer | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._authority = authority
        self._log_path = experiment_log_path
        self._blackboard = blackboard
        self._audit_path = audit_path if audit_path is not None else registry.audit_path
        self._pending = []
        self._evaluations = []
        self._evaluate = evaluate_candidate
        self._equity = float(equity)
        self._materialize = materializer
        self._freeze()
        bus.register_topic_guard(RESEARCH_VALIDATION_TOPIC, self._guard_validation)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_VALIDATION_TOPIC, self._guard_validation)
        bus.subscribe(RESEARCH_HYPOTHESIS_TOPIC, self._on_hypothesis)

    def _on_hypothesis(self, event: DomainEvent) -> None:
        self._pending.append(event.typed_payload(HypothesisProposed))

    def pending(self) -> tuple[HypothesisProposed, ...]:
        """Hypotheses buffered since the last ``flush`` (empty after a flush)."""
        return tuple(self._pending)

    def flush(self) -> tuple[ValidationResult, ...]:
        """Run the full Phase 1 pipeline for every pending hypothesis and publish."""
        batch = tuple(self._pending)
        self._pending.clear()
        self._evaluations.clear()
        if not batch:
            return ()
        nets = _peer_nets(batch, equity=self._equity, materialize_fn=self._tape)
        results: list[ValidationResult] = []
        for index, hypothesis in enumerate(batch):
            peers = tuple(nets[j] for j in range(len(nets)) if j != index)
            results.append(self._evaluate_one(hypothesis, peers))
        return tuple(results)

    def evaluations(self) -> tuple[CandidateEvaluation, ...]:
        """Phase 1 evaluations from the last ``flush`` (fitness uses GateReport only)."""
        return tuple(self._evaluations)

    def _evaluate_one(
        self,
        hypothesis: HypothesisProposed,
        peers: Sequence[Sequence[float]],
    ) -> ValidationResult:
        try:
            if int(hypothesis.expected_horizon_bars) < 1:
                raise ValueError("expected_horizon_missing")
            gross, positions, markets = self._tape(hypothesis)
            evaluation = self._evaluate(
                agent_id=VALIDATION_AGENT_ID,
                config_id=hypothesis.config_id,
                gross_returns=gross,
                positions=positions,
                markets=markets,
                spec=hypothesis.instrument,
                registry=self._registry,
                peer_net_returns=peers,
                audit_path=self._audit_path,
                equity=self._equity,
                is_size=int(hypothesis.is_size),
                oos_size=int(hypothesis.oos_size),
            )
        except Exception:
            evaluation = missing_evaluation(
                agent_id=VALIDATION_AGENT_ID,
                audit_path=self._audit_path,
                registry=self._registry,
            )
        self._evaluations.append(evaluation)
        trial_id = _latest_trial_id(self._registry, hypothesis.config_id)
        result = self._seal(hypothesis, evaluation.report, trial_id)
        dumped = dump_json(result)
        self._bus.publish(
            topic=RESEARCH_VALIDATION_TOPIC,
            producer=VALIDATION_AGENT_ID,
            payload=dict(dumped),
        )
        if self._blackboard is not None:
            self._blackboard.publish_sync(
                topic=RESEARCH_VALIDATION_TOPIC,
                producer=VALIDATION_AGENT_ID,
                payload=dict(dumped),
                confidence=1.0 if result.passed else 0.0,
            )
        reasons = result.reject_reasons
        log_experiment(
            path=self._log_path,
            agent_id=VALIDATION_AGENT_ID,
            event="validation",
            hypothesis_id=hypothesis.hypothesis_id,
            rationale=dump_json(hypothesis.rationale),
            metrics=dict(report_metric_fields(evaluation.report)),
            reject_reason=reasons[0] if reasons else None,
            failed_checks=reasons,
        )
        return result

    def _seal(
        self,
        hypothesis: HypothesisProposed,
        report: GateReport,
        trial_id: int,
    ) -> ValidationResult:
        fields: dict[str, object] = {
            "schema_version": "research.validation.result.v1",
            "hypothesis_id": hypothesis.hypothesis_id,
            "config_id": hypothesis.config_id,
            "trial_id": trial_id,
            "agent_id": VALIDATION_AGENT_ID,
            "passed": report.passed,
            "reject_reasons": list(report.reject_reasons),
            "oos_distribution": dump_json(oos_payload(report.oos_distribution)),
            "dsr": dump_json(dsr_payload(report.dsr)),
            "pbo": dump_json(pbo_payload(report.pbo)),
            "wfe": dump_json(wfe_payload(report.wfe)),
            "regimes": dump_json(regime_payload(report.regimes)),
            "n_oos_windows": report.n_oos_windows,
            "median_oos_after_costs": json_float(report.median_oos_after_costs),
            **integrity_fields(report),
        }
        digest, mac = self._authority.seal_validation(fields)
        median_raw = fields["median_oos_after_costs"]
        if isinstance(median_raw, bool) or not isinstance(median_raw, (int, float)):
            median_value: float | None = None
        else:
            median_value = float(median_raw)
        integrity = integrity_fields(report)
        return ValidationResult(
            hypothesis_id=hypothesis.hypothesis_id,
            config_id=hypothesis.config_id,
            trial_id=trial_id,
            agent_id=VALIDATION_AGENT_ID,
            passed=report.passed,
            reject_reasons=tuple(report.reject_reasons),
            oos_distribution=oos_payload(report.oos_distribution),
            dsr=dsr_payload(report.dsr),
            pbo=pbo_payload(report.pbo),
            wfe=wfe_payload(report.wfe),
            regimes=regime_payload(report.regimes),
            n_oos_windows=report.n_oos_windows,
            median_oos_after_costs=median_value,
            purge_applied=bool(integrity["purge_applied"]),
            embargo_applied=bool(integrity["embargo_applied"]),
            cost_applied=bool(integrity["cost_applied"]),
            cost_contract_root=str(integrity["cost_contract_root"]),
            cost_model_id=str(integrity["cost_model_id"]),
            regimes_complete=bool(integrity["regimes_complete"]),
            report_sha256=digest,
            provenance_mac=mac,
        )

    def _guard_validation(self, producer: str, payload: dict[str, object]) -> bool:
        return self._authority.guard_validation(producer, payload)

    def _tape(self, hypothesis: HypothesisProposed) -> Tape:
        mapper = self._materialize
        if mapper is None:
            return materialize(hypothesis)
        return mapper(hypothesis)


def _peer_nets(
    batch: tuple[HypothesisProposed, ...],
    *,
    equity: float,
    materialize_fn: Materializer,
) -> tuple[tuple[float, ...], ...]:
    nets: list[tuple[float, ...]] = []
    for hypothesis in batch:
        try:
            gross, positions, markets = materialize_fn(hypothesis)
            costed = apply_costs(
                gross_returns=gross,
                positions=positions,
                equity=equity,
                spec=hypothesis.instrument,
                markets=markets,
            )
            nets.append(costed.net_returns)
        except Exception:
            nets.append(())
    return tuple(nets)


def _latest_trial_id(registry: TrialRegistry, config_id: str) -> int:
    for record in reversed(registry.records()):
        if record.config_id == config_id:
            return record.trial_id
    raise RuntimeError(f"trial missing for config_id={config_id}")
