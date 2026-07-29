"""SelfEvolutionMetaAgent façade — nightly helpers live in ``meta_agent_nightly``.

Public symbols and compat re-exports remain importable from this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..evolution.dna_registry import DNARegistry, PolicyDNA
from ..evolution.evolution_guard import EvolutionGuard
from .lumina_engine import LuminaEngine
from .evolution_lifecycle import EvolutionLifecycleManager
from .errors import ErrorSeverity, LuminaError
from lumina_core.risk.risk_controller import HardRiskController
from .valuation_engine import ValuationEngine
from .anomaly_detector import AnomalyDetector
from lumina_core.evolution.audit_writer import EvolutionAuditWriter
from .proposal_generator import ProposalGenerator
from lumina_core.evolution.mutation_executor import apply_evolution_candidate
from lumina_core.evolution.nightly_cycle import run_nightly_evolution_cycle
from .meta_agent_nightly import MetaAgentNightlyMixin


@dataclass(slots=True)
class SelfEvolutionMetaAgent(MetaAgentNightlyMixin):
    """Nightly self-evolution orchestrator for Lumina v50.

    Safety contract:
    - Never disables or bypasses RiskController.
    - Auto-apply is blocked when risk enforcement is not active.
    - All decisions are append-only logged with hash chaining.
    """

    engine: LuminaEngine
    valuation_engine: ValuationEngine
    risk_controller: HardRiskController | None
    enabled: bool = True
    approval_required: bool = True
    sim_mode: bool = False
    aggressive_evolution: bool = False
    max_mutation_depth: str = "conservative"
    log_path: Path = field(default_factory=lambda: Path("state/evolution_log.jsonl"))
    obs_service: Any | None = None  # Optional ObservabilityService; injected at runtime
    auto_fine_tuning_enabled: bool = True
    min_acceptance_rate: float = 0.4
    drift_threshold: float = 0.25
    ppo_trainer: Any | None = None
    rl_environment: Any | None = None
    lifecycle_manager: EvolutionLifecycleManager | None = None
    blackboard: Any | None = None
    dna_registry: DNARegistry = field(default_factory=DNARegistry)
    runtime_mode: str = "real"
    evolution_guard: EvolutionGuard = field(default_factory=EvolutionGuard)
    _audit_writer: EvolutionAuditWriter | None = field(init=False, default=None, repr=False, compare=False)
    _anomaly_detector: AnomalyDetector | None = field(init=False, default=None, repr=False, compare=False)
    _proposal_generator: ProposalGenerator | None = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._audit_writer = EvolutionAuditWriter(
            log_path=self.log_path,
            decision_log_provider=lambda: getattr(self.engine, "decision_log", None),
        )
        self._anomaly_detector = AnomalyDetector(owner=self, audit_writer=self._audit_writer)
        self._proposal_generator = ProposalGenerator(owner=self)

    @classmethod
    def from_container(
        cls,
        *,
        container: Any,
        enabled: bool = True,
        approval_required: bool = True,
        mode: str = "real",
        aggressive_evolution: bool = False,
        max_mutation_depth: str = "conservative",
        obs_service: Any | None = None,
        fine_tuning_cfg: dict[str, Any] | None = None,
    ) -> "SelfEvolutionMetaAgent":
        engine = getattr(container, "engine", None)
        if engine is None:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_ENGINE_MISSING",
                message="ApplicationContainer-like object must expose .engine",
            )

        valuation_engine = getattr(container, "valuation_engine", None)
        if not isinstance(valuation_engine, ValuationEngine):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_VALUATION_ENGINE_MISSING",
                message="Container must expose .valuation_engine as ValuationEngine instance.",
            )

        risk_controller = getattr(container, "risk_controller", None)
        if risk_controller is None:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_RISK_CONTROLLER_MISSING",
                message="Container must expose .risk_controller.",
            )

        if not isinstance(fine_tuning_cfg, dict):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_FINE_TUNING_CONFIG_MISSING",
                message="fine_tuning_cfg must be an explicit dict in dev-only runtime.",
            )
        ft_cfg = fine_tuning_cfg

        mode_key = str(mode).strip().lower()
        if mode_key not in {"sim", "paper", "real"}:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_MODE_INVALID",
                message=f"Unsupported evolution mode: {mode_key}",
            )

        return cls(
            engine=engine,
            valuation_engine=valuation_engine,
            risk_controller=risk_controller,
            enabled=enabled,
            approval_required=bool(False if mode_key == "sim" else approval_required),
            sim_mode=bool(mode_key == "sim"),
            aggressive_evolution=bool(aggressive_evolution or mode_key == "sim"),
            max_mutation_depth=str(max_mutation_depth).strip().lower(),
            obs_service=obs_service,
            auto_fine_tuning_enabled=bool(ft_cfg["auto_trigger"]),
            min_acceptance_rate=float(ft_cfg["min_acceptance"]),
            drift_threshold=float(ft_cfg["drift_threshold"]),
            ppo_trainer=getattr(container, "ppo_trainer"),
            rl_environment=getattr(container, "rl_environment"),
            blackboard=getattr(container, "blackboard"),
            runtime_mode=mode_key,
        )

    def run_nightly_evolution(self, *, nightly_report: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
        return run_nightly_evolution_cycle(self, nightly_report=nightly_report, dry_run=dry_run)

    def _apply_candidate(self, candidate: dict[str, Any]) -> None:
        apply_evolution_candidate(self, candidate)

    def _dna_registry(self) -> DNARegistry:
        return self.dna_registry

    # Split-module delegation wrappers (must be defined last).
    def _log_agent_decision(
        self,
        *,
        raw_input: dict[str, Any],
        raw_output: dict[str, Any],
        confidence: float,
        policy_outcome: str,
        decision_context_id: str,
        evolution_log_hash: str | None = None,
    ) -> None:
        assert self._audit_writer is not None
        self._audit_writer.log_agent_decision(
            raw_input=raw_input,
            raw_output=raw_output,
            confidence=confidence,
            policy_outcome=policy_outcome,
            decision_context_id=decision_context_id,
            evolution_log_hash=evolution_log_hash,
            is_real_mode=not bool(self.sim_mode),
        )

    def _external_release_gates_ok(self) -> bool:
        assert self._anomaly_detector is not None
        return self._anomaly_detector.external_release_gates_ok()

    def _shadow_rollout_evidence_ok(self) -> bool:
        assert self._anomaly_detector is not None
        return self._anomaly_detector.shadow_rollout_evidence_ok()

    def _auto_fine_tuning_trigger(self, *, meta_review: dict[str, Any]) -> dict[str, Any]:
        assert self._anomaly_detector is not None
        return self._anomaly_detector.auto_fine_tuning_trigger(meta_review=meta_review)

    def _entries_last_3_days(self) -> list[dict[str, Any]]:
        assert self._audit_writer is not None
        return self._audit_writer.entries_last_3_days()

    def _acceptance_rate_3d(self) -> float:
        assert self._anomaly_detector is not None
        return self._anomaly_detector.acceptance_rate_3d()

    def _max_drift_3d_from_log(self) -> float:
        assert self._anomaly_detector is not None
        return self._anomaly_detector.max_drift_3d_from_log()

    def _compute_meta_review_metrics(self, report: dict[str, Any]) -> dict[str, Any]:
        assert self._anomaly_detector is not None
        return self._anomaly_detector.compute_meta_review_metrics(report)

    def _meta_swarm_nightly_payload(self, report: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        assert self._anomaly_detector is not None
        return self._anomaly_detector.meta_swarm_nightly_payload(report, base)

    def _meta_review(self, report: dict[str, Any]) -> dict[str, Any]:
        assert self._anomaly_detector is not None
        return self._anomaly_detector.meta_review(report)

    def _current_champion(self) -> dict[str, Any]:
        assert self._proposal_generator is not None
        return self._proposal_generator.current_champion()

    def _build_challengers(self, champion: dict[str, Any], meta_review: dict[str, Any]) -> list[dict[str, Any]]:
        assert self._proposal_generator is not None
        return self._proposal_generator.build_challengers(champion, meta_review)

    def _score_challenger(
        self,
        champion: dict[str, Any],
        challenger: dict[str, Any],
        report: dict[str, Any],
        meta_review: dict[str, Any],
    ) -> dict[str, Any]:
        assert self._proposal_generator is not None
        return self._proposal_generator.score_challenger(champion, challenger, report, meta_review)

    def _dna_fitness(self, meta_review: dict[str, Any]) -> float:
        assert self._anomaly_detector is not None
        return self._anomaly_detector.dna_fitness(meta_review)

    def _top_ranked_dna(self, *, active_dna: PolicyDNA | None) -> list[PolicyDNA]:
        assert self._proposal_generator is not None
        return self._proposal_generator.top_ranked_dna(active_dna=active_dna)

    def _genetic_fitness(self, nightly_report: dict[str, Any]) -> float:
        return ProposalGenerator.genetic_fitness(
            nightly_report,
            float(getattr(self.engine.config, "drawdown_kill_percent", 8.0) or 8.0),
        )

    def _build_genetic_candidates(
        self,
        *,
        champion: dict[str, Any],
        top_dna: list[PolicyDNA],
        nightly_report: dict[str, Any],
        meta_review: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, PolicyDNA]]:
        assert self._proposal_generator is not None
        return self._proposal_generator.build_genetic_candidates(
            champion=champion,
            top_dna=top_dna,
            nightly_report=nightly_report,
            meta_review=meta_review,
            fitness_score=self._genetic_fitness(nightly_report),
        )

    def _promote_winning_dna(
        self,
        *,
        active_dna: PolicyDNA | None,
        winner_dna: PolicyDNA | None,
        should_promote: bool,
    ) -> PolicyDNA | None:
        assert self._proposal_generator is not None
        return self._proposal_generator.promote_winning_dna(
            active_dna=active_dna,
            winner_dna=winner_dna,
            should_promote=should_promote,
        )

    def _content_from_dna(self, dna: PolicyDNA) -> dict[str, Any]:
        return ProposalGenerator.content_from_dna(dna)

    def _prompt_source_from_dna(self, dna: PolicyDNA) -> str:
        return ProposalGenerator.prompt_source_from_dna(dna)

    def _normalized_hyperparams(self, dna: PolicyDNA, champion: dict[str, Any]) -> dict[str, float]:
        return ProposalGenerator.normalized_hyperparams(dna, champion)

    def _mutated_hyperparams(self, *, parent: PolicyDNA, scale: float, champion: dict[str, Any]) -> dict[str, float]:
        return ProposalGenerator.mutated_hyperparams(parent=parent, scale=scale, champion=champion)

    def _blended_hyperparams(
        self, *, left_parent: PolicyDNA, right_parent: PolicyDNA, champion: dict[str, Any]
    ) -> dict[str, float]:
        return ProposalGenerator.blended_hyperparams(
            left_parent=left_parent,
            right_parent=right_parent,
            champion=champion,
        )

    def _candidate_from_dna(self, dna: PolicyDNA) -> dict[str, Any]:
        return ProposalGenerator.candidate_from_dna(dna)

    def _register_active_dna(self, *, nightly_report: dict[str, Any], meta_review: dict[str, Any]) -> PolicyDNA | None:
        assert self._proposal_generator is not None
        return self._proposal_generator.register_active_dna(
            nightly_report=nightly_report,
            meta_review=meta_review,
            dna_fitness=self._dna_fitness(meta_review),
        )

    def _register_candidate_dna(
        self,
        *,
        active_dna: PolicyDNA | None,
        best: dict[str, Any] | None,
        nightly_report: dict[str, Any],
        meta_review: dict[str, Any],
    ) -> PolicyDNA | None:
        assert self._proposal_generator is not None
        return self._proposal_generator.register_candidate_dna(
            active_dna=active_dna,
            best=best,
            nightly_report=nightly_report,
            meta_review=meta_review,
            dna_fitness=self._dna_fitness(meta_review),
        )

    @staticmethod
    def _dna_summary(dna: PolicyDNA | None) -> dict[str, Any] | None:
        return ProposalGenerator.dna_summary(dna)

    def _prompt_fingerprint(self) -> str:
        assert self._proposal_generator is not None
        return self._proposal_generator.prompt_fingerprint()

    @staticmethod
    def _compute_regime_drift(regime_history: list[Any]) -> float:
        return AnomalyDetector.compute_regime_drift(regime_history)

    @staticmethod
    def _regime_breakdown(report: dict[str, Any]) -> dict[str, Any]:
        return AnomalyDetector.regime_breakdown(report)

    @staticmethod
    def _weakest_regime(meta_review: dict[str, Any]) -> str:
        return AnomalyDetector.weakest_regime(meta_review)

    @staticmethod
    def _compute_rl_drift(report: dict[str, Any]) -> float:
        return AnomalyDetector.compute_rl_drift(report)

    def _compute_emotional_twin_accuracy(self, report: dict[str, Any]) -> float:
        return AnomalyDetector.compute_emotional_twin_accuracy(self.engine, report)

    def _append_immutable_log(self, entry: dict[str, Any]) -> None:
        assert self._audit_writer is not None
        self._audit_writer.append(entry)

    def _last_log_hash(self) -> str:
        assert self._audit_writer is not None
        return self._audit_writer.last_hash()


# Backward-compatible facade for dream_integration and legacy tests.
from lumina_bible.chroma_community import resolve_community_vector_collection
from lumina_core.evolution.evolution_orchestrator import EvolutionOrchestrator
from lumina_core.evolution.meta_agent_config import should_run_multi_gen_nightly

__all__ = [
    "EvolutionOrchestrator",
    "SelfEvolutionMetaAgent",
    "resolve_community_vector_collection",
    "should_run_multi_gen_nightly",
]
