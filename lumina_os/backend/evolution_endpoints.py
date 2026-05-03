"""FastAPI evolution-approval endpoints for Lumina v51.

Endpoints
---------
GET  /api/evolution/proposals          – List all open (undecided) proposals
POST /api/evolution/approve            – Approve a challenger, promote to champion
POST /api/evolution/reject             – Reject a proposal with a reason

State files
-----------
  state/evolution_log.jsonl       – Source of challenger proposals (append-only)
  state/evolution_decisions.jsonl – Audit log of approve/reject decisions
  state/evolution_trigger.json    – Written on approve to signal the meta-agent

Requires ``X-API-Key`` for mutations. When ``set_security_module()`` is wired from
``app.py``, keys and admin role follow ``config.yaml`` ``security.api_keys``;
otherwise ``LUMINA_DASHBOARD_API_KEY`` is used (legacy).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from lumina_core.audit import get_audit_logger
from lumina_core.governance import ApprovalChain, RealPromotionPayload, SignedApproval
from lumina_core.evolution.promotion_readiness import check_promotion_readiness
from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION

router = APIRouter(prefix="/api/evolution", tags=["evolution"])

logger = logging.getLogger(__name__)

# ── Service singleton injected at FastAPI startup ─────────────────────────────
_obs_service: Any = None
# Same dict as ``lumina_os.backend.app`` ``SECURITY`` from ``get_security_module`` (optional).
_SECURITY_MODULE: dict[str, Any] | None = None

# ── State file paths (overridable via env vars for testing) ───────────────────
_EVOLUTION_LOG = Path(os.getenv("EVOLUTION_LOG_PATH", "state/evolution_log.jsonl"))
_EVOLUTION_DECISIONS = Path(os.getenv("EVOLUTION_DECISIONS_PATH", "state/evolution_decisions.jsonl"))
_EVOLUTION_TRIGGER = Path(os.getenv("EVOLUTION_TRIGGER_PATH", "state/evolution_trigger.json"))
_APPROVED_HYPERPARAMS = Path(os.getenv("APPROVED_HYPERPARAMS_PATH", "state/approved_hyperparams.json"))

# ── API key env var (single shared key for the dashboard) ─────────────────────
_DASHBOARD_API_KEY = os.getenv("LUMINA_DASHBOARD_API_KEY", "")


def set_observability_service(obs: Any) -> None:
    """Inject the shared ObservabilityService instance at app startup."""
    global _obs_service
    _obs_service = obs


def set_security_module(sec: dict[str, Any] | None) -> None:
    """Inject the shared security module dict from ``app.py`` (API keys, audit, config)."""
    global _SECURITY_MODULE
    _SECURITY_MODULE = sec


# ── Internal helpers ──────────────────────────────────────────────────────────


def _load_proposals() -> list[dict[str, Any]]:
    """Return all entries with status=='proposed' from the evolution log."""
    if not _EVOLUTION_LOG.exists():
        return []
    proposals: list[dict[str, Any]] = []
    with _EVOLUTION_LOG.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry: dict[str, Any] = json.loads(raw)
                if entry.get("status") == "proposed":
                    proposals.append(entry)
            except json.JSONDecodeError:
                pass
    return proposals


def _load_decisions() -> dict[str, dict[str, Any]]:
    """Return all decisions keyed by proposal hash."""
    if not _EVOLUTION_DECISIONS.exists():
        return {}
    decisions: dict[str, dict[str, Any]] = {}
    with _EVOLUTION_DECISIONS.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry: dict[str, Any] = json.loads(raw)
                h = entry.get("entry_hash")
                if h:
                    decisions[str(h)] = entry
            except json.JSONDecodeError:
                pass
    return decisions


def _append_decision(record: dict[str, Any]) -> None:
    """Append a single decision record to the decisions audit log."""
    _EVOLUTION_DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    get_audit_logger().register_stream("evolution.decisions", _EVOLUTION_DECISIONS)
    get_audit_logger().append(
        stream="evolution.decisions",
        payload=record,
        path=_EVOLUTION_DECISIONS,
        mode=_runtime_mode(),
        actor_id="evolution_endpoints",
        severity="info",
    )


def _runtime_mode() -> str:
    raw = os.getenv("LUMINA_MODE") or os.getenv("TRADE_MODE") or os.getenv("LUMINA_RUNTIME_MODE") or "sim"
    return str(raw).strip().lower() or "sim"


def _require_dashboard_key_for_mode() -> bool:
    return _runtime_mode() in {"real", "paper", "sim_real_guard"}


def _verify_legacy_dashboard_key(x_api_key: Optional[str]) -> None:
    if _require_dashboard_key_for_mode() and not _DASHBOARD_API_KEY:
        raise HTTPException(status_code=503, detail="Dashboard API key missing in protected mode")
    if not _DASHBOARD_API_KEY:
        return
    if not x_api_key or x_api_key != _DASHBOARD_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _verify_with_security_module(
    x_api_key: Optional[str],
    *,
    require_admin: bool,
) -> dict[str, Any]:
    sec = _SECURITY_MODULE
    if sec is None:
        raise HTTPException(status_code=503, detail="Security module not initialized")
    audit = sec.get("audit_log")
    if not x_api_key:
        if audit is not None and hasattr(audit, "log_auth_attempt"):
            audit.log_auth_attempt("unknown", False, "api_key")
        raise HTTPException(status_code=401, detail="API key required")
    api_key = sec.get("api_key")
    if api_key is None or not hasattr(api_key, "verify_api_key"):
        raise HTTPException(status_code=503, detail="API key authenticator unavailable")
    meta = api_key.verify_api_key(x_api_key)
    if not meta:
        if audit is not None and hasattr(audit, "log_auth_attempt"):
            audit.log_auth_attempt("unknown", False, "api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")
    if audit is not None and hasattr(audit, "log_auth_attempt"):
        audit.log_auth_attempt(meta.get("name", "api_key"), True, "api_key")
    cfg = sec.get("config")
    admin_required = bool(getattr(cfg, "admin_role_required", True)) if cfg is not None else True
    if require_admin and admin_required:
        role = str(meta.get("role", "user"))
        if role != "admin":
            if audit is not None and hasattr(audit, "log_unauthorized_access"):
                audit.log_unauthorized_access(
                    meta.get("name", "unknown"),
                    "evolution_mutation",
                    f"insufficient_role_{role}",
                )
            raise HTTPException(status_code=403, detail="Admin role required for evolution mutations")
    return {"api_key": x_api_key, "metadata": meta}


def _verify_api_key(x_api_key: Optional[str], *, require_admin: bool = False) -> None:
    """Authenticate evolution routes; uses injected security or legacy dashboard key."""
    if not _require_dashboard_key_for_mode():
        return
    if _SECURITY_MODULE is not None:
        _verify_with_security_module(x_api_key, require_admin=require_admin)
        return
    _verify_legacy_dashboard_key(x_api_key)


# ── Request models ─────────────────────────────────────────────────────────────


class ApproveRequest(BaseModel):
    hash: str
    challenger_name: str
    require_human_approval: bool = True
    promotion_payload: RealPromotionPayload | None = None
    approvals: list[SignedApproval] = Field(default_factory=list)


class RejectRequest(BaseModel):
    hash: str
    reason: str


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/proposals")
async def get_proposals(
    x_api_key: Optional[str] = Header(None),
) -> list[dict[str, Any]]:
    """Return all open (undecided) proposals, newest first."""
    _verify_api_key(x_api_key, require_admin=False)
    proposals = _load_proposals()
    decisions = _load_decisions()
    open_proposals = [p for p in proposals if p.get("hash") not in decisions]
    # Newest first
    open_proposals.sort(key=lambda p: str(p.get("timestamp", "")), reverse=True)
    return open_proposals


@router.post("/approve")
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


@router.post("/reject")
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
