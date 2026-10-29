"""S3 research seal for live PromotionGate. HMAC + nt_pit; dict evidence refuses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from lumina_core.evolution.promotion_gate import (
    PromotionCriterion,
    PromotionCriterionResult,
    PromotionGateDecision,
    PromotionGateEvidence,
)


def reject_untyped_research_evidence(
    dna_hash: str,
    *,
    timestamp: str,
    config_snapshot: dict[str, Any],
) -> PromotionGateDecision:
    reject = PromotionCriterionResult(
        criterion=PromotionCriterion.RESEARCH_SEAL,
        passed=False,
        score=0.0,
        threshold=1.0,
        actual=0.0,
        reason="research_evidence_not_typed",
    )
    return PromotionGateDecision(
        dna_hash=str(dna_hash or "").strip() or "unknown",
        promoted=False,
        criteria=[reject],
        timestamp=timestamp,
        config_snapshot=config_snapshot,
        fail_reasons=(PromotionCriterion.RESEARCH_SEAL.value,),
    )


def research_seal_result(evidence: PromotionGateEvidence) -> PromotionCriterionResult:
    mac = str(evidence.validation_mac or "").strip().lower()
    digest = str(evidence.report_sha256 or "").strip().lower()
    kind = str(evidence.tape_kind or "").strip().lower()
    mac_ok = len(mac) == 64 and all(ch in "0123456789abcdef" for ch in mac)
    sha_ok = len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest)
    tape_ok = kind == "nt_pit"
    passed = mac_ok and sha_ok and tape_ok
    if not mac_ok:
        reason = "research_mac_missing"
    elif not sha_ok:
        reason = "research_report_sha_missing"
    elif not tape_ok:
        reason = "survivors_not_nt_pit"
    else:
        reason = "research_seal_ok"
    return PromotionCriterionResult(
        criterion=PromotionCriterion.RESEARCH_SEAL,
        passed=passed,
        score=1.0 if passed else 0.0,
        threshold=1.0,
        actual=1.0 if passed else 0.0,
        reason=reason,
        metadata={"tape_kind": kind, "mac_len": len(mac), "sha_len": len(digest)},
    )


def load_promotion_gate_evidence(path: Path, *, dna_hash: str) -> PromotionGateEvidence | None:
    """Optional helper for offline/CLI checks from a JSON file."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload.setdefault("dna_hash", dna_hash)
    try:
        return PromotionGateEvidence.model_validate(payload)
    except ValidationError:
        return None
