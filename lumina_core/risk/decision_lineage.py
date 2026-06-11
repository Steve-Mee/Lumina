"""
Decision Lineage — Small reconstruction helpers for the critical risk decision path.

Phase 2 focus: Reconstruct and validate the hash-chained lineage between
`risk.policy.decision` and `risk.final_arbitration.result` for a given
decision_context_id, including upstream proposal and (Slice 12) dream/coordination roots.

This module is intentionally tiny and has no side effects on trading logic.
It is designed to be used by the Guardian, post-trade audits, and tests.
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
    return str(getattr(event, "topic", "") or "").strip().lower()


def _payload_model_for_topic(topic: str) -> type[BaseModel] | None:
    return EVENT_BUS_TOPIC_MODELS.get(str(topic).strip().lower())


def decision_context_id_from_event(event: Any) -> str:
    """Resolve decision_context_id from metadata first, then typed payload fields."""
    meta = getattr(event, "metadata", {}) or {}
    if not isinstance(meta, dict):
        meta = {}
    cid = str(meta.get("decision_context_id", "") or "")
    if cid:
        return cid

    model = _payload_model_for_topic(_event_topic_key(event))
    if model is not None:
        try:
            inst = typed_payload_from_event(event, model)
            field_cid = getattr(inst, "decision_context_id", None)
            if field_cid:
                return str(field_cid)
        except ValidationError:
            pass

    payload = getattr(event, "payload", {}) or {}
    if isinstance(payload, dict):
        return str(payload.get("decision_context_id", "") or "")
    return ""


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


def get_downstream_link_from_order(order: Any) -> dict[str, Any]:
    """
    Small helper (Slice 15) to extract the first downstream lineage link
    that was attached to an Order at the post-Final-Arbitration submission boundary.
    Returns empty dict if no link information is present.
    """
    if order is None:
        return {}
    metadata = getattr(order, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        return {}
    cid = metadata.get("decision_context_id")
    prev = metadata.get("prev_hash")
    prev_topic = metadata.get("prev_event_topic")
    if cid or prev:
        return {
            "decision_context_id": cid,
            "prev_hash": prev,
            "prev_event_topic": prev_topic,
        }
    return {}


# ---------------------------------------------------------------------------
# Phase 2 Slice 16: Tiny extraction helpers for downstream execution objects
# ---------------------------------------------------------------------------

def get_lineage_from_fill(fill: Any) -> dict[str, Any]:
    """Extract lineage fields (if present) from a Fill object.

    Phase 2 Slice 19: Prefers the new first-class fields on the dataclass;
    falls back to raw only for transition safety.
    """
    if fill is None:
        return {}

    # Prefer first-class fields (Slice 19)
    cid = getattr(fill, "decision_context_id", None)
    ph = getattr(fill, "prev_hash", None)
    pet = getattr(fill, "prev_event_topic", None)

    if cid or ph or pet:
        return {
            "decision_context_id": cid,
            "prev_hash": ph,
            "prev_event_topic": pet,
        }

    # Fallback to raw (for transition / older fills)
    raw = getattr(fill, "raw", {}) or {}
    if not isinstance(raw, dict):
        return {}
    return {
        "decision_context_id": raw.get("decision_context_id"),
        "prev_hash": raw.get("prev_hash"),
        "prev_event_topic": raw.get("prev_event_topic"),
    }


def get_lineage_from_order_result(result: Any) -> dict[str, Any]:
    """Extract lineage fields (if present) from an OrderResult (populated in Slice 16 + live broker wiring).
    Prefers first-class fields on the dataclass (post live-broker plan); falls back to raw for compat.
    """
    if result is None:
        return {}
    # Prefer first-class (added for CrossTrade live parity with Paper Slice 19/ live wiring)
    dcid = getattr(result, "decision_context_id", None)
    ph = getattr(result, "prev_hash", None)
    pet = getattr(result, "prev_event_topic", None)
    if dcid or ph or pet:
        return {
            "decision_context_id": dcid,
            "prev_hash": ph,
            "prev_event_topic": pet,
        }
    raw = getattr(result, "raw", {}) or {}
    if not isinstance(raw, dict):
        return {}
    return {
        "decision_context_id": raw.get("decision_context_id"),
        "prev_hash": raw.get("prev_hash"),
        "prev_event_topic": raw.get("prev_event_topic"),
    }


# ---------------------------------------------------------------------------
# Phase 2 Slice 17: Support for including fills in reconstruction and reports
# ---------------------------------------------------------------------------

def extend_chain_with_fills(
    base_chain: list[dict[str, Any]],
    fills: list[Any],
) -> list[dict[str, Any]]:
    """
    Small helper (Slice 17): Given a base reconstructed chain and a list of Fill
    objects, append any fills that carry a matching decision_context_id as
    downstream nodes.

    This keeps the core reconstruction function clean while allowing callers
    (especially the provenance report) to include execution data when available.
    """
    if not base_chain or not fills:
        return base_chain

    # Find the last node in the base chain to use as a reasonable prev for fills
    last_node = base_chain[-1] if base_chain else None
    last_hash = last_node.get("event_hash") if last_node else None
    last_topic = last_node.get("topic") if last_node else None

    extended = list(base_chain)

    for fill in fills:
        if fill is None:
            continue

        lineage = get_lineage_from_fill(fill)
        cid = lineage.get("decision_context_id")
        if not cid:
            continue

        # Only include fills that match the decision_context_id of the chain
        # (we assume the caller passes relevant fills; we do a best-effort match)
        # For simplicity in the first version, we include all fills that have a cid
        # and let the caller filter. A more sophisticated version could filter here.

        # Phase 2 Slice 23: Compute real cryptographic hash_ok for downstream fills.
        # Now that automatic fill data is available (Slice 22) and fills carry prev_hash,
        # we verify the link against the preceding event in the chain (usually final_arbitration).
        fill_prev_hash = lineage.get("prev_hash") or last_hash
        fill_prev_topic = lineage.get("prev_event_topic") or last_topic

        # Build the node first so we can fingerprint it
        fill_node = {
            "topic": "execution.fill",
            "producer": "broker",
            "payload": {
                "fill_id": getattr(fill, "fill_id", None),
                "symbol": getattr(fill, "symbol", None),
                "side": getattr(fill, "side", None),
                "quantity": getattr(fill, "quantity", None),
                "price": getattr(fill, "price", None),
                "commission": getattr(fill, "commission", None),
                "timestamp": getattr(fill, "timestamp", None),
            },
            "metadata": {
                "decision_context_id": cid,
                "prev_hash": fill_prev_hash,
                "prev_event_topic": fill_prev_topic,
            },
            "event_hash": None,
            "prev_hash": fill_prev_hash,
            "hash_ok": True,  # will be recomputed below
        }

        # Compute a proper event_hash for the fill node (using existing _fingerprint helper)
        fill_node["event_hash"] = _fingerprint(fill_node)

        # Verify cryptographic linkage: does this fill's prev_hash match the hash of the
        # preceding event in the chain (the last node from the base reconstruction)?
        if fill_prev_hash is not None and last_hash is not None:
            fill_node["hash_ok"] = (fill_prev_hash == last_hash)
        else:
            # No recorded prev_hash or no predecessor available → cannot verify (conservative)
            fill_node["hash_ok"] = False if fill_prev_hash is not None else True

        extended.append(fill_node)

    return extended


# ---------------------------------------------------------------------------
# Phase 2 Slice 24: Small helper to attach verified close / realized PnL nodes
# (mirrors the fills pattern from Slices 17 + 23)
# ---------------------------------------------------------------------------

def extend_chain_with_closes(
    base_chain: list[dict[str, Any]],
    closes: list[Any],
) -> list[dict[str, Any]]:
    """
    Phase 2 Slice 24/25: Given a base reconstructed chain (that now includes verified fills),
    append close/PnL nodes that carry matching decision_context_id, with real hash_ok
    computed against the preceding fill node (using the same logic as fills).
    For multi-leg netting (Slice 25), multiple closes sharing the same decision_context_id
    are linked in a chain (prev_hash of next points to hash of previous close).
    """
    if not base_chain or not closes:
        return base_chain

    extended = list(base_chain)

    # Find a reasonable predecessor hash (last node in the extended chain so far)
    last_node = extended[-1] if extended else None
    last_hash = last_node.get("event_hash") if last_node else None

    for close in closes:
        if close is None:
            continue

        # Support both dict-like and simple objects (best-effort, like fills)
        if isinstance(close, dict):
            cid = close.get("decision_context_id")
            ph = close.get("prev_hash")
            payload = close.get("payload", close)
        else:
            cid = getattr(close, "decision_context_id", None)
            ph = getattr(close, "prev_hash", None)
            payload = {
                "gross_pnl": getattr(close, "gross_pnl", None),
                "realized_net": getattr(close, "realized_net", None),
                "exit_commission": getattr(close, "exit_commission", None),
                "slippage_points_vs_reference": getattr(close, "slippage_points_vs_reference", None),
            }

        if not cid:
            continue

        # For multi-leg (Slice 25): if a prev_hash is provided for this close, use it;
        # otherwise chain to the last hash in the extended chain (netting continuation).
        effective_prev = ph or last_hash

        close_node = {
            "topic": "trade.position_closed",
            "producer": "trade_reconciler",
            "payload": payload if isinstance(payload, dict) else {},
            "metadata": {
                "decision_context_id": cid,
                "prev_hash": effective_prev,
            },
            "event_hash": _fingerprint({"payload": payload, "metadata": {"decision_context_id": cid, "prev_hash": effective_prev}}),
            "prev_hash": effective_prev,
            "hash_ok": (effective_prev == last_hash) if (effective_prev is not None and last_hash is not None) else True,
        }

        extended.append(close_node)
        last_hash = close_node["event_hash"]

    return extended


# ---------------------------------------------------------------------------
# Phase 2 Slice 14: Human-readable Pre-Trade Decision Provenance Report
# Thin, read-only layer on top of the existing reconstruction helper.
# ---------------------------------------------------------------------------

def build_pretrade_provenance_report(
    decision_context_id: str,
    *,
    event_bus: Any | None = None,
    recent_fills: list[Any] | None = None,
    recent_closes: list[Any] | None = None,
    engine: Any | None = None,
) -> dict[str, Any]:
    """
    Build a structured, human-oriented provenance report for a decision_context_id.

    Phase 2 Slice 17: Accepts optional recent_fills (e.g. from broker.get_fills()).
    Phase 2 Slice 22: If recent_fills is not explicitly provided and an engine
    (with a .broker that implements get_fills()) is supplied, best-effort auto-fetch
    recent fills and filter by the target decision_context_id using the first-class
    lineage fields (Slice 19). This makes the full end-to-end report (including
    downstream execution) automatic for the CLI and Guardian.
    """
    if not decision_context_id:
        return {"error": "decision_context_id is required"}

    # Phase 2 Slice 22: Best-effort auto-pull of fills when not explicitly provided.
    # This turns the provenance report into a complete daily forcing function
    # without requiring callers to manually pass recent_fills.
    effective_fills = recent_fills
    if effective_fills is None:
        try:
            broker = None
            if engine is not None:
                broker = getattr(engine, "broker", None) or getattr(engine, "get_broker", lambda: None)()
            if broker is not None and hasattr(broker, "get_fills"):
                all_fills = broker.get_fills() or []
                # Filter using first-class fields (Slice 19) with raw fallback
                effective_fills = [
                    f for f in all_fills
                    if getattr(f, "decision_context_id", None) == decision_context_id
                    or (isinstance(getattr(f, "raw", None), dict) and f.raw.get("decision_context_id") == decision_context_id)
                ]
        except Exception:
            effective_fills = []  # best-effort only; never break the report

    base_chain = reconstruct_risk_decision_chain(decision_context_id, event_bus=event_bus, limit=100)
    extended_chain = extend_chain_with_fills(base_chain, effective_fills or [])
    if recent_closes:
        extended_chain = extend_chain_with_closes(extended_chain, recent_closes)

    if not extended_chain:
        return {
            "decision_context_id": decision_context_id,
            "summary": {"status": "NO_DATA", "message": "No events found for this decision_context_id"},
            "upstream": [],
            "core_risk_chain": [],
            "fills": [],
            "anomalies": ["No lineage events found"],
        }

    upstream_topics = {
        "trading_engine.dream_state.updated",
        "agent.rl.proposal",
        "agent.news.proposal",
        "agent.emotional_twin.proposal",
        "agent.swarm.proposal",
        "agent.tape.proposal",
    }
    core_topics = {"admission.gate_entry", "risk.policy.decision", "risk.final_arbitration.result"}

    upstream = [e for e in extended_chain if e.get("topic") in upstream_topics]
    core_chain = [e for e in extended_chain if e.get("topic") in core_topics]
    fills_section = [
        e for e in extended_chain if e.get("topic") in (EXECUTION_FILL_RECEIVED_TOPIC, "execution.fill")
    ]

    anomalies = []
    if not any(e.get("topic") == "admission.gate_entry" for e in core_chain):
        anomalies.append("Missing admission.gate_entry")
    if not any(e.get("topic") == "risk.final_arbitration.result" for e in core_chain):
        anomalies.append("Missing final arbitration result")

    broken_links = [e for e in extended_chain if not e.get("hash_ok", True)]
    if broken_links:
        anomalies.append(f"{len(broken_links)} broken hash link(s) detected")

    final_arb = next((e for e in reversed(core_chain) if e.get("topic") == "risk.final_arbitration.result"), None)
    final_status = None
    if final_arb:
        final_status = _outcome_label_for_chain_node(
            str(final_arb.get("topic", "risk.final_arbitration.result")),
            final_arb.get("payload", {}) or {},
        )

    summary = {
        "status": "OK" if not anomalies else "ANOMALIES",
        "total_nodes": len(extended_chain),
        "upstream_nodes": len(upstream),
        "core_nodes": len(core_chain),
        "fill_nodes": len(fills_section),
        "final_arbitration_status": final_status,
        "chain_integrity_ok": len(broken_links) == 0,
    }

    return {
        "decision_context_id": decision_context_id,
        "summary": summary,
        "upstream": upstream,
        "core_risk_chain": core_chain,
        "fills": fills_section,
        "anomalies": anomalies,
        "full_raw_chain": extended_chain,
    }


def format_provenance_report_as_markdown(report: dict[str, Any]) -> str:
    """Convert the structured provenance report into clean, human-readable Markdown."""
    if "error" in report:
        return f"# Provenance Report Error\n\n{report['error']}"

    lines = []
    ctx = report.get("decision_context_id", "unknown")
    summary = report.get("summary", {})

    lines.append("# Pre-Trade Decision Provenance Report")
    lines.append(f"**Decision Context ID**: `{ctx}`")
    lines.append(f"**Status**: {summary.get('status', 'UNKNOWN')}")
    lines.append("")

    # Summary box
    lines.append("## Summary")
    lines.append(f"- Total lineage nodes: {summary.get('total_nodes', 0)}")
    lines.append(f"- Upstream (dream/proposals): {summary.get('upstream_nodes', 0)}")
    lines.append(f"- Core risk chain: {summary.get('core_nodes', 0)}")
    lines.append(f"- Final arbitration outcome: {summary.get('final_arbitration_status', 'N/A')}")
    lines.append(f"- Cryptographic chain integrity: {'OK' if summary.get('chain_integrity_ok') else 'BROKEN'}")
    lines.append("")

    # Anomalies
    anomalies = report.get("anomalies", [])
    if anomalies:
        lines.append("## ANOMALIES DETECTED")
        for a in anomalies:
            lines.append(f"- {a}")
        lines.append("")

    # Upstream
    upstream = report.get("upstream", [])
    if upstream:
        lines.append("## Upstream Intention Formation")
        for event in upstream:
            topic = event.get("topic", "unknown")
            producer = event.get("producer", "unknown")
            payload = event.get("payload", {})
            sig = payload.get("signal") or payload.get("reason", "")[:60]
            lines.append(f"- **{topic}** by `{producer}`: {sig}")
        lines.append("")

    # Core risk chain
    core = report.get("core_risk_chain", [])
    if core:
        lines.append("## Core Risk Decision Chain (Hash Verified)")
        lines.append("| Step | Topic | Outcome | hash_ok |")
        lines.append("|------|-------|---------|---------|")
        for event in core:
            topic = event.get("topic", "")
            payload = event.get("payload", {}) or {}
            outcome = _outcome_label_for_chain_node(str(topic), payload)
            h_ok = "OK" if event.get("hash_ok") else "BROKEN"
            lines.append(f"|  | `{topic}` | {outcome} | {h_ok} |")
        lines.append("")

    # Phase 2 Slice 17 + 23: Fills & Execution section (now with hash linkage status)
    fills = report.get("fills", [])
    if fills:
        lines.append("## Fills & Execution (Downstream Lineage)")
        lines.append("| Fill ID | Symbol | Side | Qty | Price | hash_ok |")
        lines.append("|---------|--------|------|-----|-------|---------|")
        for f in fills:
            p = f.get("payload", {}) or {}
            h_ok = "OK" if f.get("hash_ok") else "BROKEN"
            lines.append(
                f"| {p.get('fill_id', '')[:12]} | {p.get('symbol', '')} | "
                f"{p.get('side', '')} | {p.get('quantity', '')} | "
                f"{p.get('price', '')} | {h_ok} |"
            )
        lines.append("")

    # Phase 2 Slice 24: Closes & Realized PnL section (light, mirrors fills)
    closes = report.get("closes", []) or report.get("recent_closes", [])
    if closes:
        lines.append("## Closes & Realized PnL (Downstream Lineage)")
        lines.append("| Topic | Realized Net | hash_ok |")
        lines.append("|-------|--------------|---------|")
        for c in closes:
            p = c.get("payload", {}) or {}
            h_ok = "OK" if c.get("hash_ok") else "BROKEN"
            net = p.get("realized_net", p.get("pnl", "—"))
            lines.append(f"| `{c.get('topic', 'trade.position_closed')}` | {net} | {h_ok} |")
        lines.append("")

    # Raw note
    lines.append("---")
    lines.append("*This report was generated by `lumina_core.risk.decision_lineage` (Slice 14 + 17 + 24). Full raw data available in the returned dict.*")

    return "\n".join(lines)


# Simple CLI for human use: python -m lumina_core.risk.decision_lineage <decision_context_id>
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m lumina_core.risk.decision_lineage <decision_context_id>")
        sys.exit(1)

    ctx = sys.argv[1]

    # Phase 2 Slice 22: Best-effort attempt to provide a broker/engine context
    # so the report automatically includes recent fills (when available).
    engine = None
    try:
        from lumina_core.engine.lumina_engine import LuminaEngine  # type: ignore
        # Only attempt if a default engine can be constructed cheaply
        engine = LuminaEngine()  # may be partial; auto-pull inside report is best-effort
    except Exception:
        engine = None

    report = build_pretrade_provenance_report(ctx, engine=engine)
    print(format_provenance_report_as_markdown(report))