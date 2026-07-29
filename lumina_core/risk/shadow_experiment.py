"""Shadow experiment run / execute helpers."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from lumina_core.logging_utils import get_logger
from lumina_core.risk.shadow_registry import ShadowRunRegistry
from lumina_core.risk.shadow_types import ShadowContext, ShadowExperimentResult

if TYPE_CHECKING:
    pass

logger = get_logger("lumina.risk.shadow")


class ShadowExperimentMixin:
    def run_shadow_experiment(
        self,
        *,
        experiment_id: str,
        dna_hash: str,
        signal: str,
        confluence_score: float,
        proposed_risk: float,
        recent_fills: list[dict] | None = None,
        reference_trace: dict[str, Any] | None = None,
        reference_experiment_id: str | None = None,
        registry: ShadowRunRegistry | None = None,
    ) -> ShadowExperimentResult:
        """
        High-level convenience method that runs a complete shadow experiment cycle:

        1. Creates proper ShadowContext
        2. Runs isolated risk assessment (with optional replay data)
        3. Performs comparison against reference (explicit or looked up via registry)
        4. Creates and publishes EvolutionPromotionDecision (stage="shadow")
        5. Auto-records the result in the registry (if provided)

        This is the primary, production-oriented entry point for running
        shadow experiments and feeding results into the promotion flow.
        """
        context = ShadowContext(
            experiment_id=experiment_id,
            dna_hash=dna_hash,
            decision_context_id=f"shadow-{experiment_id}",
            market_data={"recent_fills": recent_fills or []},
        )

        shadow_result, decision_trace = self.run_isolated_risk_assessment(
            context,
            signal=signal,
            confluence_score=confluence_score,
            proposed_risk=proposed_risk,
            recent_fills=recent_fills,
        )

        # Resolve reference trace (explicit > registry lookup)
        effective_reference = reference_trace
        if effective_reference is None and reference_experiment_id is not None:
            reg = registry or getattr(self, "_registry", None)
            if reg is not None:
                effective_reference = reg.get_decision_trace(reference_experiment_id)

        comparison = None
        if effective_reference is not None:
            comparison = self.compare_decision_traces(
                decision_trace,
                effective_reference,
            )

        recommendation = self.recommend_promotion_action(shadow_result, comparison)

        promotion_decision = self.create_shadow_promotion_decision(
            context,
            shadow_result,
            comparison=comparison,
            recommendation=recommendation,
        )

        human_approval_request = None
        if recommendation and recommendation.get("suggested_stage") == "human_approval":
            human_approval_request = self.prepare_human_approval_request(
                context,
                shadow_result,
                comparison=comparison,
                recommendation=recommendation,
                decision_trace=decision_trace,
            )

            # Record the human approval request in the registry so it can be retrieved later
            # for human review workflows (in addition to the main result).
            reg = registry or getattr(self, "_registry", None)
            if reg is not None and human_approval_request is not None:
                try:
                    reg.record(f"{experiment_id}:human_approval_request", human_approval_request)
                except Exception:
                    pass

        result = ShadowExperimentResult(
            experiment_id=experiment_id,
            dna_hash=dna_hash,
            shadow_result=shadow_result,
            decision_trace=decision_trace,
            comparison=comparison,
            promotion_decision=promotion_decision,
            recommendation=recommendation,
            human_approval_request=human_approval_request,
            success=promotion_decision.allowed,
        )

        # Auto-record if a registry is available
        reg = registry or getattr(self, "_registry", None)
        if reg is not None:
            reg.record(experiment_id, result)
            # Also record the promotion decision for pending queries
            try:
                reg.record_promotion_decision(experiment_id, promotion_decision)
            except Exception:
                pass

        return result

    def execute_shadow_experiment(
        self,
        *,
        experiment_id: str,
        dna_hash: str,
        signal: str,
        confluence_score: float,
        proposed_risk: float,
        recent_fills: list[dict] | None = None,
        registry: ShadowRunRegistry | None = None,
        reference_experiment_id: str | None = None,
        storage_path: str | Path | None = None,
    ) -> ShadowExperimentResult:
        """
        Recommended high-level entrypoint for running a complete, realistic
        shadow experiment.

        This is the primary, production-oriented way to use the shadow aperture.

        New convenience (this slice): `storage_path` parameter.
        If provided, a file-backed `ShadowRunRegistry` is created automatically.
        This is now the easiest and strongly recommended pattern for real use.

        Full recommended usage pattern (copy-paste example with one-line persistence):

            from lumina_core.risk.shadow import ShadowRiskEvaluator
            from pathlib import Path

            evaluator = ShadowRiskEvaluator(engine=engine)

            # Full realistic workflow with automatic durable persistence
            result = evaluator.execute_shadow_experiment(
                experiment_id="exp-2026-06-02",
                dna_hash="risk-policy-v1.2.4",
                signal="BUY",
                confluence_score=0.87,
                proposed_risk=185.0,
                recent_fills=recent_fills,
                storage_path=Path("shadow_experiments.jsonl"),   # ← new, easiest pattern
                reference_experiment_id="baseline-2026-06-01",   # optional
            )

            print(result.recommendation)
            print("Stage:", result.promotion_decision.stage)

            if result.human_approval_request:
                package = evaluator.get_human_review_package(result.experiment_id)
                # ... send to human reviewer ...

            # Human submits decision (persistence is automatic)
            evaluator.submit_human_approval_decision(
                experiment_id="exp-2026-06-02",
                approved=True,
                reason="Approved after review.",
                approver="risk-lead@company.com",
            )
        """
        # Convenience: if storage_path is provided, create a file-backed registry automatically
        effective_registry = registry
        if effective_registry is None and storage_path is not None:
            effective_registry = ShadowRunRegistry(storage_path=storage_path)

        return self.run_shadow_experiment(
            experiment_id=experiment_id,
            dna_hash=dna_hash,
            signal=signal,
            confluence_score=confluence_score,
            proposed_risk=proposed_risk,
            recent_fills=recent_fills,
            registry=effective_registry,
            reference_experiment_id=reference_experiment_id,
        )

    @classmethod
    def get_usage_example(cls) -> str:
        """
        Returns the recommended production usage pattern as a clean,
        copy-pasteable string.

        Preferred path for most callers (especially evolution / DNA change code):
            orchestrator = RiskOrchestrator(engine=engine)
            orchestrator.initialize()
            result = orchestrator.run_shadow_risk_experiment(...)   # or execute_...

        This is the official evolution-facing surface added for Phase 2 Deliverable 5.

        This serves as the official living reference for teams using
        the shadow aperture capability.
        """
        return '''\
# Recommended production usage of Shadow Deployment (Phase 2 Deliverable 5)

from lumina_core.risk.shadow import ShadowRiskEvaluator, ShadowRunRegistry

# 1. Create a durable registry (strongly recommended for real use)
registry = ShadowRunRegistry(storage_path="shadow_experiments.jsonl")

# 2. Create evaluator with the registry attached for maximum ergonomics
evaluator = ShadowRiskEvaluator(engine=engine, registry=registry)

# 3. (Optional but recommended) Run a "baseline" experiment first
baseline = evaluator.execute_shadow_experiment(
    experiment_id="baseline-2026-06-01",
    dna_hash="risk-policy-v1.2.3",
    signal="BUY",
    confluence_score=0.88,
    proposed_risk=180.0,
    recent_fills=recent_fills,
)

# 4. Later — run a new experiment (e.g. after a DNA change) against the baseline
result = evaluator.execute_shadow_experiment(
    experiment_id="exp-2026-06-02",
    dna_hash="risk-policy-v1.2.4",   # new version being tested in shadow
    signal="BUY",
    confluence_score=0.87,
    proposed_risk=185.0,
    recent_fills=newer_fills,
    reference_experiment_id="baseline-2026-06-01",
)

print("Recommendation:", result.recommendation)
print("Promotion decision stage:", result.promotion_decision.stage)

if result.human_approval_request:
    print("Human review required. Package:")
    print(evaluator.get_human_review_package(result.experiment_id))

# 5. Human review side (any process / dashboard / email)
pending = evaluator.list_pending_human_approvals()
for item in pending:
    package = evaluator.get_human_review_package(item["experiment_id"])
    # ... present to human reviewer ...

# 6. Human submits decision
evaluator.submit_human_approval_decision(
    experiment_id="exp-2026-06-02",
    approved=True,
    reason="Approved after review. Risk parameters are acceptable.",
    approver="risk-lead@company.com",
    registry=registry,
)

# The promotion decision with stage="final" has now been emitted.
'''
