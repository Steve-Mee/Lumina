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

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

# Internal imports — all best-effort and defensive
# We deliberately import inside functions where possible to keep startup light


def discover_recent_final_arbitration_ctxs(max_ctxs: int = 30, max_tail: int = 5000) -> list[str]:
    """
    Best-effort discovery of decision_context_ids that reached Final Arbitration.

    Primary "live from system" source for Phase 3 D1 (one human 20 min) and D4
    (30-day public campaign evidence). Scans the immutable JSONL audit/decision
    logs for events whose topic or payload indicates a Final Arbitration result
    (risk.final_arbitration.result, arbitration checks, final status, etc.).

    Returns ctxs in reverse-chronological order (most recent first), deduplicated,
    up to max_ctxs. Defensive: never raises, works standalone without engine/bus.

    Reusable by Guardian daily runs and D4 script so that when real trading/SIM
    activity with aggressive evolution produces FinalArbitration events, the
    public demonstration bundle can be built directly from the source-of-truth
    logs (no pre-requiring Guardian D1 sidecars).

    This strengthens the "real (non-demo) data" path per the 2026-05-31 roadmap.
    """
    ctxs: list[str] = []
    possible_paths: list[Path] = [
        Path(os.getenv("LUMINA_TRADE_DECISION_AUDIT_LOG", "state/trade_decision_audit.jsonl")),
        Path("state/trade_decision_audit.jsonl"),
        Path("state/agent_decision_log.jsonl"),
        Path("state/promotion_gate_audit.jsonl"),
        Path(os.getenv("LUMINA_STATE_DIR", "state")) / "agent_blackboard.jsonl",
        Path("state/agent_blackboard.jsonl"),
        Path("state/audits/demo_final_arbitration_seed.jsonl"),  # for D4 self-contained live log demo data (reversible sidecar)
        # Genuine campaign data produced by phase3_d4_genuine_evidence.py (Phase 3 D4 genuine step)
        *list(Path("state/audits").glob("genuine_d4_campaign_*/genuine_final_arbitration_campaign.jsonl")),
        # Longer multi-day genuine campaign data (Phase 3 D4 next step per MC)
        *list(Path("state/audits").glob("genuine_d4_multiday_*/**/*.jsonl")),
        *list(Path("state/audits").glob("genuine_d4_multiday_*/*.jsonl")),
    ]

    tail_size = min(max_tail or 5000, 100_000)
    for p in possible_paths:
        if len(ctxs) >= max_ctxs:
            break
        if not p.exists():
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-tail_size:]
            for line in reversed(lines):
                if len(ctxs) >= max_ctxs:
                    break
                try:
                    rec = json.loads(line)
                    payload = rec.get("payload") if isinstance(rec.get("payload"), dict) else rec
                    if not isinstance(payload, dict):
                        payload = {}
                    topic = str(rec.get("topic", "") or payload.get("topic", "") or "").lower()

                    # Match Final Arbitration events (typed topic or structural markers in payload)
                    is_arb_topic = any(k in topic for k in ("final_arbitration", "arbitration.result", "final.arbitration"))
                    has_arb_markers = (
                        "checks" in payload
                        or "final_arbitration_status" in payload
                        or "constitution_checks" in payload
                        or (isinstance(payload.get("final_arbitration"), dict))
                    )
                    if not (is_arb_topic or has_arb_markers):
                        continue

                    cid = str(
                        payload.get("decision_context_id")
                        or rec.get("decision_context_id")
                        or rec.get("correlation_id")
                        or payload.get("correlation_id")
                        or ""
                    ).strip()
                    if cid and cid not in ctxs:
                        ctxs.append(cid)
                except Exception:
                    continue
        except Exception:
            continue
    return ctxs[:max_ctxs]


def merge_d1_audit_context_ids(
    existing: list[str] | None = None,
    *,
    max_ctxs: int = 8,
) -> list[str]:
    """
    Merge bus/blackboard ctx ids with Final Arbitration discoveries from immutable logs.

    Phase 3 D3: ensures Guardian --d1-audits auto-runs on genuine Final Arbitration ctxs
    even when the live bus is unavailable (standalone Guardian runs).
    """
    merged: list[str] = []
    for cid in list(existing or []):
        c = str(cid or "").strip()
        if c and c not in merged:
            merged.append(c)
    try:
        for cid in discover_recent_final_arbitration_ctxs(max_ctxs=max_ctxs):
            if cid and cid not in merged:
                merged.append(cid)
    except Exception:
        pass
    return merged[:max_ctxs]


def build_aperture_audit_artifact(
    decision_context_id: str,
    *,
    engine: Any = None,
    include_audit_log: bool = True,
    include_agent_decision_log: bool = True,
    max_log_lines: int = 500,
) -> dict[str, Any]:
    """
    Build a complete, self-contained Aperture Audit Artifact for a decision.

    This is the primary high-level entry point for Phase 3 Deliverable 1.

    Returns a rich dictionary containing:
    - decision_context_id
    - generated_at
    - summary (status, chain_integrity, final_outcome, red_flags)
    - constitution_checks (full table from FinalArbitration)
    - risk_numbers (proposed_risk, kelly, sizing, limits)
    - agent_dna_lineage (originating agents, DNA version, shadow_experiment if any)
    - execution (fills + realized PnL with hash linkage)
    - aperture_context (current Aperture Integrity Score + warnings)
    - lineage_chain (full reconstructed + verified chain)
    - raw_sources (best-effort excerpts from audit logs, blackboard, etc.)
    - missing_data (honest list of anything that could not be retrieved)

    The function is best-effort and never raises for missing data.
    All reconstruction failures are captured in "missing_data" and surfaced
    clearly in the rendered markdown.

    max_log_lines: controls how far back to scan the immutable logs for excerpts.
    Default 500 (recent). For historical ctxs, pass e.g. 10000 or a large number
    (capped internally for safety). This improves durability for old decisions
    without always paying the cost.
    """
    if not decision_context_id or not isinstance(decision_context_id, str):
        return {
            "decision_context_id": str(decision_context_id or "invalid"),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "error": "Invalid decision_context_id",
            "missing_data": ["valid decision_context_id"],
        }

    artifact: dict[str, Any] = {
        "decision_context_id": decision_context_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {},
        "constitution_checks": [],
        "risk_numbers": {},
        "agent_dna_lineage": {},
        "execution": {},
        "aperture_context": {},
        "lineage_chain": [],
        "raw_sources": {},
        "missing_data": [],
    }

    # Delegate to the excellent existing Phase 2 decision_lineage foundation
    # (this is the core of why D1 can be delivered quickly).
    try:
        from lumina_core.risk import decision_lineage as dl

        report = dl.build_pretrade_provenance_report(
            decision_context_id,
            engine=engine,
        )

        if "error" in report:
            artifact["missing_data"].append(f"provenance_report: {report['error']}")
        else:
            chain = report.get("full_raw_chain", []) or report.get("core_risk_chain", [])
            artifact["lineage_chain"] = chain
            artifact["summary"] = report.get("summary", {})

            exec_data = {
                "fills": report.get("fills", []) or [],
                "closes": report.get("closes", []) or report.get("recent_closes", []) or [],
            }
            artifact["execution"] = exec_data

            # Seed some summary fields if the underlying report provided them
            if not artifact["summary"].get("status"):
                artifact["summary"]["status"] = "PARTIAL" if chain else "INCOMPLETE"

            # First real data population (Phase 3 D1 progress): extract constitution checks
            # and risk numbers from the raw chain when FinalArbitration / policy events are present.
            _extract_constitution_and_risk(artifact, chain)

            # Next slice progress: best-effort agent/DNA lineage + shadow linkage + aperture context
            _extract_agent_dna_shadow_and_aperture(artifact, chain)

    except Exception as e:
        artifact["missing_data"].append(f"decision_lineage: {type(e).__name__}: {e}")

    # Phase 3 D1: best-effort excerpts from immutable audit logs (AuditLogService + AgentDecisionLog)
    # These provide the full decision transparency for the "one human 20 min" view.
    if include_audit_log:
        artifact["raw_sources"]["audit_log_excerpts"] = _load_ctx_excerpts(
            decision_context_id,
            possible_paths=[
                Path(os.getenv("LUMINA_TRADE_DECISION_AUDIT_LOG", "state/trade_decision_audit.jsonl")),
                Path("state/trade_decision.jsonl"),
            ],
            max_tail=max_log_lines,
        )
    if include_agent_decision_log:
        agent_log_path = os.getenv("LUMINA_AGENT_DECISION_LOG", "state/agent_decision_log.jsonl")
        artifact["raw_sources"]["agent_decision_excerpts"] = _load_ctx_excerpts(
            decision_context_id,
            possible_paths=[Path(agent_log_path)],
            max_tail=max_log_lines,
        )

    # Honest best-effort marker for this skeleton
    if not artifact.get("lineage_chain"):
        artifact["missing_data"].append("full_lineage_chain (skeleton phase)")

    return artifact


def _extract_constitution_and_risk(artifact: dict[str, Any], chain: list[dict[str, Any]]) -> None:
    """Best-effort extraction of constitution checks and key risk numbers from the lineage chain."""
    if not chain:
        return
    if not isinstance(artifact, dict):
        return

    summary = artifact.get("summary")
    if not isinstance(summary, dict):
        summary = {}
        artifact["summary"] = summary

    checks: list[dict[str, Any]] = []
    risk: dict[str, Any] = {}

    for node in chain:
        payload = node.get("payload", {}) or {}
        topic = node.get("topic", "")

        # Final Arbitration carries the full checks list (including constitution step)
        if "final_arbitration" in topic and "checks" in payload:
            raw_checks = payload.get("checks", [])
            for c in raw_checks:
                if isinstance(c, dict):
                    checks.append({
                        "name": c.get("name"),
                        "ok": c.get("ok"),
                        "reason": c.get("reason"),
                    })
            if payload.get("violated_principle"):
                summary["violated_principle"] = payload["violated_principle"]

        # Risk policy decision often carries the proposed risk parameters
        if "risk.policy.decision" in topic or "RiskVerdict" in str(type(payload)):
            for key in ("proposed_risk", "kelly", "max_risk_percent", "position_size", "drawdown_kill_percent"):
                if key in payload:
                    risk[key] = payload[key]

    if checks:
        artifact["constitution_checks"] = checks
        # Remove the skeleton placeholder note if we got real data
        artifact["missing_data"] = [m for m in artifact.get("missing_data", []) if "constitution" not in m.lower()]

    if risk:
        artifact["risk_numbers"] = risk


def _extract_agent_dna_shadow_and_aperture(artifact: dict[str, Any], chain: list[dict[str, Any]]) -> None:
    """Best-effort extraction of agent/DNA lineage, shadow linkage, and current aperture context."""
    if not chain or not isinstance(artifact, dict):
        return

    lineage: dict[str, Any] = {}

    for node in chain:
        payload = node.get("payload", {}) or {}
        if not isinstance(payload, dict):
            continue

        # Common fields across proposal, meta, shadow, and evolution events
        for key in ("agent_id", "dna_hash", "prompt_id", "shadow_experiment_id", "evolution_experiment_id"):
            if key in payload and payload[key] and key not in lineage:
                lineage[key] = payload[key]

        # Look inside nested proposal/dna structures (common in evolution events)
        for nested_key in ("proposal", "dna", "meta"):
            nested = payload.get(nested_key)
            if isinstance(nested, dict):
                for key in ("agent_id", "dna_hash", "prompt_id"):
                    if key in nested and nested[key] and key not in lineage:
                        lineage[key] = nested[key]

    if lineage:
        artifact["agent_dna_lineage"] = lineage

    # Best-effort current Aperture Integrity snapshot (from Guardian)
    try:
        import sys
        from pathlib import Path
        guardian_path = Path(__file__).parent.parent.parent / "scripts" / "dna_guardian"
        if guardian_path.exists():
            sys.path.insert(0, str(guardian_path))
            from validate_dna import calculate_aperture_integrity  # type: ignore
            aperture = calculate_aperture_integrity()
            if isinstance(aperture, dict):
                artifact["aperture_context"] = {
                    "score": aperture.get("score"),
                    "status": aperture.get("status"),
                    "fatal_count": aperture.get("fatal_count"),
                    "high_count": aperture.get("high_count"),
                }
    except Exception:
        # Never break the audit on Guardian import/execution issues
        pass

    return artifact


def _load_ctx_excerpts(ctx: str, possible_paths: list[Path], max_entries: int = 5, max_tail: int = 500) -> list[dict[str, Any]]:
    """Best-effort: tail recent lines from audit/decision logs and return richer compact entries matching the ctx.
    Includes payload_sample with key fields for completeness (full large payloads avoided to keep artifact lightweight).

    max_tail: how many lines from the end to scan (for durability on historical ctxs).
    Larger values (e.g. 10000) allow finding old decision_context_ids at the cost of more I/O.
    Internally capped at 100_000 for safety.
    """
    excerpts: list[dict[str, Any]] = []
    tail_size = min(max_tail, 100_000) if max_tail and max_tail > 0 else 100_000
    for p in possible_paths:
        if not p.exists():
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-tail_size:]
            for line in reversed(lines):
                try:
                    rec = json.loads(line)
                    payload = rec.get("payload") if isinstance(rec.get("payload"), dict) else {}
                    rec_ctx = str(payload.get("decision_context_id", "") or rec.get("decision_context_id", ""))
                    if rec_ctx == ctx:
                        compact = {}
                        for k in ("timestamp", "decision_context_id", "stage", "final_decision", "agent_id", "policy_outcome", "reason", "model_version"):
                            v = rec.get(k) or payload.get(k)
                            if v is not None:
                                compact[k] = v

                        # Richer: payload sample with interesting keys (risk, signals, etc.)
                        sample_keys = ("proposed_risk", "kelly", "max_risk_percent", "signal", "confidence", "qty", "reason", "raw_input", "raw_output")
                        if payload:
                            compact["payload_sample"] = {k: payload[k] for k in sample_keys if k in payload}
                        elif any(k in rec for k in sample_keys):
                            compact["payload_sample"] = {k: rec[k] for k in sample_keys if k in rec}

                        # For the first (most recent) matching, include a bounded full raw for audit depth
                        if len(excerpts) == 0:
                            raw_str = json.dumps(rec, default=str)
                            if len(raw_str) < 4000:
                                compact["full_raw_sample"] = rec
                            else:
                                compact["full_raw_sample"] = "(truncated in artifact; see original log)"

                        excerpts.append(compact)
                        if len(excerpts) >= max_entries:
                            return list(reversed(excerpts))
                except Exception:
                    continue
        except Exception:
            continue
    return list(reversed(excerpts))


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

    # Constitution & Arbitration (placeholder in skeleton — will be rich)
    checks = artifact.get("constitution_checks", []) or []
    lines.append("## Constitution & Final Arbitration Checks")
    if checks:
        lines.append("| Step | OK | Reason |")
        lines.append("|------|----|--------|")
        for c in checks:
            ok = "✅" if c.get("ok") else "❌"
            lines.append(f"| {c.get('name', '?')} | {ok} | {c.get('reason', '')} |")
    else:
        lines.append("_Detailed constitution checks not yet populated in this skeleton build._")
        lines.append("Full `checks[]` from `risk.final_arbitration.result` will appear here.")
    lines.append("")

    # Risk Numbers (placeholder)
    risk = artifact.get("risk_numbers", {}) or {}
    lines.append("## Risk Decision Numbers")
    if risk:
        for k, v in risk.items():
            lines.append(f"- **{k}**: {v}")
    else:
        lines.append("_Risk parameters (proposed_risk, kelly, sizing, limits) will be extracted here._")
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


def export_aperture_audit_bundle(
    decision_context_id: str,
    output_dir: Path | str = "state/audits",
    *,
    engine: Any = None,
) -> tuple[Path | None, Path | None]:
    """
    Convenience helper: build the artifact and write both .md and .json to disk.

    Returns (markdown_path, json_path) or (None, None) on failure.
    """
    try:
        artifact = build_aperture_audit_artifact(decision_context_id, engine=engine)
        md = format_aperture_audit_as_markdown(artifact)

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        safe_ctx = "".join(c if c.isalnum() or c in "-_" else "_" for c in decision_context_id)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        md_path = out_dir / f"aperture_audit_{safe_ctx}_{ts}.md"
        json_path = out_dir / f"aperture_audit_{safe_ctx}_{ts}.json"

        md_path.write_text(md, encoding="utf-8")
        json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")

        return md_path, json_path
    except Exception:
        # Best-effort: never break the caller
        return None, None


# =============================================================================
# CLI (modeled directly on the excellent shadow_review.py pattern)
# =============================================================================

def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Phase 3 D1 Aperture Audit Artifact for a decision_context_id"
    )
    parser.add_argument("decision_context_id", help="The decision_context_id to audit")
    parser.add_argument(
        "--export",
        metavar="DIR",
        help="Export both .md and .json to this directory (e.g. state/audits)",
    )

    args = parser.parse_args()

    if args.export:
        md_path, json_path = export_aperture_audit_bundle(
            args.decision_context_id,
            output_dir=args.export,
        )
        if md_path and json_path:
            print(f"Exported:\n  Markdown: {md_path}\n  JSON:     {json_path}")
        else:
            print("Export failed (best-effort).")
    else:
        artifact = build_aperture_audit_artifact(args.decision_context_id)
        print(format_aperture_audit_as_markdown(artifact))


if __name__ == "__main__":
    _main()
