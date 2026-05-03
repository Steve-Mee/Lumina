from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.reasoning.agent_contracts import apply_agent_policy_gateway
from lumina_core.broker.broker_bridge import Order, OrderResult
from lumina_core.order_gatekeeper import enforce_pre_trade_gate


@dataclass(slots=True)
class PolicyEngine:
    engine: Any
    broker: Any

    def evaluate_proposal(
        self,
        *,
        signal: str,
        confluence_score: float,
        min_confluence: float,
        hold_until_ts: float,
        mode: str,
        session_allowed: bool,
        risk_allowed: bool,
        lineage: dict[str, Any] | None,
    ) -> dict[str, Any]:
        decision = apply_agent_policy_gateway(
            signal=signal,
            confluence_score=float(confluence_score),
            min_confluence=float(min_confluence),
            hold_until_ts=float(hold_until_ts),
            mode=str(mode).strip().lower(),
            session_allowed=bool(session_allowed),
            risk_allowed=bool(risk_allowed),
            lineage=lineage,
        )
        blackboard = getattr(self.engine, "blackboard", None)
        if blackboard is not None and hasattr(blackboard, "mark_policy_decision"):
            blackboard.mark_policy_decision(
                approved=bool(decision.get("approved", False)),
                reason=str(decision.get("reason", "")),
            )
        return decision

    def execute_order(self, order: Order, *, skip_final_arbitration: bool = False) -> OrderResult:
        if not bool(skip_final_arbitration):
            metadata = order.metadata if isinstance(order.metadata, dict) else {}
            reference_price = float(metadata.get("reference_price", 0.0) or 0.0)
            stop_loss = float(order.stop_loss or 0.0)
            fallback_risk = abs(reference_price - stop_loss) if reference_price > 0 and stop_loss > 0 else 0.0
            proposed_risk = float(metadata.get("proposed_risk", fallback_risk) or fallback_risk)
            allowed, reason = enforce_pre_trade_gate(
                self.engine,
                symbol=str(order.symbol),
                regime=str(metadata.get("regime", "NEUTRAL") or "NEUTRAL"),
                proposed_risk=float(proposed_risk),
                order_side=str(order.side).upper(),
            )
            if not allowed:
                return OrderResult(
                    accepted=False,
                    order_id="",
                    status="rejected",
                    message=f"AdmissionChain blocked order: {reason}",
                )
        if isinstance(order.metadata, dict):
            order.metadata["skip_admission_chain_recheck"] = True
        return self.broker.submit_order(order)
