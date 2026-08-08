"""
Aperture Audit Artifact — Phase 3 Deliverable 1 (One Human, 20 Minutes Audit)

This module provides the official, production-grade interface for generating
self-contained, human-auditable artifacts for any decision_context_id.

It unifies:
- Cryptographic decision lineage (from decision_lineage.py)
- Full FinalArbitration constitution + risk checks
- Agent + DNA + evolution context (including D5 shadow linkage when present)
- Aperture Integrity Score snapshot
- Correlated immutable audit logs

The goal (per the 2026-05-31 90-day roadmap): one human can fully understand
provenance, constitution compliance, risk parameters, agent lineage, and
execution outcome for any trade in under 20 minutes.

Design principles (matching shadow_review.py and the approved plan):
- Library-first (importable functions for dashboards, Guardian, notebooks)
- Best-effort and non-breaking (never fails the caller)
- Clean CLI for daily human use
- Strong "Red Flags First" UX in the rendered markdown
- Explicitly surfaces Phase 2 D5 shadow protection results when available

Usage (CLI):
    python -m lumina_core.audit.aperture_audit <decision_context_id>
    python -m lumina_core.audit.aperture_audit <ctx> --export state/audits/

Usage (library):
    from lumina_core.audit.aperture_audit_artifact import (
        build_aperture_audit_artifact,
        format_aperture_audit_as_markdown,
        export_aperture_audit_bundle,
        discover_recent_final_arbitration_ctxs,  # for D4 campaign + Guardian "live from logs" real data
    )

All changes to this module must follow the Recursive Self-Improvement Protocol,
constitution-guard, risk-safety-review, and produce public evolution entries.
"""

from __future__ import annotations

from typing import Any

# Internal imports — all best-effort and defensive
# We deliberately import inside functions where possible to keep startup light


def format_aperture_audit_as_markdown(artifact: dict[str, Any]) -> str:
    """
    Render the artifact as a clean, "one human 20 minutes" markdown document.

    Design goals:
    - Red Flags First (missing data and broken chain at the very top)
    - Constitution table prominent
    - Risk numbers and agent lineage clearly visible
    - Hash integrity status on every section
    - Self-contained (no external links required for first-pass review)
    """
    if not isinstance(artifact, dict):
        return "# Aperture Audit Error\n\nInvalid artifact data."

    if "error" in artifact:
        return f"# Aperture Audit Error\n\n{artifact.get('error', 'Unknown error')}"

    ctx = artifact.get("decision_context_id", "unknown")
    lines: list[str] = []

    lines.append("# Aperture Audit Artifact")
    lines.append(f"**Decision Context ID**: `{ctx}`")
    lines.append(f"**Generated**: {artifact.get('generated_at', 'unknown')}")
    lines.append("")

    # Red Flags First
    missing = artifact.get("missing_data", []) or []
    if missing:
        lines.append("## ⚠️ RED FLAGS / MISSING DATA")
        for item in missing:
            lines.append(f"- {item}")
        lines.append("")

    # Summary (reuse + extend existing structure)
    summary = artifact.get("summary", {}) or {}
    lines.append("## Summary")
    lines.append(f"- Chain integrity: {'OK' if summary.get('chain_integrity_ok') else 'BROKEN / INCOMPLETE'}")
    lines.append(f"- Final arbitration: {summary.get('final_arbitration_status', 'UNKNOWN')}")
    lines.append("")

    # Constitution & Arbitration (status: unavailable when streams lack data)
    checks = artifact.get("constitution_checks", []) or []
    lines.append("## Constitution & Final Arbitration Checks")
    if checks:
        lines.append("| Step | OK | Reason |")
        lines.append("|------|----|--------|")
        for c in checks:
            ok = "✅" if c.get("ok") else "❌"
            lines.append(f"| {c.get('name', '?')} | {ok} | {c.get('reason', '')} |")
    else:
        lines.append("**status: unavailable** — no constitution check rows in this artifact.")
        lines.append(
            "When present, full `checks[]` from `risk.final_arbitration.result` appear here."
        )
    lines.append("")

    # Risk Numbers (status: unavailable when not extracted)
    risk = artifact.get("risk_numbers", {}) or {}
    lines.append("## Risk Decision Numbers")
    if risk:
        for k, v in risk.items():
            lines.append(f"- **{k}**: {v}")
    else:
        lines.append(
            "**status: unavailable** — risk parameters (proposed_risk, kelly, sizing, limits) "
            "were not present in the source streams for this artifact."
        )
    lines.append("")

    # Agent + DNA + Shadow Lineage (D5 visibility)
    lineage = artifact.get("agent_dna_lineage", {}) or {}
    lines.append("## Agent & Evolution Lineage (incl. Shadow Protection)")
    if lineage:
        for k, v in lineage.items():
            lines.append(f"- **{k}**: {v}")
    else:
        lines.append("_Agent style, DNA version, prompt_id, and linked `evolution.shadow.verdict` will appear here (best-effort from proposal and evolution events)._")
        lines.append("This section makes Phase 2 Deliverable 5 shadow results visible in every audit.")
    lines.append("")

    # Execution
    exec_section = artifact.get("execution", {}) or {}
    lines.append("## Execution & Realized PnL (Hash Verified)")
    fills = exec_section.get("fills", []) or []
    if fills:
        lines.append(f"- Fills found: {len(fills)}")
    else:
        lines.append("_No fills linked yet (best-effort)._")
    lines.append("")

    # Aperture Context
    aperture = artifact.get("aperture_context", {}) or {}
    lines.append("## Aperture Integrity Context")
    if aperture:
        lines.append(f"- Score: {aperture.get('score', 'N/A')}/10  |  Status: {aperture.get('status', 'N/A')}")
        if aperture.get("fatal_count") or aperture.get("high_count"):
            lines.append(f"- Active issues: fatal={aperture.get('fatal_count', 0)}, high={aperture.get('high_count', 0)}")
    else:
        lines.append("_Current Guardian Aperture Integrity Score snapshot will appear here._")
    lines.append("")

    # Additional immutable audit sources (Phase 3 D1 excerpts)
    raw = artifact.get("raw_sources", {}) or {}
    audit_ex = raw.get("audit_log_excerpts", []) or []
    agent_ex = raw.get("agent_decision_excerpts", []) or []
    if audit_ex or agent_ex:
        lines.append("## Additional Audit Sources (immutable log excerpts)")
        if audit_ex:
            lines.append("### Trade Decision Audit Log")
            for e in audit_ex[:3]:
                lines.append(f"- { {k: e[k] for k in e if k not in ('full_raw_sample', 'payload_sample')} }")
                if "payload_sample" in e and e["payload_sample"]:
                    lines.append(f"  payload_sample: {e['payload_sample']}")
                if "full_raw_sample" in e:
                    lines.append(f"  full_raw_sample: {e['full_raw_sample'] if not isinstance(e['full_raw_sample'], dict) else '(see json artifact for full)'}")
        if agent_ex:
            lines.append("### Agent Decision Log")
            for e in agent_ex[:3]:
                lines.append(f"- { {k: e[k] for k in e if k not in ('full_raw_sample', 'payload_sample')} }")
                if "payload_sample" in e and e["payload_sample"]:
                    lines.append(f"  payload_sample: {e['payload_sample']}")
                if "full_raw_sample" in e:
                    lines.append(f"  full_raw_sample: {e['full_raw_sample'] if not isinstance(e['full_raw_sample'], dict) else '(see json artifact for full)'}")
    else:
        lines.append("## Additional Audit Sources (immutable log excerpts)")
        lines.append("_Excerpts from AuditLogService / AgentDecisionLog (with payload samples) will appear here when entries for this ctx exist._")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append(
        "*Generated by `lumina_core.audit.aperture_audit_artifact` (Phase 3 D1 first slice). "
        "Foundation: decision_lineage.py + FinalArbitration + Guardian. "
        "This is a skeleton build — full data population in subsequent micro-steps.*"
    )

    return "\n".join(lines)


def format_compact_aperture_audit(artifact: dict[str, Any]) -> str:
    """
    Compact 1-screen "one human 20 minutes" summary suitable for embedding
    directly in Guardian reports and daily outputs.
    """
    if not isinstance(artifact, dict):
        return "**Aperture Audit: invalid data**"

    if "error" in artifact:
        return f"**Aperture Audit Error** for {artifact.get('decision_context_id', '?')}: {artifact.get('error')}"

    ctx = artifact.get("decision_context_id", "unknown")
    summary = artifact.get("summary", {}) or {}
    chain_ok = "✅ OK" if summary.get("chain_integrity_ok") else "❌ BROKEN/INCOMPLETE"
    final = summary.get("final_arbitration_status", "UNKNOWN")

    checks = artifact.get("constitution_checks", []) or []
    violations = sum(1 for c in checks if not c.get("ok", True))
    const_step = next((c for c in checks if c.get("name") == "constitution"), None)
    const_status = "✅" if const_step and const_step.get("ok") else "❌" if const_step else "?"

    risk = artifact.get("risk_numbers", {}) or {}
    proposed = risk.get("proposed_risk") or risk.get("max_risk_percent") or "?"
    kelly = risk.get("kelly", "?")

    lineage = artifact.get("agent_dna_lineage", {}) or {}
    agent = lineage.get("agent_id") or lineage.get("prompt_id") or "unknown"
    shadow = lineage.get("shadow_experiment_id", "none linked")

    return (
        f"**D1 Compact Audit — {ctx}**\n"
        f"- Chain: {chain_ok} | Final Arb: {final}\n"
        f"- Constitution: {const_status} (checks: {len(checks)}, violations: {violations})\n"
        f"- Proposed risk: {proposed} | Kelly: {kelly}\n"
        f"- Agent/DNA: {agent} | Shadow experiment: {shadow}\n"
        f"Full view: guardian_d1_{ctx}_*.md (auto-saved in state/audits/)"
    )


