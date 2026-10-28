"""ValidationAgent: full Phase 1 pipeline, no shortcut. Always publishes a ValidationResult."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

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
from lumina_research.agents.payloads import (
    dsr_payload,
    json_float,
    oos_payload,
    pbo_payload,
    regime_payload,
    report_metric_fields,
    wfe_payload,
)
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.agents.synthetic import materialize
from lumina_research.validation.cost_model import apply_costs
from lumina_research.validation.pipeline import evaluate_candidate
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import GateReport


class ValidationAgent:
    """Buffers HypothesisProposed events, then runs evaluate_candidate for every variant."""

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
    ) -> None:
        object.__setattr__(self, "_bus", bus)
        object.__setattr__(self, "_registry", registry)
        object.__setattr__(self, "_authority", authority)
        object.__setattr__(self, "_log_path", experiment_log_path)
        object.__setattr__(self, "_blackboard", blackboard)
        object.__setattr__(self, "_audit_path", audit_path if audit_path is not None else registry.audit_path)
        object.__setattr__(self, "_pending", [])
        object.__setattr__(self, "_evaluate", evaluate_candidate)
        bus.subscribe(RESEARCH_HYPOTHESIS_TOPIC, self._on_hypothesis)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ValidationAgent attributes are frozen")

    def _on_hypothesis(self, event: DomainEvent) -> None:
        pending: list[HypothesisProposed] = self._pending  # type: ignore[attr-defined]
        pending.append(event.typed_payload(HypothesisProposed))

    def pending(self) -> tuple[HypothesisProposed, ...]:
        pending: list[HypothesisProposed] = self._pending  # type: ignore[attr-defined]
        return tuple(pending)

    def flush(self) -> tuple[ValidationResult, ...]:
        pending: list[HypothesisProposed] = self._pending  # type: ignore[attr-defined]
        batch = tuple(pending)
        pending.clear()
        if not batch:
            return ()
        nets = _peer_nets(batch)
        results: list[ValidationResult] = []
        for index, hypothesis in enumerate(batch):
            peers = tuple(nets[j] for j in range(len(nets)) if j != index)
            results.append(self._evaluate_one(hypothesis, peers))
        return tuple(results)

    def _evaluate_one(
        self,
        hypothesis: HypothesisProposed,
        peers: Sequence[Sequence[float]],
    ) -> ValidationResult:
        gross, positions, markets = materialize(hypothesis)
        evaluate = self._evaluate  # type: ignore[attr-defined]
        registry: TrialRegistry = self._registry  # type: ignore[attr-defined]
        evaluation = evaluate(
            agent_id=VALIDATION_AGENT_ID,
            config_id=hypothesis.config_id,
            gross_returns=gross,
            positions=positions,
            markets=markets,
            spec=hypothesis.instrument,
            registry=registry,
            peer_net_returns=peers,
            audit_path=self._audit_path,  # type: ignore[attr-defined]
        )
        trial_id = _latest_trial_id(registry, hypothesis.config_id)
        result = self._seal(hypothesis, evaluation.report, trial_id)
        dumped = result.model_dump(mode="json", exclude_none=False)
        bus: EventBus = self._bus  # type: ignore[attr-defined]
        bus.publish(
            topic=RESEARCH_VALIDATION_TOPIC,
            producer=VALIDATION_AGENT_ID,
            payload=dumped,
        )
        board: AgentBlackboard | None = self._blackboard  # type: ignore[attr-defined]
        if board is not None:
            board.publish_sync(
                topic=RESEARCH_VALIDATION_TOPIC,
                producer=VALIDATION_AGENT_ID,
                payload=dumped,
                confidence=1.0 if result.passed else 0.0,
            )
        reasons = result.reject_reasons
        log_experiment(
            path=self._log_path,  # type: ignore[attr-defined]
            agent_id=VALIDATION_AGENT_ID,
            event="validation",
            hypothesis_id=hypothesis.hypothesis_id,
            rationale=hypothesis.rationale.model_dump(mode="json"),
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
            "oos_distribution": oos_payload(report.oos_distribution).model_dump(mode="json"),
            "dsr": dsr_payload(report.dsr).model_dump(mode="json"),
            "pbo": pbo_payload(report.pbo).model_dump(mode="json"),
            "wfe": wfe_payload(report.wfe).model_dump(mode="json"),
            "regimes": regime_payload(report.regimes).model_dump(mode="json"),
            "n_oos_windows": report.n_oos_windows,
            "median_oos_after_costs": json_float(report.median_oos_after_costs),
        }
        authority: ProvenanceAuthority = self._authority  # type: ignore[attr-defined]
        digest, mac = authority.seal_validation(fields)
        median = fields["median_oos_after_costs"]
        median_value: float | None
        if median is None or isinstance(median, float):
            median_value = median
        else:
            median_value = None
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
            report_sha256=digest,
            provenance_mac=mac,
        )


def _peer_nets(batch: tuple[HypothesisProposed, ...]) -> tuple[tuple[float, ...], ...]:
    nets: list[tuple[float, ...]] = []
    for hypothesis in batch:
        gross, positions, markets = materialize(hypothesis)
        costed = apply_costs(
            gross_returns=gross,
            positions=positions,
            equity=100_000.0,
            spec=hypothesis.instrument,
            markets=markets,
        )
        nets.append(costed.net_returns)
    return tuple(nets)


def _latest_trial_id(registry: TrialRegistry, config_id: str) -> int:
    for record in reversed(registry.records()):
        if record.config_id == config_id:
            return record.trial_id
    raise RuntimeError(f"trial missing for config_id={config_id}")
