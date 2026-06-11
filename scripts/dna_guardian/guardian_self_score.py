"""
Phase 3 D6 — Guardian self-score vs aperture contracts.

Heuristic scoring of the in-memory Guardian report dict (no LLM).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DNA_ROOT = PROJECT_ROOT / "project-dna" / "lumina"
CONTRACT_PATH = DNA_ROOT / "operating-system" / "rules" / "guardian-self-score-contract.yaml"


def _load_contract() -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        if CONTRACT_PATH.exists():
            data = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {
        "thresholds": {"warn_below": 8.0, "fail_below": 6.0},
        "dimensions": [],
    }


def collect_phase3_aperture_panel(
    *,
    repo_root: Path | None = None,
    d1_audits: bool = True,
) -> dict[str, Any]:
    """
    Collect structured Phase 3 aperture forcing facts for self-score (mirrors print_markdown checks).
    """
    root = repo_root or PROJECT_ROOT
    panel: dict[str, Any] = {
        "d3_violations": [],
        "d1_ctx_count": 0,
        "d4_bundle_present": False,
        "d4_bundle_name": None,
        "hash_chain_broken_count": 0,
        "fill_lineage_issue_count": 0,
    }

    recent_ctxs: list[str] = []
    try:
        from lumina_core.audit.aperture_audit_artifact import merge_d1_audit_context_ids

        recent_ctxs = merge_d1_audit_context_ids([], max_ctxs=8)
        panel["d1_ctx_count"] = len(recent_ctxs)
    except Exception as e:
        panel["d3_violations"].append(f"d1 ctx merge failed: {e}")

    if d1_audits and not recent_ctxs:
        panel["d3_violations"].append(
            "no decision_context_ids for D1 auto-audit (populate logs or run phase3_d4_genuine_evidence.py)"
        )

    try:
        import sys

        sys.path.insert(0, str(root))
        from lumina_core.risk.decision_lineage import is_chain_healthy, reconstruct_risk_decision_chain

        broken = 0
        for ctx in recent_ctxs[:6]:
            try:
                chain = reconstruct_risk_decision_chain(ctx, event_bus=None, limit=50)
                if chain:
                    healthy = is_chain_healthy(chain)
                    has_core = any(
                        item.get("topic")
                        in ("admission.gate_entry", "risk.policy.decision", "risk.final_arbitration.result")
                        for item in chain
                    )
                    if not healthy or not has_core:
                        broken += 1
                        panel["d3_violations"].append(
                            f"broken/incomplete risk chain ctx={ctx} (healthy={healthy}, nodes={len(chain)})"
                        )
            except Exception:
                continue
        panel["hash_chain_broken_count"] = broken
    except Exception as e:
        panel["d3_violations"].append(f"hash chain check skipped: {e}")

    try:
        import os

        state_dir = os.getenv("LUMINA_STATE_DIR", "state")
        bb_path = Path(state_dir) / "agent_blackboard.jsonl"
        fill_issues = 0
        if bb_path.exists():
            lines = bb_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-100:]
            for line in reversed(lines):
                try:
                    rec = json.loads(line)
                    topic = str(rec.get("topic", "")).lower()
                    if "fill.received" in topic or "execution.fill" in topic:
                        payload = rec.get("payload", {}) or {}
                        cid = str(payload.get("decision_context_id", "") or rec.get("correlation_id", ""))
                        if cid:
                            has_lineage = bool(payload.get("decision_context_id") and payload.get("prev_hash"))
                            if not has_lineage:
                                fill_issues += 1
                                if fill_issues <= 5:
                                    panel["d3_violations"].append(
                                        f"missing fill lineage ctx={cid} (blackboard)"
                                    )
                except Exception:
                    continue
        panel["fill_lineage_issue_count"] = fill_issues
    except Exception as e:
        panel["d3_violations"].append(f"fill lineage check skipped: {e}")

    audits_dir = root / "state" / "audits"
    if audits_dir.is_dir():
        bundles = sorted(
            list(audits_dir.glob("d4_genuine_campaign_evidence_*.md"))
            + list(audits_dir.glob("d4_30day_campaign_evidence_*.md")),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )
        if bundles:
            panel["d4_bundle_present"] = True
            panel["d4_bundle_name"] = bundles[0].name

    return panel


def score_guardian_aperture_self_consistency(report: dict[str, Any]) -> dict[str, Any]:
    """
    Score Guardian report dict against aperture contract (0-10 overall + per-dimension).
    """
    contract = _load_contract()
    thresholds = contract.get("thresholds", {}) or {}
    warn_below = float(thresholds.get("warn_below", 8.0))
    fail_below = float(thresholds.get("fail_below", 6.0))

    panel = report.get("phase3_aperture_panel") or {}
    d3_violations = list(panel.get("d3_violations") or [])
    d1_ctx = int(panel.get("d1_ctx_count") or 0)
    d4_present = bool(panel.get("d4_bundle_present"))
    d5 = report.get("d5_capital_aperture") or {}
    aperture = report.get("aperture_integrity") or {}

    dimension_scores: dict[str, float] = {}

    struct_ok = report.get("overall_status") == "PASS" and (report.get("summary", {}).get("failed", 0) == 0)
    dimension_scores["structural_dna"] = 10.0 if struct_ok else 0.0

    ap_score = float(aperture.get("score", 0.0) or 0.0)
    dimension_scores["aperture_integrity"] = min(10.0, ap_score)

    dimension_scores["d5_no_bypass"] = 10.0 if d5.get("ok") else 0.0

    if not d3_violations:
        dimension_scores["d3_forcing"] = 10.0
    else:
        dimension_scores["d3_forcing"] = max(0.0, 10.0 - 2.0 * len(d3_violations))

    dimension_scores["d4_genuine_surface"] = 10.0 if d4_present else 6.0

    dimension_scores["d1_ctx_pool"] = 10.0 if d1_ctx >= 1 else 3.0

    weights = {
        "structural_dna": 1.0,
        "aperture_integrity": 1.5,
        "d5_no_bypass": 2.0,
        "d3_forcing": 2.0,
        "d4_genuine_surface": 1.0,
        "d1_ctx_pool": 1.0,
    }
    total_w = sum(weights.values())
    overall = sum(dimension_scores.get(k, 0.0) * weights.get(k, 0.0) for k in weights) / total_w
    overall = round(overall, 2)

    status = "GREEN"
    if overall < fail_below:
        status = "RED"
    elif overall < warn_below:
        status = "YELLOW"

    missing_fields = [
        f for f in (contract.get("required_report_fields") or [])
        if f not in report and f != "phase3_aperture_panel"
    ]
    if "phase3_aperture_panel" in (contract.get("required_report_fields") or []) and not panel:
        missing_fields.append("phase3_aperture_panel")

    return {
        "ok": overall >= warn_below and not missing_fields,
        "overall_score": overall,
        "status": status,
        "warn_below": warn_below,
        "fail_below": fail_below,
        "dimension_scores": dimension_scores,
        "d3_violation_count": len(d3_violations),
        "missing_report_fields": missing_fields,
        "notes": (
            "Heuristic self-score v1: structural + aperture_integrity + D5 + D3 panel + D4 surface + D1 pool. "
            "Not a substitute for human review."
        ),
    }


def enrich_report_with_phase3_panel(
    report: dict[str, Any],
    *,
    repo_root: Path | None = None,
    d1_audits: bool = True,
) -> dict[str, Any]:
    """Attach phase3_aperture_panel and guardian_self_score to report."""
    report["phase3_aperture_panel"] = collect_phase3_aperture_panel(
        repo_root=repo_root or PROJECT_ROOT,
        d1_audits=d1_audits,
    )
    report["guardian_self_score"] = score_guardian_aperture_self_consistency(report)
    return report
