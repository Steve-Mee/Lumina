"""Evolution approve/reject handlers (M5)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Header, HTTPException
from pydantic import BaseModel, Field

from lumina_core.audit import get_audit_logger
from lumina_core.governance import ApprovalChain, RealPromotionPayload, SignedApproval
from lumina_core.evolution.promotion_readiness import check_promotion_readiness
from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION
from lumina_os.backend.evolution_endpoints_auth import (
    _runtime_mode,
    _APPROVED_HYPERPARAMS,
    _EVOLUTION_TRIGGER,
    _append_decision,
    _load_decisions,
    _load_proposals,
    _obs_service,
    _verify_api_key,
)

logger = logging.getLogger(__name__)

class ApproveRequest(BaseModel):
    hash: str
    challenger_name: str
    require_human_approval: bool = True
    promotion_payload: RealPromotionPayload | None = None
    approvals: list[SignedApproval] = Field(default_factory=list)

class RejectRequest(BaseModel):
    hash: str
    reason: str

async def approve_proposal(
    body: ApproveRequest,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Approve a challenger, apply its hyperparams to config, and trigger the meta-agent."""
    _verify_api_key(x_api_key, require_admin=True)

    proposals = _load_proposals()
    decisions = _load_decisions()

    if body.hash in decisions:
        raise HTTPException(status_code=409, detail="Proposal already decided")

    proposal = next((p for p in proposals if p.get("hash") == body.hash), None)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    challenger = next(
        (c for c in proposal.get("challengers", []) if c.get("name") == body.challenger_name),
        None,
    )
    if challenger is None:
        raise HTTPException(
            status_code=404,
            detail=f"Challenger {body.challenger_name!r} not in this proposal",
        )

    new_hyperparams: dict[str, Any] = challenger.get("hyperparam_suggestion", {})
    if not isinstance(new_hyperparams, dict):
        raise HTTPException(status_code=422, detail="Invalid hyperparam payload")

    # Constitution gate before writing approved payload.
    candidate = {"hyperparam_suggestion": dict(new_hyperparams)}
    violations = TRADING_CONSTITUTION.audit(
        dna_content=json.dumps(candidate, ensure_ascii=True, sort_keys=True),
        mode=_runtime_mode(),
        raise_on_fatal=False,
    )
    fatals = [v.principle_name for v in violations if v.severity == "fatal"]
    if fatals:
        raise HTTPException(
            status_code=422,
            detail=f"Constitutional gate blocked approved hyperparams: {fatals}",
        )

    readiness = check_promotion_readiness(
        mode=_runtime_mode(),
        challenger=dict(challenger),
        proposal=dict(proposal) if isinstance(proposal, dict) else None,
    )
    if not readiness.ok:
        raise HTTPException(
            status_code=422,
            detail=f"Promotion readiness gate blocked approve: {readiness.message()}",
        )

    current_mode = _runtime_mode()
    if current_mode == "real":
        if not body.require_human_approval:
            raise HTTPException(status_code=422, detail="REAL mode requires human approval and cannot be disabled")
        if body.promotion_payload is None:
            raise HTTPException(status_code=422, detail="REAL mode requires a signed promotion payload")
        if body.promotion_payload.dna_hash != body.hash:
            raise HTTPException(status_code=422, detail="Promotion payload dna_hash does not match proposal hash")
        chain = ApprovalChain()
        approved, reason = chain.verify(payload=body.promotion_payload, signatures=body.approvals)
        if not approved:
            raise HTTPException(status_code=422, detail=f"Approval chain blocked REAL promotion: {reason}")

    # Persist approved payload in state; runtime can load this without mutating base config.
    _APPROVED_HYPERPARAMS.parent.mkdir(parents=True, exist_ok=True)
    approved_record = {
        "hash": body.hash,
        "challenger_name": body.challenger_name,
        "hyperparams": dict(new_hyperparams),
        "target_section": "risk_controller",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _APPROVED_HYPERPARAMS.write_text(
        json.dumps(approved_record, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    # ── 2. Write decision to audit log ────────────────────────────────────────
    _append_decision(
        {
            "hash": body.hash,
            "decision": "approved",
            "challenger_name": body.challenger_name,
            "hyperparams_applied": new_hyperparams,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    # ── 3. Write trigger file for the Self-Evolution Meta-Agent ───────────────
    _EVOLUTION_TRIGGER.parent.mkdir(parents=True, exist_ok=True)
    _EVOLUTION_TRIGGER.write_text(
        json.dumps(
            {
                "action": "promote_champion",
                "challenger_name": body.challenger_name,
                "hash": body.hash,
                "hyperparams": new_hyperparams,
                "target_section": "risk_controller",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    # ── 4. Observability: record metrics + fire approval event ────────────────
    if _obs_service is not None:
        confidence = float(challenger.get("confidence", 0.0))
        _obs_service.record_evolution_proposal(
            status="applied",
            confidence=confidence,
            best_candidate=body.challenger_name,
        )
        _obs_service.send_alert(
            title="Evolution Proposal Approved",
            message=(
                f"Challenger **{body.challenger_name}** promoted to champion. Hyperparams applied: {new_hyperparams}"
            ),
            severity="info",
            data={
                "hash": body.hash[:8],
                "challenger": body.challenger_name,
                **{k: str(v) for k, v in new_hyperparams.items()},
            },
        )

    return {
        "status": "approved",
        "challenger": body.challenger_name,
        "hyperparams_applied": new_hyperparams,
    }

async def reject_proposal(
    body: RejectRequest,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Reject a proposal and log the reason; fires an observability alert."""
    _verify_api_key(x_api_key, require_admin=True)

    proposals = _load_proposals()
    decisions = _load_decisions()

    if body.hash in decisions:
        raise HTTPException(status_code=409, detail="Proposal already decided")

    proposal = next((p for p in proposals if p.get("hash") == body.hash), None)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    _append_decision(
        {
            "hash": body.hash,
            "decision": "rejected",
            "reason": body.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    if _obs_service is not None:
        _obs_service.send_alert(
            title="Evolution Proposal Rejected",
            message=f"Proposal {body.hash[:8]}… rejected. Reason: {body.reason}",
            severity="warning",
            data={"hash": body.hash[:8], "reason": body.reason},
        )

    return {"status": "rejected", "reason": body.reason}
