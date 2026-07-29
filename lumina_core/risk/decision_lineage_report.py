"""Decision lineage provenance report builders.

Read-only; no side effects on trading logic.
"""

from __future__ import annotations

from typing import Any

from lumina_core.agent_orchestration.schemas import EXECUTION_FILL_RECEIVED_TOPIC
from lumina_core.risk.decision_lineage_extend import (
    extend_chain_with_closes,
    extend_chain_with_fills,
)
from lumina_core.risk.decision_lineage_reconstruct import (
    _outcome_label_for_chain_node,
    reconstruct_risk_decision_chain,
)


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
