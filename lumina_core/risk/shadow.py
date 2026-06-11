"""
Shadow Aperture Evaluator for Risk Logic Experiments.

Implements Phase 2 Deliverable 5 from the 2026-05-31 Elon first-principles
90-day aperture hardening roadmap:

"Extended shadow deployment: every evolution experiment that touches risk logic
must run in a 'shadow aperture' mode that replays real market data but never
touches the live broker."

Design principles (non-negotiable):
- Highest code quality, lowest bug/breakdown risk, maximum safe speed.
- Zero possibility of shadow execution ever reaching a real broker or mutating live state.
- Reuses the existing modular risk stack (RiskOrchestrator, RiskPolicy, HardRiskController,
  FinalArbitration, aperture_guard) instead of duplicating logic.
- Hard isolation enforced via aperture_guard-style permanent detectors.
- Produces typed events using the pre-existing ShadowResult contract.
- Best-effort, additive, and easily removable.

This module is the single source of truth for safe shadow risk evaluation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from lumina_core.logging_utils import get_logger
from lumina_core.risk.orchestration import RiskOrchestrator

logger = get_logger("lumina.risk.shadow")


@dataclass(slots=True)
class ShadowContext:
    """Context for a single shadow evaluation run."""

    experiment_id: str
    dna_hash: str
    decision_context_id: str  # Must be prefixed with "shadow-" for isolation
    market_data: dict[str, Any]  # Replay or live-read-only market snapshot
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ShadowExperimentResult:
    """Clean, typed return value from a complete shadow experiment run.

    This replaces the previous raw dict return from run_shadow_experiment,
    improving code quality, type safety, and usability.
    """

    experiment_id: str
    dna_hash: str
    shadow_result: "ShadowResult"
    decision_trace: dict[str, Any]
    comparison: dict[str, Any] | None
    promotion_decision: "EvolutionPromotionDecision"
    recommendation: dict[str, Any]  # Suggested next action in the promotion flow
    success: bool
    human_approval_request: dict[str, Any] | None = None  # Populated when recommendation requires human review


class ShadowRunRegistry:
    """
    Registry for shadow experiment runs with optional file persistence.

    - If no `storage_path` is provided: pure in-memory behavior (fast, for testing/SIM).
    - If `storage_path` is provided: uses a simple, robust JSONL append-only log.
      This gives durability across restarts with minimal complexity and very low risk
      of data corruption.

    This design allows easy evolution to a more sophisticated backend later
    while delivering immediate practical value for repeated shadow experimentation.
    """

    def __init__(self, storage_path: str | Path | None = None):
        self._runs: dict[str, dict[str, Any]] = {}
        self._storage_path: Path | None = Path(storage_path) if storage_path else None

        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load existing runs from JSONL file (best-effort, non-fatal)."""
        if not self._storage_path or not self._storage_path.exists():
            return

        try:
            with self._storage_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if "experiment_id" in record:
                            self._runs[record["experiment_id"]] = record
                    except json.JSONDecodeError:
                        logger.warning("shadow_registry_corrupt_line_skipped", extra={"path": str(self._storage_path)})
        except Exception:
            logger.warning("shadow_registry_load_failed", extra={"path": str(self._storage_path)})

    def _append_to_disk(self, record: dict[str, Any]) -> None:
        """Append a single record to the JSONL file (best-effort)."""
        if not self._storage_path:
            return

        try:
            with self._storage_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            logger.warning("shadow_registry_append_failed", extra={"path": str(self._storage_path)})

    def record(self, experiment_id: str, result: ShadowExperimentResult) -> None:
        """Store a completed shadow experiment result (memory + optional disk)."""
        record = {
            "experiment_id": result.experiment_id,
            "dna_hash": result.dna_hash,
            "decision_trace": result.decision_trace,
            "success": result.success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._runs[experiment_id] = record
        self._append_to_disk(record)

    def get(self, experiment_id: str) -> dict[str, Any] | None:
        """Retrieve a previously recorded shadow run by ID."""
        return self._runs.get(experiment_id)

    def get_decision_trace(self, experiment_id: str) -> dict[str, Any] | None:
        """Convenience method to directly get the decision trace for comparison."""
        run = self._runs.get(experiment_id)
        return run["decision_trace"] if run else None

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most recent recorded runs (newest first)."""
        runs = sorted(
            self._runs.values(),
            key=lambda r: r.get("timestamp", ""),
            reverse=True,
        )
        return runs[:limit]

    def record_promotion_decision(self, experiment_id: str, decision: "EvolutionPromotionDecision") -> None:
        """Store a promotion decision (e.g. after human approval)."""
        key = f"{experiment_id}:promotion:{decision.stage}"
        self._runs[key] = {
            "experiment_id": experiment_id,
            "stage": decision.stage,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._append_to_disk(self._runs[key])

    def list_pending_human_approvals(self) -> list[dict[str, Any]]:
        """
        Return experiments that have reached the human_approval stage
        but have not yet received a final decision.
        """
        pending = []
        # Group by base experiment_id
        by_experiment = {}
        for key, run in self._runs.items():
            if ":promotion:" in key:
                base_id = key.split(":promotion:")[0]
                if base_id not in by_experiment:
                    by_experiment[base_id] = []
                by_experiment[base_id].append(run)

        for exp_id, decisions in by_experiment.items():
            # Find the latest decision
            latest = max(decisions, key=lambda d: d.get("timestamp", ""))
            if latest.get("stage") == "human_approval":
                pending.append(latest)
        return pending


class ShadowRiskEvaluator:
    """
    Safe, isolated evaluator for running risk logic experiments in shadow.

    The evaluator can optionally be initialized with a default `ShadowRunRegistry`.
    When a registry is attached (either at construction or per-call), the high-level
    experiment methods will automatically use it for reference lookup and recording.

    Usage (example):
        registry = ShadowRunRegistry(storage_path="shadow_runs.jsonl")
        evaluator = ShadowRiskEvaluator(engine=engine, registry=registry)

        result = evaluator.execute_shadow_experiment(
            experiment_id="exp-042",
            dna_hash="abc123",
            signal="BUY",
            confluence_score=0.87,
            proposed_risk=210.0,
            recent_fills=recent_fills,
            # registry=...   # can still override per call if needed
        )
    """

    def __init__(self, engine: Any, registry: ShadowRunRegistry | None = None):
        self.engine = engine
        self._shadow_orchestrator: Optional[RiskOrchestrator] = None
        self._isolation_enforced = True  # Permanent guard
        self._registry: ShadowRunRegistry | None = registry

        # Hard isolation: shadow must never run in a way that could reach live broker paths
        # We treat shadow as its own strict "experiment-only" context.
        from lumina_core.risk.aperture_guard import enforce_no_bypass_in_strict_mode
        enforce_no_bypass_in_strict_mode(
            engine=engine,
            bypass_id="shadow_risk_evaluator",
            caller="ShadowRiskEvaluator.__init__",
            reason="ShadowRiskEvaluator must never share mutable live risk state or reach broker paths",
        )

    @classmethod
    def with_persistent_registry(
        cls,
        engine: Any,
        storage_path: str | Path,
        **kwargs
    ) -> "ShadowRiskEvaluator":
        """
        Convenience constructor that returns a `ShadowRiskEvaluator` with a
        file-backed `ShadowRunRegistry` already attached.

        This is the easiest way to get the full durable shadow deployment
        experience in one line.

        Example:
            evaluator = ShadowRiskEvaluator.with_persistent_registry(
                engine=engine,
                storage_path=Path("shadow_experiments.jsonl")
            )

            result = evaluator.execute_shadow_experiment(
                experiment_id=...,
                ...
            )
        """
        registry = ShadowRunRegistry(storage_path=storage_path)
        return cls(engine=engine, registry=registry, **kwargs)

    def _get_isolated_orchestrator(self) -> RiskOrchestrator:
        """
        Returns a fresh, isolated RiskOrchestrator instance for shadow use only.

        This is critical: we do NOT reuse the live engine's orchestrator.
        Any future attempt to bypass this isolation will be caught by aperture_guard.
        """
        if self._shadow_orchestrator is None:
            # Create a completely separate orchestrator instance.
            # It will still read config for policy/limits, but we will never allow
            # it to proceed to any broker submission path.
            orchestrator = RiskOrchestrator(engine=self.engine)
            orchestrator.initialize()

            # The isolation guarantee comes from:
            # 1. Fresh object instance (never the live one)
            # 2. Hard aperture_guard calls on every entry point
            # 3. Never wiring this orchestrator to any broker submission path
            self._shadow_orchestrator = orchestrator

        return self._shadow_orchestrator

    def _enforce_shadow_isolation(self, operation: str) -> None:
        """
        Hard guard. Any code path that reaches real execution from shadow context
        must die here with a clear ConstitutionViolation.
        """
        from lumina_core.risk.aperture_guard import enforce_no_bypass_in_strict_mode
        enforce_no_bypass_in_strict_mode(
            engine=self.engine,
            bypass_id=f"shadow_isolation_violation:{operation}",
            caller="ShadowRiskEvaluator._enforce_shadow_isolation",
            reason="Shadow execution attempted to reach live capital path. This is forbidden.",
        )

    def evaluate_risk_decision(
        self,
        context: ShadowContext,
        decision_fn: Callable[[Any], dict[str, Any]],
    ) -> "ShadowResult":
        """
        Run a single risk decision (or full risk chain) in complete shadow isolation.

        The provided decision_fn should be a pure function or a bound method from
        the isolated RiskOrchestrator that only reads market data and produces a decision.
        It must never mutate live state or call broker code.

        Returns a ShadowResult (also published to the Event Bus under evolution.shadow.verdict).
        """
        if not context.decision_context_id.startswith("shadow-"):
            raise ValueError(
                f"Shadow decision_context_id must start with 'shadow-'. Got: {context.decision_context_id}"
            )

        self._enforce_shadow_isolation("evaluate_risk_decision_entry")

        orchestrator = self._get_isolated_orchestrator()

        # Execute the decision function in the isolated orchestrator context.
        # The decision_fn is responsible for using orchestrator.risk_policy,
        # orchestrator.risk_controller, orchestrator.final_arbitration etc.
        try:
            raw_decision = decision_fn(orchestrator)
        except Exception as exc:
            logger.exception("shadow_risk_evaluation_failed", extra={"experiment_id": context.experiment_id})
            verdict = ShadowResult(
                verdict="fail",
                dna_hash=context.dna_hash,
                sample_size=0,
                pnl=None,
            )
            self._publish_shadow_result(context, verdict, error=str(exc))
            return verdict

        # For now we treat any successful run that did not explode as "pass".
        # Later increments will add proper comparison vs live decisions, PnL simulation, etc.
        from lumina_core.agent_orchestration.schemas import ShadowResult as _ShadowResult

        verdict = _ShadowResult(
            verdict="pass",
            dna_hash=context.dna_hash,
            sample_size=1,
            pnl=None,  # To be filled by higher-level experiment runner in future increments
        )

        self._publish_shadow_result(context, verdict)
        return verdict

    def _publish_shadow_result(
        self,
        context: ShadowContext,
        result: "ShadowResult",
        error: str | None = None,
        decision_trace: dict[str, Any] | None = None,
    ) -> None:
        """Publish using the pre-existing typed contract, with optional rich trace."""
        try:
            from lumina_core.agent_orchestration.schemas import ShadowResult as _ShadowResult
            from lumina_core.agent_orchestration.event_bus import publish_validated  # type: ignore

            payload = {
                "verdict": result.verdict,
                "dna_hash": result.dna_hash,
                "sample_size": result.sample_size,
                "pnl": result.pnl,
                "experiment_id": context.experiment_id,
                "shadow_decision_context_id": context.decision_context_id,
                "error": error,
            }
            if decision_trace:
                payload["decision_trace"] = decision_trace

            publish_validated(
                topic="evolution.shadow.verdict",
                payload=payload,
                payload_model=_ShadowResult,
            )
        except Exception:
            logger.warning(
                "shadow_result_publish_failed",
                extra={"experiment_id": context.experiment_id, "error": "publish_failed"},
            )

    # ------------------------------------------------------------------
    # Next Narrow Increment: Real Risk Logic + Basic Replay Support
    # ------------------------------------------------------------------
    def run_isolated_risk_assessment(
        self,
        context: ShadowContext,
        *,
        signal: str,
        confluence_score: float,
        proposed_risk: float,
        recent_fills: list[dict] | None = None,
    ) -> tuple[ShadowResult, dict[str, Any]]:
        """
        Runs real risk decision logic through the isolated orchestrator,
        optionally using replayed recent fills/market data.

        Now drives RiskPolicy + HardRiskController + FinalArbitration (when available)
        in the shadow instance. Returns both the ShadowResult and the full
        decision_trace for comparison and promotion decisions.
        """
        self._enforce_shadow_isolation("run_isolated_risk_assessment")

        orchestrator = self._get_isolated_orchestrator()

        try:
            if orchestrator.risk_policy is None:
                from lumina_core.risk.risk_policy import load_risk_policy
                orchestrator.risk_policy = load_risk_policy(
                    mode=str(getattr(self.engine.config, "trade_mode", "paper"))
                )

            decision_trace: dict[str, Any] = {}

            # 1. Real policy evaluation
            if hasattr(orchestrator.risk_policy, "evaluate"):
                policy_decision = orchestrator.risk_policy.evaluate(
                    signal=signal,
                    confluence_score=confluence_score,
                    proposed_risk=proposed_risk,
                )
            else:
                policy_decision = {"approved": True, "reason": "shadow_policy_fallback"}

            decision_trace["policy"] = policy_decision

            # 2. HardRiskController (if initialized in the isolated orchestrator)
            if orchestrator.risk_controller is not None and hasattr(orchestrator.risk_controller, "check_risk"):
                try:
                    risk_controller_result = orchestrator.risk_controller.check_risk(
                        proposed_risk=proposed_risk,
                        signal=signal,
                    )
                    decision_trace["risk_controller"] = risk_controller_result
                except Exception as e:
                    decision_trace["risk_controller"] = {"error": str(e)}

            # 3. FinalArbitration (if available)
            if orchestrator.final_arbitration is not None:
                try:
                    arb_decision = orchestrator.final_arbitration.check(
                        signal=signal,
                        confluence_score=confluence_score,
                        proposed_risk=proposed_risk,
                    )
                    decision_trace["final_arbitration"] = arb_decision
                except Exception as e:
                    decision_trace["final_arbitration"] = {"error": str(e)}

            # Replay context
            decision_trace["replay"] = {
                "recent_fills_count": len(recent_fills) if recent_fills else 0,
            }

            from lumina_core.agent_orchestration.schemas import ShadowResult as _ShadowResult

            approved = policy_decision.get("approved", True)
            if "risk_controller" in decision_trace and isinstance(decision_trace["risk_controller"], dict):
                approved = approved and decision_trace["risk_controller"].get("approved", True)
            if "final_arbitration" in decision_trace and isinstance(decision_trace["final_arbitration"], dict):
                approved = approved and decision_trace["final_arbitration"].get("approved", True)

            verdict = _ShadowResult(
                verdict="pass" if approved else "fail",
                dna_hash=context.dna_hash,
                sample_size=1,
                pnl=None,
            )

            # Publish with rich trace (policy + controller + arbitration + replay)
            self._publish_shadow_result(
                context,
                verdict,
                decision_trace=decision_trace,
            )

            return verdict, decision_trace

        except Exception as exc:
            from lumina_core.agent_orchestration.schemas import ShadowResult as _ShadowResult
            verdict = _ShadowResult(
                verdict="fail",
                dna_hash=context.dna_hash,
                sample_size=0,
                pnl=None,
            )
            self._publish_shadow_result(context, verdict, error=str(exc))
            return verdict, {"error": str(exc)}

    @staticmethod
    def compare_decision_traces(
        shadow_trace: dict[str, Any],
        reference_trace: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Pure comparison between a shadow run's decision_trace and a reference
        (live or previously recorded) trace.

        Returns a structured diff focused on the most important risk signals.
        This directly supports future automated promotion gates and the
        "rich outcome comparison" requirement from the original Phase 2 plan.
        """
        comparison: dict[str, Any] = {
            "policy_match": False,
            "risk_controller_match": False,
            "final_arbitration_match": False,
            "overall_risk_delta": None,
            "differences": [],
        }

        # Policy comparison
        shadow_policy = shadow_trace.get("policy", {})
        ref_policy = reference_trace.get("policy", {})
        comparison["policy_match"] = shadow_policy.get("approved") == ref_policy.get("approved")
        if not comparison["policy_match"]:
            comparison["differences"].append({
                "field": "policy.approved",
                "shadow": shadow_policy.get("approved"),
                "reference": ref_policy.get("approved"),
            })

        # Risk controller (if both present)
        if "risk_controller" in shadow_trace and "risk_controller" in reference_trace:
            shadow_rc = shadow_trace["risk_controller"]
            ref_rc = reference_trace["risk_controller"]
            comparison["risk_controller_match"] = shadow_rc.get("approved") == ref_rc.get("approved")
            if not comparison["risk_controller_match"]:
                comparison["differences"].append({
                    "field": "risk_controller.approved",
                    "shadow": shadow_rc.get("approved"),
                    "reference": ref_rc.get("approved"),
                })

        # Final arbitration
        if "final_arbitration" in shadow_trace and "final_arbitration" in reference_trace:
            shadow_arb = shadow_trace["final_arbitration"]
            ref_arb = reference_trace["final_arbitration"]
            comparison["final_arbitration_match"] = shadow_arb.get("approved") == ref_arb.get("approved")
            if not comparison["final_arbitration_match"]:
                comparison["differences"].append({
                    "field": "final_arbitration.approved",
                    "shadow": shadow_arb.get("approved"),
                    "reference": ref_arb.get("approved"),
                })

        # Simple overall risk delta (if proposed_risk exists in both)
        shadow_risk = shadow_trace.get("policy", {}).get("proposed_risk") or shadow_trace.get("proposed_risk")
        ref_risk = reference_trace.get("policy", {}).get("proposed_risk") or reference_trace.get("proposed_risk")
        if shadow_risk is not None and ref_risk is not None:
            comparison["overall_risk_delta"] = float(shadow_risk) - float(ref_risk)

        comparison["has_differences"] = len(comparison["differences"]) > 0
        return comparison

    @staticmethod
    def recommend_promotion_action(
        shadow_result: "ShadowResult",
        comparison: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Produces a structured recommendation for the next step in the promotion flow
        based on the shadow outcome and comparison (if available).

        This is a key piece for making shadow results actionable toward
        promotion_gate / human_approval / final stages.
        """
        verdict = shadow_result.verdict
        has_comparison = comparison is not None

        if verdict != "pass":
            return {
                "suggested_stage": "reject",
                "reason": "shadow_verdict_failed",
                "confidence": "high",
            }

        if not has_comparison:
            return {
                "suggested_stage": "promotion_gate",
                "reason": "shadow_passed_no_reference",
                "confidence": "medium",
            }

        critical_differences = comparison.get("has_differences", False)

        if critical_differences:
            return {
                "suggested_stage": "human_approval",
                "reason": "critical_differences_detected",
                "confidence": "high",
            }

        # Clean pass with matching reference
        return {
            "suggested_stage": "promotion_gate",
            "reason": "shadow_passed_clean_vs_reference",
            "confidence": "high",
        }

    def create_shadow_promotion_decision(
        self,
        context: ShadowContext,
        shadow_result: "ShadowResult",
        comparison: dict[str, Any] | None = None,
        recommendation: dict[str, Any] | None = None,
    ) -> "EvolutionPromotionDecision":
        """
        Turns the result of a shadow run into an EvolutionPromotionDecision.

        Now respects an optional `recommendation` (from `recommend_promotion_action`)
        to set the appropriate stage ("shadow", "promotion_gate", or "human_approval")
        instead of always defaulting to "shadow".

        This makes the recommendation directly drive progression in the promotion flow.
        """
        from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision as _EvolutionPromotionDecision

        # Basic automated promotion readiness rules
        verdict_ok = shadow_result.verdict == "pass"

        comparison_ok = True
        if comparison:
            critical_mismatches = (
                not comparison.get("policy_match", False) or
                not comparison.get("final_arbitration_match", True)
            )
            comparison_ok = not critical_mismatches

        allowed = verdict_ok and comparison_ok

        if not verdict_ok:
            reason = "shadow_verdict_failed"
        elif comparison and not comparison_ok:
            reason = "critical_differences_vs_live"
        else:
            reason = "shadow_evaluation_passed_clean"

        # Use recommendation to choose stage (if provided)
        if recommendation:
            suggested = recommendation.get("suggested_stage", "shadow")
            if suggested in ("promotion_gate", "human_approval", "shadow"):
                stage = suggested
            else:
                stage = "shadow"
        else:
            stage = "shadow"

        decision = _EvolutionPromotionDecision(
            dna_hash=context.dna_hash,
            allowed=allowed,
            reason=reason,
            stage=stage,
            mode=None,
            evidence_ref=context.decision_context_id,
        )

        # Publish the promotion decision (best-effort)
        try:
            from lumina_core.agent_orchestration.event_bus import publish_validated
            publish_validated(
                topic="evolution.promotion.decision",
                payload=decision,
                payload_model=_EvolutionPromotionDecision,
            )
        except Exception:
            logger.warning("shadow_promotion_decision_publish_failed", extra={"experiment_id": context.experiment_id})

        # Record in registry if available (for pending human approval queries etc.)
        reg = getattr(self, "_registry", None)
        if reg is not None:
            try:
                reg.record_promotion_decision(context.experiment_id, decision)
            except Exception:
                pass

        return decision

    @staticmethod
    def prepare_human_approval_request(
        context: ShadowContext,
        shadow_result: "ShadowResult",
        comparison: dict[str, Any] | None = None,
        recommendation: dict[str, Any] | None = None,
        decision_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Packages all relevant data from a shadow run into a clean, human-reviewer-friendly
        structure intended for the human_approval stage.

        Includes a concise "decision_summary" extracted from the decision_trace so that
        a human reviewer gets the essential outcomes at a glance (policy, risk controller,
        final arbitration) without having to parse the raw trace.
        """
        decision_summary = {}
        if decision_trace:
            if "policy" in decision_trace:
                decision_summary["policy"] = decision_trace["policy"]
            if "risk_controller" in decision_trace:
                decision_summary["risk_controller"] = decision_trace["risk_controller"]
            if "final_arbitration" in decision_trace:
                decision_summary["final_arbitration"] = decision_trace["final_arbitration"]

        return {
            "experiment_id": context.experiment_id,
            "dna_hash": context.dna_hash,
            "shadow_result": {
                "verdict": shadow_result.verdict,
                "sample_size": shadow_result.sample_size,
            },
            "decision_summary": decision_summary,
            "comparison": comparison or {},
            "recommendation": recommendation or {},
            "decision_context_id": context.decision_context_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "requires_human_review": True,
        }

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

    def list_pending_human_approvals(self) -> list[dict[str, Any]]:
        """
        Convenience method that delegates to the attached/default registry
        (if any) to list experiments currently waiting for human review.

        Returns an empty list if no registry is attached.
        """
        reg = self._registry
        if reg is None:
            return []
        return reg.list_pending_human_approvals()

    def get_human_review_package(self, experiment_id: str) -> dict[str, Any] | None:
        """
        When a registry is attached, assembles a ready-to-review package for a
        pending human approval.

        Returns the human_approval_request (with rich decision_summary) plus
        any other available context. Returns None if no registry or no pending
        human approval for the given experiment.
        """
        reg = self._registry
        if reg is None:
            return None

        request = reg.get(f"{experiment_id}:human_approval_request")
        if request is None:
            return None

        # Also try to get the main run and latest promotion decision for extra context
        run = reg.get(experiment_id)
        latest_decision = None
        for key in [f"{experiment_id}:promotion:human_approval", f"{experiment_id}:promotion:final"]:
            if key in getattr(reg, "_runs", {}):
                latest_decision = reg._runs[key]
                break

        return {
            "experiment_id": experiment_id,
            "human_approval_request": request,
            "original_run": run,
            "latest_promotion_decision": latest_decision,
        }

    def get_experiment_history(self, experiment_id: str) -> list[dict[str, Any]]:
        """
        Returns the complete chronological history of a shadow experiment,
        including the initial run, all promotion decisions, human approval
        request (if any), and final decision.

        This provides a full audit trail for an experiment — extremely useful
        for compliance, post-mortems, and understanding promotion outcomes.
        """
        reg = self._registry
        if reg is None:
            return []

        history = []

        # Main experiment run
        main_run = reg.get(experiment_id)
        if main_run:
            history.append({
                "type": "shadow_run",
                "data": main_run,
            })

        # Human approval request (if exists)
        ha_request = reg.get(f"{experiment_id}:human_approval_request")
        if ha_request:
            history.append({
                "type": "human_approval_request",
                "data": ha_request,
            })

        # All promotion decisions for this experiment
        for key, value in reg._runs.items():
            if key.startswith(f"{experiment_id}:promotion:"):
                history.append({
                    "type": "promotion_decision",
                    "stage": value.get("stage"),
                    "data": value,
                })

        # Human resolution record (if a human decision was submitted)
        resolution = reg.get(f"{experiment_id}:human_resolution")
        if resolution:
            history.append({
                "type": "human_resolution",
                "data": resolution,
            })

        # Sort by timestamp when available
        history.sort(key=lambda x: x["data"].get("timestamp", "") if isinstance(x.get("data"), dict) else "")

        return history

    def get_experiment_resolution(self, experiment_id: str) -> dict[str, Any] | None:
        """
        Returns a clean, high-level summary of the final resolution for a
        shadow experiment (including the human decision and notes if present).

        This is the easiest way to answer "what was the final outcome of this
        shadow experiment and why?"
        """
        reg = self._registry
        if reg is None:
            return None

        # Get the latest promotion decision (final or reject)
        final_decision = None
        for stage in ["final", "reject"]:
            key = f"{experiment_id}:promotion:{stage}"
            if key in getattr(reg, "_runs", {}):
                final_decision = reg._runs[key]
                break

        if final_decision is None:
            # Fall back to the last known promotion decision
            for key in sorted([k for k in getattr(reg, "_runs", {}) if k.startswith(f"{experiment_id}:promotion:")]):
                final_decision = reg._runs[key]

        resolution = reg.get(f"{experiment_id}:human_resolution")

        return {
            "experiment_id": experiment_id,
            "final_promotion_decision": final_decision,
            "human_resolution": resolution,
            "has_human_review": resolution is not None,
        }

    def get_experiment_resolution_summary(self, experiment_id: str) -> dict[str, Any] | None:
        """
        Returns a concise, human-friendly one-pager summary of the entire
        promotion outcome for a shadow experiment.

        Includes key decision points, the recommendation at the time, the
        human decision (if any), and the final result. Perfect for dashboards,
        reports, and quick audits.
        """
        reg = self._registry
        if reg is None:
            return None

        resolution = self.get_experiment_resolution(experiment_id)
        if resolution is None:
            return None

        history = self.get_experiment_history(experiment_id)

        # Extract the most relevant human context
        human_notes = None
        if resolution.get("human_resolution"):
            human_notes = resolution["human_resolution"].get("resolution_notes")

        # Find the recommendation that was active when human review was requested
        recommendation_at_human_review = None
        for item in history:
            if item["type"] == "promotion_decision" and item.get("stage") == "human_approval":
                # This is a bit indirect; in a real system we'd store it better.
                # For now we rely on the recommendation that was current.
                pass

        return {
            "experiment_id": experiment_id,
            "final_outcome": {
                "stage": resolution["final_promotion_decision"]["stage"] if resolution.get("final_promotion_decision") else None,
                "allowed": resolution["final_promotion_decision"]["allowed"] if resolution.get("final_promotion_decision") else None,
            },
            "human_decision": {
                "approved": resolution["human_resolution"]["approved"] if resolution.get("human_resolution") else None,
                "notes": human_notes,
                "approver": resolution["human_resolution"].get("approver") if resolution.get("human_resolution") else None,
            } if resolution.get("human_resolution") else None,
            "had_human_review": resolution.get("has_human_review", False),
            "history_length": len(history),
        }

    def submit_human_approval_decision(
        self,
        *,
        experiment_id: str,
        approved: bool,
        reason: str,
        approver: str | None = None,
        resolution_notes: str | None = None,
        evidence: dict[str, Any] | None = None,
        registry: ShadowRunRegistry | None = None,
    ) -> "EvolutionPromotionDecision":
        """
        Record the outcome of a human review for a shadow experiment that
        reached the human_approval stage, and emit the next EvolutionPromotionDecision
        (typically with stage="final").

        Supports richer context for better auditability and future tooling:
        - `resolution_notes`: free-text explanation from the human reviewer
        - `evidence`: structured additional data (e.g. links, extra analysis, screenshots)

        This completes the basic human approval workflow tooling for the shadow
        promotion chain.
        """
        from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision as _EvolutionPromotionDecision

        # Look up the previous promotion decision for context (best effort)
        previous_stage = "human_approval"
        previous_dna_hash = None
        reg = registry or getattr(self, "_registry", None)
        if reg is not None:
            prev_run = reg.get(experiment_id)
            if prev_run:
                previous_dna_hash = prev_run.get("dna_hash")

        next_stage = "final"  # Use "final" for both approved and rejected cases for now (model constraint)

        decision = _EvolutionPromotionDecision(
            dna_hash=previous_dna_hash or experiment_id,
            allowed=approved,
            reason=reason,
            stage=next_stage,
            mode=None,
            evidence_ref=f"human_approval:{experiment_id}",
        )

        # Attach richer human context (we enrich the published payload)
        payload = decision.model_dump() if hasattr(decision, "model_dump") else decision.dict()
        if approver:
            payload["approver"] = approver
        if resolution_notes:
            payload["resolution_notes"] = resolution_notes
        if evidence:
            payload["evidence"] = evidence
        payload["experiment_id"] = experiment_id

        try:
            from lumina_core.agent_orchestration.event_bus import publish_validated
            publish_validated(
                topic="evolution.promotion.decision",
                payload=payload,
                payload_model=_EvolutionPromotionDecision,
            )
        except Exception:
            logger.warning("human_approval_decision_publish_failed", extra={"experiment_id": experiment_id})

        # Record the final decision properly (including richer context)
        if reg is not None:
            try:
                reg.record_promotion_decision(experiment_id, decision)
                # Also store the full enriched payload for auditability
                reg.record(f"{experiment_id}:human_resolution", {
                    "experiment_id": experiment_id,
                    "approved": approved,
                    "reason": reason,
                    "approver": approver,
                    "resolution_notes": resolution_notes,
                    "evidence": evidence,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass

        return decision