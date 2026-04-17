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

Requires an X-API-Key header for approve/reject mutations.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/evolution", tags=["evolution"])

# ── Service singleton injected at FastAPI startup ─────────────────────────────
_obs_service: Any = None

# ── State file paths (overridable via env vars for testing) ───────────────────
_EVOLUTION_LOG = Path(os.getenv("EVOLUTION_LOG_PATH", "state/evolution_log.jsonl"))
_EVOLUTION_DECISIONS = Path(
    os.getenv("EVOLUTION_DECISIONS_PATH", "state/evolution_decisions.jsonl")
)
_CONFIG_PATH = Path(os.getenv("LUMINA_CONFIG", "config.yaml"))
_EVOLUTION_TRIGGER = Path(os.getenv("EVOLUTION_TRIGGER_PATH", "state/evolution_trigger.json"))

# ── API key env var (single shared key for the dashboard) ─────────────────────
_DASHBOARD_API_KEY = os.getenv("LUMINA_DASHBOARD_API_KEY", "")


def set_observability_service(obs: Any) -> None:
    """Inject the shared ObservabilityService instance at app startup."""
    global _obs_service
    _obs_service = obs


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
                h = entry.get("hash")
                if h:
                    decisions[str(h)] = entry
            except json.JSONDecodeError:
                pass
    return decisions


def _append_decision(record: dict[str, Any]) -> None:
    """Append a single decision record to the decisions audit log."""
    _EVOLUTION_DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    with _EVOLUTION_DECISIONS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _verify_api_key(x_api_key: Optional[str]) -> None:
    """Raise 401 unless the provided key matches the configured dashboard key."""
    if not _DASHBOARD_API_KEY:
        return  # key auth disabled – allow all (dev / paper mode)
    if not x_api_key or x_api_key != _DASHBOARD_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ── Request models ─────────────────────────────────────────────────────────────


class ApproveRequest(BaseModel):
    hash: str
    challenger_name: str


class RejectRequest(BaseModel):
    hash: str
    reason: str


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/proposals")
async def get_proposals(
    x_api_key: Optional[str] = Header(None),
) -> list[dict[str, Any]]:
    """Return all open (undecided) proposals, newest first."""
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
    _verify_api_key(x_api_key)

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

    # ── 1. Update config.yaml with the promoted hyperparams ──────────────────
    if new_hyperparams and _CONFIG_PATH.exists():
        with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
            cfg: dict[str, Any] = yaml.safe_load(fh) or {}
        risk_cfg: dict[str, Any] = cfg.setdefault("risk", {})
        risk_cfg.update(new_hyperparams)
        with _CONFIG_PATH.open("w", encoding="utf-8") as fh:
            yaml.dump(cfg, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

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
                f"Challenger **{body.challenger_name}** promoted to champion. "
                f"Hyperparams applied: {new_hyperparams}"
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
    _verify_api_key(x_api_key)

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
