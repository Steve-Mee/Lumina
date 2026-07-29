"""Decision lineage reconstruction helpers (hash-chained risk path).

Read-only; no side effects on trading logic.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ValidationError

from lumina_core.agent_orchestration.event_bus import DomainEvent
from lumina_core.agent_orchestration.schemas import (
    EVENT_BUS_TOPIC_MODELS,
    EXECUTION_FILL_RECEIVED_TOPIC,
    typed_payload_from_event,
)


def _event_topic_key(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("topic", "") or "").strip().lower()
    return str(getattr(event, "topic", "") or "").strip().lower()


def event_metadata_from_event(event: Any) -> dict[str, Any]:
    """Metadata dict from DomainEvent or plain dict snapshots (e.g. bus.history)."""
    if isinstance(event, dict):
        meta = event.get("metadata", {})
        return meta if isinstance(meta, dict) else {}
    meta = getattr(event, "metadata", {}) or {}
    return meta if isinstance(meta, dict) else {}


def event_payload_from_event(event: Any) -> dict[str, Any]:
    """Payload dict from DomainEvent or plain dict snapshots."""
    if isinstance(event, dict):
        payload = event.get("payload", {})
        return payload if isinstance(payload, dict) else {}
    payload = getattr(event, "payload", {}) or {}
    return payload if isinstance(payload, dict) else {}


def _payload_model_for_topic(topic: str) -> type[BaseModel] | None:
    return EVENT_BUS_TOPIC_MODELS.get(str(topic).strip().lower())


def decision_context_id_from_event(event: Any) -> str:
    """Resolve decision_context_id from metadata first, then typed payload fields."""
    meta = event_metadata_from_event(event)
    cid = str(meta.get("decision_context_id", "") or "")
    if cid:
        return cid

    if not isinstance(event, dict):
        model = _payload_model_for_topic(_event_topic_key(event))
        if model is not None:
            try:
                inst = typed_payload_from_event(event, model)
                field_cid = getattr(inst, "decision_context_id", None)
                if field_cid:
                    return str(field_cid)
            except ValidationError:
                pass

    payload = event_payload_from_event(event)
    return str(payload.get("decision_context_id", "") or "")


def decision_context_id_from_blackboard_event(event: Any) -> str:
    """Blackboard lineage: metadata/typed cid first, then correlation_id."""
    cid = decision_context_id_from_event(event)
    if cid:
        return cid
    return str(getattr(event, "correlation_id", "") or "")


def event_hash_from_event(event: Any) -> str | None:
    """Best-effort event_hash from metadata or first-class attribute."""
    meta = getattr(event, "metadata", {}) or {}
    if isinstance(meta, dict):
        h = meta.get("event_hash")
        if h:
            return str(h)
    h = getattr(event, "event_hash", None)
    if h:
        return str(h)
    return None


def _payload_dict_from_event(event: Any) -> tuple[dict[str, Any], str | None]:
    """Return JSON-safe payload dict and optional Pydantic model name for chain export."""
    topic = _event_topic_key(event)
    model = _payload_model_for_topic(topic)
    if model is not None:
        try:
            inst = typed_payload_from_event(event, model)
            return inst.model_dump(mode="json", exclude_none=False), model.__name__
        except ValidationError:
            pass
    payload = getattr(event, "payload", {}) or {}
    if isinstance(payload, dict):
        return dict(payload), None
    return {}, None


def _outcome_label_for_chain_node(topic: str, payload: dict[str, Any]) -> str:
    """Human-oriented outcome string from a chain node (typed fields when present)."""
    if topic == "risk.final_arbitration.result":
        return str(payload.get("status") or payload.get("decision") or "unknown")
    if topic == "risk.policy.decision":
        approved = payload.get("approved")
        if approved is not None:
            return "approved" if approved else "rejected"
        return str(payload.get("reason") or "—")
    if topic == "admission.gate_entry":
        return str(payload.get("order_side") or payload.get("mode") or "entered")
    if topic in (EXECUTION_FILL_RECEIVED_TOPIC, "execution.fill"):
        return f"{payload.get('side', '')} {payload.get('quantity', '')} @ {payload.get('price', '')}".strip()
    return str(payload.get("status") or payload.get("signal") or payload.get("reason") or "—")


def _fingerprint(event: Any) -> str:
    """Compute a stable SHA256 fingerprint of a DomainEvent (or dict-like)."""
    if isinstance(event, DomainEvent):
        raw = event.to_dict()
    elif hasattr(event, "to_dict"):
        raw = event.to_dict()
    elif isinstance(event, dict):
        raw = event
    else:
        raw = {"repr": repr(event)}

    body = json.dumps(raw, sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reconstruct_risk_decision_chain(
    decision_context_id: str,
    *,
    event_bus: Any | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Reconstruct the ordered, hash-verified risk decision chain for a decision_context_id.

    Returns a list of events (most recent last) with the following shape:
    {
        "topic": str,
        "producer": str,
        "payload": dict,
        "metadata": dict,
        "event_hash": str,          # computed fingerprint of this event
        "prev_hash": str | None,    # expected previous hash (if present in metadata)
        "hash_ok": bool,            # whether prev_hash matches the actual previous event
    }

    If the chain is broken, the first broken event will have hash_ok=False and
    subsequent events may be partial.

    This is best-effort and read-only. It never mutates state or affects trading.
    """
    if not decision_context_id:
        return []

    if event_bus is None:
        # Best effort: try to get a global or engine-provided bus if available.
        # In most call sites the caller should pass the bus explicitly.
        try:
            # This is a bit of a hack; callers should prefer passing the bus.
            event_bus = None  # fallback will be handled by history checks below
        except Exception:
            event_bus = None

    if event_bus is None or not hasattr(event_bus, "history"):
        return []

    # Pull recent events from the key lineage topics (including the new gate entry root)
    try:
        arb_events = list(event_bus.history("risk.final_arbitration.result", limit=limit))
    except Exception:
        arb_events = []

    try:
        policy_events = list(event_bus.history("risk.policy.decision", limit=limit))
    except Exception:
        policy_events = []

    try:
        gate_entry_events = list(event_bus.history("admission.gate_entry", limit=limit))
    except Exception:
        gate_entry_events = []

    # Phase 2 Slice 10: Prefer main Event Bus for proposal events (now that they are dual-published).
    # Fall back to blackboard only if needed (handled by caller or future extension).
    proposal_events = []
    proposal_topics = [
        "agent.rl.proposal",
        "agent.news.proposal",
        "agent.emotional_twin.proposal",
        "agent.swarm.proposal",
        "agent.tape.proposal",
    ]
    for topic in proposal_topics:
        try:
            proposal_events.extend(list(event_bus.history(topic, limit=20)))
        except Exception:
            pass

    # Phase 2 Slice 12: Pull dream_state.updated events so reconstruction surfaces the earliest
    # upstream coordination/intention nodes (when they carry the shared decision_context_id).
    dream_events = []
    try:
        dream_events = list(event_bus.history("trading_engine.dream_state.updated", limit=30))
    except Exception:
        pass

    # Phase 2 Slice 18: Pull typed execution.fill.received events so the hash chain
    # continues into actual fills on the Event Bus.
    # Phase 2 Slice 20: This topic is now CRITICAL; future Guardian screaming rules
    # can treat malformed critical fill events (present but missing lineage) as loud anomalies.
    fill_events = []
    try:
        fill_events = list(event_bus.history("execution.fill.received", limit=50))
    except Exception:
        pass

    # Filter to the requested context
    ctx = str(decision_context_id)
    relevant: list[DomainEvent] = []
    for ev in arb_events + policy_events + gate_entry_events + proposal_events + dream_events + fill_events:
        if decision_context_id_from_event(ev) == ctx:
            relevant.append(ev)

    if not relevant:
        return []

    # Sort by sequence if available, otherwise by timestamp (best effort)
    def _sort_key(e: DomainEvent):
        meta = getattr(e, "metadata", {}) or {}
        return (int(meta.get("sequence", 0) or 0), getattr(e, "timestamp", ""))

    relevant.sort(key=_sort_key)

    # Build the reconstructed chain with hash verification
    chain: list[dict[str, Any]] = []
    prev_computed_hash: str | None = None

    for ev in relevant:
        meta = dict(getattr(ev, "metadata", {}) or {})
        payload, payload_model = _payload_dict_from_event(ev)
        topic = _event_topic_key(ev) or "unknown"

        current_hash = _fingerprint(ev)
        recorded_prev = meta.get("prev_hash")

        hash_ok = True
        if recorded_prev is not None and prev_computed_hash is not None:
            hash_ok = recorded_prev == prev_computed_hash

        node: dict[str, Any] = {
            "topic": topic,
            "producer": getattr(ev, "producer", "unknown"),
            "payload": payload,
            "metadata": meta,
            "event_hash": current_hash,
            "prev_hash": recorded_prev,
            "hash_ok": hash_ok,
        }
        if payload_model:
            node["payload_model"] = payload_model
        chain.append(node)

        prev_computed_hash = current_hash

    return chain


def is_chain_healthy(chain: list[dict[str, Any]]) -> bool:
    """Return True if every event in the reconstructed chain has hash_ok=True."""
    if not chain:
        return False
    return all(item.get("hash_ok", False) for item in chain)


def get_core_risk_decision_chain(decision_context_id: str, *, event_bus: Any | None = None) -> list[dict[str, Any]]:
    """
    Convenience wrapper that returns only the core risk decision nodes
    (Gate Entry → Risk Allocation → Final Arbitration) in order, if present.
    """
    full_chain = reconstruct_risk_decision_chain(decision_context_id, event_bus=event_bus, limit=50)
    if not full_chain:
        return []

    core_topics = {"admission.gate_entry", "risk.policy.decision", "risk.final_arbitration.result"}
    core_chain = [item for item in full_chain if item.get("topic") in core_topics]
    return core_chain
