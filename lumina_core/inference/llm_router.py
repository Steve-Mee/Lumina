from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lumina_core.inference.llm_client import LLMCallResult
from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.schemas import (
    ArbitrationCheckStep,
    ArbitrationResult,
    ArbitrationState,
    OrderIntent,
    OrderIntentMetadata,
)

NormalizedRoutingPath = Literal["llm_reasoning", "rule_based_fallback"]


class RoutedLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_context_id: str = Field(min_length=1)
    context: str = Field(min_length=1)
    routing_path: NormalizedRoutingPath
    llm_confidence: float = Field(ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)
    fallback: bool = False
    rule_based_rationale: str | None = None
    temperature: float = Field(ge=0.0)


class CapitalRoutingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routed: RoutedLLMOutput
    arbitration: ArbitrationResult
    executable_approved: bool
    real_never_llm_only: bool = True
    weighted_by_rules: bool = False


class LLMDecisionRouter:
    """Normalizes LLM outputs and enforces deterministic capital gating."""

    def __init__(self, *, low_confidence_threshold_real: float = 0.65) -> None:
        self.low_confidence_threshold_real = max(0.0, min(1.0, float(low_confidence_threshold_real)))

    @staticmethod
    def _normalize_path(raw_path: str) -> NormalizedRoutingPath:
        return "llm_reasoning" if str(raw_path) == "llm_reasoning" else "rule_based_fallback"

    @staticmethod
    def _extract_llm_confidence(payload: dict[str, Any], *, fallback: bool) -> float:
        for key in ("llm_confidence", "confidence", "meta_score"):
            if key in payload:
                try:
                    value = float(payload[key])
                    return max(0.0, min(1.0, value))
                except (TypeError, ValueError):
                    continue
        return 0.0 if fallback else 0.5

    def after_llm_call(self, result: LLMCallResult, *, context: str) -> RoutedLLMOutput:
        payload = dict(result.payload_out)
        normalized_path = self._normalize_path(result.path)
        llm_confidence = self._extract_llm_confidence(payload, fallback=result.fallback)
        payload["llm_confidence"] = llm_confidence
        if normalized_path == "rule_based_fallback":
            payload["signal"] = "HOLD"
            payload.setdefault("reason", result.error or "rule_based_fallback")
        return RoutedLLMOutput(
            decision_context_id=result.decision_context_id,
            context=context,
            routing_path=normalized_path,
            llm_confidence=llm_confidence,
            payload=payload,
            fallback=result.fallback or normalized_path == "rule_based_fallback",
            rule_based_rationale=result.error if normalized_path == "rule_based_fallback" else None,
            temperature=float(result.temperature),
        )

    def propose_order_from_llm(
        self,
        *,
        routed_output: RoutedLLMOutput,
        symbol: str,
        runtime_mode: str,
        current_state: ArbitrationState,
        final_arbitration: FinalArbitration,
        source_agent: str = "llm_router",
    ) -> CapitalRoutingResult:
        mode = str(runtime_mode or "paper").strip().lower()
        weighted_by_rules = False
        if mode == "real" and routed_output.llm_confidence < self.low_confidence_threshold_real:
            weighted_by_rules = True
            arbitration = ArbitrationResult(
                status="REJECTED",
                reason="llm_confidence_below_real_threshold",
                checks=[
                    ArbitrationCheckStep(
                        name="llm_confidence_threshold",
                        ok=False,
                        reason="confidence_too_low_for_real_order_path",
                    )
                ],
            )
            return CapitalRoutingResult(
                routed=routed_output,
                arbitration=arbitration,
                executable_approved=False,
                weighted_by_rules=weighted_by_rules,
            )

        signal = str(routed_output.payload.get("signal", "HOLD") or "HOLD").upper()
        if signal not in {"BUY", "SELL"}:
            arbitration = ArbitrationResult(
                status="REJECTED",
                reason="llm_signal_not_executable",
                checks=[ArbitrationCheckStep(name="signal_surface", ok=False, reason=f"signal={signal}")],
            )
            return CapitalRoutingResult(
                routed=routed_output,
                arbitration=arbitration,
                executable_approved=False,
                weighted_by_rules=weighted_by_rules,
            )

        quantity_raw = routed_output.payload.get("quantity", 1)
        try:
            quantity = max(1, int(quantity_raw))
        except (TypeError, ValueError):
            quantity = 1

        order_intent = OrderIntent(
            instrument=str(symbol).strip().upper(),
            side=signal,
            quantity=quantity,
            order_type=str(routed_output.payload.get("order_type", "MARKET") or "MARKET"),
            stop=float(routed_output.payload.get("stop", routed_output.payload.get("stop_loss", 0.0)) or 0.0),
            target=float(routed_output.payload.get("target", routed_output.payload.get("take_profit", 0.0)) or 0.0),
            reference_price=float(routed_output.payload.get("reference_price", 0.0) or 0.0),
            proposed_risk=float(routed_output.payload.get("proposed_risk", 0.0) or 0.0),
            regime=str(routed_output.payload.get("regime", "NEUTRAL") or "NEUTRAL"),
            confluence_score=float(routed_output.payload.get("confluence_score", 0.0) or 0.0),
            confidence=float(routed_output.llm_confidence),
            source_agent=str(source_agent or "llm_router"),
            metadata=OrderIntentMetadata(
                reason=str(routed_output.payload.get("reason", "llm_proposal") or "llm_proposal")
            ),
        )
        arbitration = final_arbitration.check(order_intent=order_intent, current_state=current_state)
        return CapitalRoutingResult(
            routed=routed_output,
            arbitration=arbitration,
            executable_approved=arbitration.status == "APPROVED",
            weighted_by_rules=weighted_by_rules,
        )

    @staticmethod
    def route_promotion_hint(*, llm_payload: dict[str, Any], context: str) -> dict[str, Any]:
        return {
            "context": context,
            "llm_recommendation": dict(llm_payload),
            "promoted": False,
            "requires_promotion_gate": True,
            "reason": "llm_cannot_promote_without_promotion_gate",
        }
