"""Maturation ladder API (ADR-0027)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lumina_launcher.services.birth_service import birth_service
from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
    maturation_eligible_for_real,
    sync_maturation_from_birth_state,
)

router = APIRouter(prefix="/api/maturity", tags=["maturity"])


class ApproveRealRequest(BaseModel):
    confirm: bool = Field(default=False, description="Operator confirms REAL capital risk")


@router.get("/progress")
async def get_maturation_progress() -> dict[str, Any]:
    root = birth_service.workspace_root
    progress = sync_maturation_from_birth_state(root)
    eligible, blockers = maturation_eligible_for_real(root)
    return {
        "current_phase": progress.current_phase.value,
        "milestones_reached": list(progress.milestones_reached),
        "updated_at": progress.updated_at,
        "metadata": dict(progress.metadata),
        "real_trading_eligible": eligible,
        "real_trading_blockers": blockers,
        "evolution_proof_ok": birth_service.evolution_proof_ok(),
        "certificate_ok": birth_service.certificate_ok(),
        "phases": [p.value for p in MaturationPhase],
    }


@router.post("/approve-real")
async def approve_real_mode(body: ApproveRealRequest) -> dict[str, Any]:
    """Record operator REAL approval after maturation gates pass (fail-closed)."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Operator confirmation required (confirm=true)")

    root = birth_service.workspace_root
    eligible, blockers = maturation_eligible_for_real(root)
    if not eligible:
        raise HTTPException(
            status_code=422,
            detail={"message": "REAL blocked by maturation ladder", "blockers": blockers},
        )

    from lumina_core.maturity.milestone_hooks import hook_human_real_approval

    hook_human_real_approval(root, source="command_deck")
    progress = sync_maturation_from_birth_state(root)
    return {
        "ok": True,
        "current_phase": progress.current_phase.value,
        "milestones_reached": list(progress.milestones_reached),
    }
