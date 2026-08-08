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

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from lumina_core.evolution.evolution_tree import build_evolution_tree
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






# ── Internal helpers ──────────────────────────────────────────────────────────


















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


@router.get("/tree")
async def get_evolution_tree(
    depth: int = Query(10, ge=1, le=20),
    include_rejected: bool = Query(False),
    root_hash: str | None = Query(None),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Return DNA lineage graph for Command Deck evolution visualization."""
    _verify_api_key(x_api_key, require_admin=False)
    return build_evolution_tree(
        depth=depth,
        include_rejected=include_rejected,
        root_hash=root_hash,
    )


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


from lumina_os.backend.evolution_endpoints_auth import (  # noqa: E402,F401
    _append_decision,
    _load_decisions,
    _load_proposals,
    _require_dashboard_key_for_mode,
    _runtime_mode,
    _verify_api_key,
    _verify_legacy_dashboard_key,
    _verify_with_security_module,
    set_observability_service,
    set_security_module,
)
from lumina_os.backend.evolution_endpoints_actions import (  # noqa: E402
    approve_proposal,
    reject_proposal,
)

approve_proposal = router.post("/approve")(approve_proposal)
reject_proposal = router.post("/reject")(reject_proposal)


# ── M1–M3 architecture meta / evolution axes (read-only, never auto-apply) ────


@router.get("/architecture-meta/status")
async def architecture_meta_status_endpoint(
    capital_mode: str = Query("sim"),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Architecture meta status: scan + proposals + axes + approval SSOT (M1–M3)."""
    _verify_api_key(x_api_key, require_admin=False)
    from lumina_core.architecture_meta.pipeline import architecture_meta_status

    root = Path(os.getenv("LUMINA_WORKSPACE_ROOT", "."))
    return architecture_meta_status(workspace_root=root, capital_mode=capital_mode)


@router.post("/architecture-meta/scan")
async def architecture_meta_scan_endpoint(
    enabled: bool = Query(False, description="Generate inventory proposals (still never applies)"),
    capital_mode: str = Query("sim"),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Run a dry architecture-meta cycle. Never applies patches (human gate only)."""
    _verify_api_key(x_api_key, require_admin=False)
    from lumina_core.architecture_meta.pipeline import run_architecture_meta_dry_cycle

    root = Path(os.getenv("LUMINA_WORKSPACE_ROOT", "."))
    return run_architecture_meta_dry_cycle(
        enabled=bool(enabled),
        workspace_root=root,
        write_journal=True,
        capital_mode=capital_mode,
    )


@router.get("/axes")
async def evolution_axes_endpoint(
    capital_mode: str = Query("sim"),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """M3 evolution axes catalog + M2 meta-agent approval snapshot."""
    _verify_api_key(x_api_key, require_admin=False)
    from lumina_core.architecture_meta.evolution_axes import evolution_axes_snapshot

    return evolution_axes_snapshot(capital_mode=capital_mode)


@router.get("/meta-approval")
async def meta_agent_approval_endpoint(
    capital_mode: str = Query("sim"),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """M2 meta-agent approval SSOT (fail-closed REAL / architecture)."""
    _verify_api_key(x_api_key, require_admin=False)
    from lumina_core.architecture_meta.meta_agent_approval import meta_agent_approval_snapshot

    return meta_agent_approval_snapshot(capital_mode=capital_mode)
