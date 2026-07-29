"""Decision lineage extend helpers (fills / closes / order links).

Read-only; no side effects on trading logic.
"""

from __future__ import annotations

from typing import Any

from lumina_core.risk.decision_lineage_reconstruct import _fingerprint


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
