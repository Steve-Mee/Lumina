"""Lineage emit helpers for pre-trade gate (global residual)."""
from __future__ import annotations

import uuid
from typing import Any

from lumina_core.order_gatekeeper.engine_helpers import resolve_blackboard, resolve_event_bus
from lumina_core.order_gatekeeper.lineage_emitters import domain_event_fingerprint
from lumina_core.risk.admission_chain import AdmissionContext

def _resolve_decision_context_id(engine: Any) -> str:
    try:
        from lumina_core.risk.decision_lineage import decision_context_id_from_blackboard_event

        board = resolve_blackboard(engine)
        if board is not None and hasattr(board, "latest"):
            proposal_topics = (
                "agent.rl.proposal",
                "agent.news.proposal",
                "agent.emotional_twin.proposal",
                "agent.swarm.proposal",
                "agent.tape.proposal",
            )
            for topic in proposal_topics:
                ev = board.latest(topic)
                if ev is not None:
                    candidate = decision_context_id_from_blackboard_event(ev)
                    if candidate:
                        return str(candidate)
    except Exception:
        pass
    return f"gate:{uuid.uuid4().hex[:12]}"

def _emit_gate_entry_lineage(
    engine: Any,
    *,
    decision_context_id: str,
    symbol: str,
    proposed_risk: float,
    mode: str,
    order_side: str | None,
) -> None:
    try:
        bus = resolve_event_bus(engine)
        if bus is None or not hasattr(bus, "publish_validated"):
            return

        from lumina_core.agent_orchestration.schemas import GateEntryPayload
        from lumina_core.risk.decision_lineage import (
            decision_context_id_from_blackboard_event,
            decision_context_id_from_event,
            event_hash_from_event,
        )

        proposal_prev_hash = None
        proposal_topics = (
            "agent.rl.proposal",
            "agent.news.proposal",
            "agent.emotional_twin.proposal",
            "agent.swarm.proposal",
            "agent.tape.proposal",
        )

        try:
            if hasattr(bus, "history"):
                for topic in proposal_topics:
                    events = list(bus.history(topic, limit=20))
                    for ev in reversed(events):
                        if decision_context_id_from_event(ev) == str(decision_context_id):
                            proposal_prev_hash = event_hash_from_event(ev)
                            if proposal_prev_hash:
                                break
                    if proposal_prev_hash:
                        break
        except Exception:
            pass

        if not proposal_prev_hash:
            try:
                board = resolve_blackboard(engine)
                if board is not None and hasattr(board, "history"):
                    for topic in proposal_topics:
                        events = list(board.history(topic, limit=20))
                        for ev in reversed(events):
                            if decision_context_id_from_blackboard_event(ev) == str(decision_context_id):
                                proposal_prev_hash = event_hash_from_event(ev)
                                if proposal_prev_hash:
                                    break
                        if proposal_prev_hash:
                            break
            except Exception:
                pass

        if not proposal_prev_hash:
            try:
                if hasattr(bus, "history"):
                    dream_events = list(bus.history("trading_engine.dream_state.updated", limit=30))
                    for ev in reversed(dream_events):
                        if decision_context_id_from_event(ev) == str(decision_context_id):
                            proposal_prev_hash = event_hash_from_event(ev)
                            if proposal_prev_hash:
                                break
            except Exception:
                pass

        entry = GateEntryPayload(
            decision_context_id=decision_context_id,
            symbol=str(symbol),
            proposed_risk=float(proposed_risk),
            mode=mode,
            order_side=order_side,
        )

        gate_entry_meta = {"decision_context_id": decision_context_id}
        if proposal_prev_hash:
            gate_entry_meta["prev_hash"] = proposal_prev_hash

        published = bus.publish_validated(
            topic="admission.gate_entry",
            producer="order_gatekeeper",
            payload=entry.model_dump(mode="json"),
            metadata=gate_entry_meta,
        )
        seq = getattr(published, "metadata", {}).get("sequence") if published else None
        gate_entry_hash = None
        if published:
            try:
                gate_entry_hash = domain_event_fingerprint(published)
            except Exception:
                pass
        if seq or gate_entry_hash:
            if not hasattr(engine, "_pending_lineage_refs"):
                engine._pending_lineage_refs = {}
            engine._pending_lineage_refs["gate_entry"] = {
                "seq": seq,
                "hash": gate_entry_hash,
            }
    except Exception:
        pass

def _emit_final_risk_verdict(
    engine: Any,
    *,
    allowed: bool,
    reason: str,
    symbol: str,
    mode: str,
    decision_context_id: str,
    proposed_risk: float,
    admission_context: AdmissionContext,
    trace: Any,
) -> None:
    try:
        bus = resolve_event_bus(engine)
        if bus is None or not hasattr(bus, "publish_validated"):
            return

        from lumina_core.agent_orchestration.schemas import RiskVerdict

        deny_code = admission_context.metadata.get("deny_reason_code")
        last_step = getattr(trace, "last_step_id", None)
        verdict = RiskVerdict(
            approved=bool(allowed),
            reason=str(reason)[:300] if reason else None,
            limit=str(deny_code or last_step or ""),
            value=float(proposed_risk),
        )
        meta = {
            "symbol": str(symbol),
            "mode": str(mode),
            "decision_context_id": str(decision_context_id),
        }
        arb_ref = admission_context.metadata.get("final_arbitration_ref")
        if arb_ref:
            meta["final_arbitration_ref"] = arb_ref

        try:
            from lumina_core.risk.decision_lineage import decision_context_id_from_event

            if hasattr(bus, "history"):
                recent_arbs = [
                    e
                    for e in bus.history("risk.final_arbitration.result", limit=20)
                    if decision_context_id_from_event(e) == str(decision_context_id)
                ]
                if recent_arbs:
                    prev_event = recent_arbs[-1]
                    prev_hash = domain_event_fingerprint(prev_event)
                    meta["prev_hash"] = prev_hash
                    current_for_hash = {
                        "topic": "risk.policy.decision",
                        "producer": "order_gatekeeper",
                        "payload": verdict.model_dump(mode="json"),
                        "metadata": meta,
                    }
                    meta["event_hash"] = domain_event_fingerprint(
                        type("TempEvent", (), {"to_dict": lambda s: current_for_hash})()
                    )
        except Exception:
            pass

        bus.publish_validated(
            topic="risk.policy.decision",
            producer="order_gatekeeper",
            payload=verdict.model_dump(mode="json"),
            metadata=meta,
        )
    except Exception:
        pass
