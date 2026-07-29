"""
Decision Lineage — Small reconstruction helpers for the critical risk decision path.

Phase 2 focus: Reconstruct and validate the hash-chained lineage between
`risk.policy.decision` and `risk.final_arbitration.result` for a given
decision_context_id, including upstream proposal and (Slice 12) dream/coordination roots.

This module is intentionally tiny and has no side effects on trading logic.
It is designed to be used by the Guardian, post-trade audits, and tests.

Public façade: re-exports reconstruct / extend / report helpers.
"""

from __future__ import annotations

from lumina_core.risk.decision_lineage_extend import (
    extend_chain_with_closes,
    extend_chain_with_fills,
    get_downstream_link_from_order,
    get_lineage_from_fill,
    get_lineage_from_order_result,
)
from lumina_core.risk.decision_lineage_reconstruct import (
    _fingerprint,
    _payload_dict_from_event,
    decision_context_id_from_blackboard_event,
    decision_context_id_from_event,
    event_hash_from_event,
    event_metadata_from_event,
    event_payload_from_event,
    get_core_risk_decision_chain,
    is_chain_healthy,
    reconstruct_risk_decision_chain,
)
from lumina_core.risk.decision_lineage_report import (
    build_pretrade_provenance_report,
    format_provenance_report_as_markdown,
)

__all__ = [
    "event_metadata_from_event",
    "event_payload_from_event",
    "decision_context_id_from_event",
    "decision_context_id_from_blackboard_event",
    "event_hash_from_event",
    "_payload_dict_from_event",
    "_fingerprint",
    "reconstruct_risk_decision_chain",
    "is_chain_healthy",
    "get_core_risk_decision_chain",
    "get_downstream_link_from_order",
    "get_lineage_from_fill",
    "get_lineage_from_order_result",
    "extend_chain_with_fills",
    "extend_chain_with_closes",
    "build_pretrade_provenance_report",
    "format_provenance_report_as_markdown",
]


# Simple CLI for human use: python -m lumina_core.risk.decision_lineage <decision_context_id>
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m lumina_core.risk.decision_lineage <decision_context_id>")
        sys.exit(1)

    ctx = sys.argv[1]

    # Phase 2 Slice 22: Best-effort attempt to provide a broker/engine context
    # so the report automatically includes recent fills (when available).
    report = build_pretrade_provenance_report(ctx)
    print(format_provenance_report_as_markdown(report))
