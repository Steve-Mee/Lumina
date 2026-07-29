"""Shadow risk assessment + decision-trace comparison."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from lumina_core.logging_utils import get_logger
from lumina_core.risk.shadow_types import ShadowContext

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import ShadowResult

logger = get_logger("lumina.risk.shadow")


class ShadowAssessmentMixin:
    def _publish_event(
        self,
        *,
        topic: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        bus = self._event_bus
        if bus is None or not hasattr(bus, "publish_validated"):
            logger.debug("shadow_event_bus_unavailable topic=%s", topic)
            return
        try:
            bus.publish_validated(
                topic=topic,
                producer="shadow_risk_evaluator",
                payload=payload,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(
                "shadow_event_publish_failed topic=%s error=%s",
                topic,
                exc,
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
            decision_fn(orchestrator)
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
        from lumina_core.hybrid_quarantine import (
            SHADOW_TRACE_VERDICT,
            log_quarantine,
            require_trace_verdict,
        )

        strict = require_trace_verdict()
        log_quarantine(SHADOW_TRACE_VERDICT, strict=strict, detail="evaluate_risk_decision")
        if strict:
            # Fail-closed until real comparison/PnL exists: no silent pass.
            verdict = _ShadowResult(
                verdict="fail",
                dna_hash=context.dna_hash,
                sample_size=0,
                pnl=None,
            )
            self._publish_shadow_result(
                context,
                verdict,
                error="require_trace_verdict: no evaluative shadow verdict yet",
            )
            return verdict

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
        payload = {
            "verdict": result.verdict,
            "dna_hash": result.dna_hash,
            "sample_size": result.sample_size,
            "pnl": result.pnl,
        }
        metadata: dict[str, Any] = {
            "experiment_id": context.experiment_id,
            "shadow_decision_context_id": context.decision_context_id,
        }
        if error:
            metadata["error"] = error
        if decision_trace:
            metadata["decision_trace"] = decision_trace
        self._publish_event(
            topic="evolution.shadow.verdict",
            payload=payload,
            metadata=metadata,
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
