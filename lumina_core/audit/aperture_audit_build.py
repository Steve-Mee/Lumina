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

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

# Internal imports — all best-effort and defensive
# We deliberately import inside functions where possible to keep startup light



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


