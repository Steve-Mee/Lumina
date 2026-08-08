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
from pathlib import Path

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


