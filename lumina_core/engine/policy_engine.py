from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from lumina_core.logging_utils import correlation_id, get_logger
from lumina_core.reasoning.agent_contracts import apply_agent_policy_gateway
from lumina_core.broker.broker_bridge import Order, OrderResult
from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.risk.decision_lineage import decision_context_id_from_event

logger = get_logger("lumina.risk.gatekeeper")


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
        decision_context_id = str((lineage or {}).get("decision_context_id", "")) or "policy_engine_evaluate"
        with correlation_id(decision_context_id):
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
            try:
                level = logging.INFO if bool(decision.get("approved", False)) else logging.WARNING
                logger.log(
                    level,
                    "policy.evaluate_proposal",
                    extra={
                        "event_data": {
                            "event": "policy.evaluate_proposal",
                            "approved": bool(decision.get("approved", False)),
                            "signal": str(signal),
                            "reason": str(decision.get("reason", "")),
                            "mode": str(mode),
                            "decision_context_id": decision_context_id,
                        }
                    },
                )
            except Exception:
                pass
        blackboard = getattr(self.engine, "blackboard", None)
        if blackboard is not None and hasattr(blackboard, "mark_policy_decision"):
            blackboard.mark_policy_decision(
                approved=bool(decision.get("approved", False)),
                reason=str(decision.get("reason", "")),
            )
        return decision

    def execute_order(self, order: Order) -> OrderResult:
        # Phase 1.3.2 (2026-05-31): B-001 HARD REMOVAL COMPLETE
        # The skip_final_arbitration parameter has been permanently removed.
        # The full authoritative gate now always runs for every order.
        # See evolution/log/2026-05-31-elon-phase1-3-2-hard-removal-proposal.md
        # (Executed under temporary user-authorized simulation for unblocking progress)

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
            try:
                logger.warning(
                    "policy.execute_order.rejected",
                    extra={
                        "event_data": {
                            "event": "policy.execute_order.rejected",
                            "symbol": str(order.symbol),
                            "side": str(order.side).upper(),
                            "reason": str(reason),
                        }
                    },
                )
            except Exception:
                pass
            return OrderResult(
                accepted=False,
                order_id="",
                status="rejected",
                message=f"AdmissionChain blocked order: {reason}",
            )

        # Defensive strip of any pre-1.3.3 legacy bypass metadata keys (B-004 remnant).
        # The authoritative gate is the only path; old shortcut keys must never reach the broker.
        if isinstance(order.metadata, dict):
            order.metadata.pop("skip_admission_chain_recheck", None)

        # Phase 2 Slice 15 (first downstream lineage step): Best-effort population of decision_context_id
        # so that order submission and downstream events can carry the same lineage root as the
        # pre-trade decision (Final Arbitration → submission).
        if isinstance(order.metadata, dict):
            if not order.metadata.get("decision_context_id"):
                # Try to recover from the last Final Arbitration event on the bus for this symbol
                try:
                    bus = getattr(self.engine, "event_bus", None)
                    if bus and hasattr(bus, "history"):
                        recent_arbs = [
                            e for e in bus.history("risk.final_arbitration.result", limit=20)
                            if str(getattr(e, "metadata", {}).get("symbol", "")) == str(order.symbol)
                        ]
                        if recent_arbs:
                            last_arb = recent_arbs[-1]
                            cid = decision_context_id_from_event(last_arb)
                            if cid:
                                order.metadata["decision_context_id"] = cid
                except Exception:
                    pass  # best-effort only

            # Phase 2 Slice 15: First downstream prev_hash link (Final Arbitration → submission)
            # Attach prev_hash pointing to the most recent Final Arbitration event for this ctx.
            cid = order.metadata.get("decision_context_id")
            if cid:
                try:
                    bus = getattr(self.engine, "event_bus", None)
                    if bus and hasattr(bus, "history"):
                        recent_arbs = [
                            e
                            for e in bus.history("risk.final_arbitration.result", limit=10)
                            if decision_context_id_from_event(e) == str(cid)
                        ]
                        if recent_arbs:
                            last_arb = recent_arbs[-1]
                            from lumina_core.order_gatekeeper import _domain_event_fingerprint
                            prev_hash = _domain_event_fingerprint(last_arb)
                            order.metadata["prev_hash"] = prev_hash
                            order.metadata["prev_event_topic"] = "risk.final_arbitration.result"
                except Exception:
                    pass  # best-effort only

        try:
            logger.info(
                "policy.execute_order.submit",
                extra={
                    "event_data": {
                        "event": "policy.execute_order.submit",
                        "symbol": str(order.symbol),
                        "side": str(order.side).upper(),
                    }
                },
            )
        except Exception:
            pass

        return self.broker.submit_order(order)
