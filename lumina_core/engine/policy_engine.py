from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_contracts import apply_agent_policy_gateway
from .broker_bridge import Order, OrderResult


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

    def execute_order(self, order: Order) -> OrderResult:
        return self.broker.submit_order(order)
