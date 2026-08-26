"""Maturation ladder + phase continuum API (ADR-0027 / organism hub)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lumina_launcher.services.birth_service import birth_service
from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
    maturation_eligible_for_real,
    sync_maturation_from_birth_state,
)
from lumina_core.maturity.maturity_service import maturity_service

router = APIRouter(prefix="/api/maturity", tags=["maturity"])


class ApproveRealRequest(BaseModel):
    confirm: bool = Field(default=False, description="Operator confirms REAL capital risk")


class PreferencesRequest(BaseModel):
    advance_mode: Literal["manual", "telegram", "auto_evolve"] = "manual"


class StartPhaseRequest(BaseModel):
    phase: str = Field(..., description="Phase id: awakening|playground|apprenticeship|proving_ground")
    explicit_user_start: bool = Field(default=True, description="Must be true (fail-closed)")


class AdvanceRequest(BaseModel):
    confirm: bool = Field(default=True, description="Start next phase from hub")
    telegram_token: str | None = Field(
        default=None,
        description="Token from Telegram advance request (mode=telegram)",
    )


class WipePhaseRequest(BaseModel):
    phase: str
    confirm: bool = False


class WipeAllRequest(BaseModel):
    confirm: bool = False


def _configure_service() -> None:
    maturity_service.configure_workspace(birth_service.workspace_root)


@router.get("/progress")
async def get_maturation_progress() -> dict[str, Any]:
    root = birth_service.workspace_root
    progress = sync_maturation_from_birth_state(root)
    eligible, blockers = maturation_eligible_for_real(root)
    _configure_service()
    hub = maturity_service.get_hub()
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
        "advance_mode": hub.get("advance_mode"),
        "completed_phases": hub.get("completed_phases"),
        "next_phase": hub.get("next_phase"),
        "active_phase": hub.get("active_phase"),
        "runner_active": hub.get("runner_active"),
    }


@router.get("/birth-exit")
async def get_birth_exit_status() -> dict[str, Any]:
    """H7 / ADR-0036: Birth survival exit vs post-birth maturation gates."""
    _configure_service()
    payload = maturity_service.birth_exit_status()
    payload["local_only"] = True
    return payload


@router.get("/honesty")
async def get_maturity_honesty() -> dict[str, Any]:
    """M6: continuum / READY_FOR_REAL / REAL eligibility honesty (no conflation)."""
    _configure_service()
    payload = maturity_service.honesty_status()
    payload["local_only"] = True
    return payload


@router.get("/hub")
async def get_maturity_hub() -> dict[str, Any]:
    """Genesis-like inter-phase hub: learned, next steps, advance mode, wipe controls."""
    _configure_service()
    # Keep continuum synced with birth artifacts on every hub open / restart
    try:
        if birth_service.certificate_ok() or birth_service.artifacts_ok():
            from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

            if not is_birth_exit_sufficient(birth_service.workspace_root):
                return maturity_service.get_hub()
            continuum = maturity_service.get_hub()
            completed = set(continuum.get("completed_phases") or [])
            if "birth" not in completed:
                maturity_service.mark_birth_complete_from_artifacts()
    except Exception:
        pass
    return maturity_service.get_hub()


@router.post("/preferences")
async def set_maturity_preferences(body: PreferencesRequest) -> dict[str, Any]:
    _configure_service()
    return maturity_service.set_preferences(advance_mode=body.advance_mode)


@router.post("/start-phase")
async def start_maturity_phase(body: StartPhaseRequest) -> dict[str, Any]:
    _configure_service()
    result = maturity_service.start_phase(
        body.phase,
        explicit_user_start=bool(body.explicit_user_start),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/advance")
async def advance_next_phase(body: AdvanceRequest) -> dict[str, Any]:
    """Manual or Telegram-confirmed start of the next continuum phase."""
    _configure_service()
    result = maturity_service.advance(
        confirm=bool(body.confirm),
        telegram_token=body.telegram_token,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/stop-phase")
async def stop_maturity_phase() -> dict[str, Any]:
    _configure_service()
    return maturity_service.stop_phase()


@router.post("/wipe-phase")
async def wipe_maturity_phase(body: WipePhaseRequest) -> dict[str, Any]:
    _configure_service()
    result = maturity_service.wipe_phase(body.phase, confirm=bool(body.confirm))
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/wipe-all")
async def wipe_all_maturation(body: WipeAllRequest) -> dict[str, Any]:
    _configure_service()
    result = maturity_service.wipe_all(confirm=bool(body.confirm))
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/approve-real")
async def approve_real_mode(body: ApproveRealRequest) -> dict[str, Any]:
    """Record operator REAL approval after maturation gates pass (fail-closed).

    H2: Twin cannot call this path productively without operator confirm=true.
    """
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Operator confirmation required (confirm=true)")

    root = birth_service.workspace_root
    eligible, blockers = maturation_eligible_for_real(root)
    if not eligible:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "REAL blocked by maturation ladder",
                "blockers": blockers,
                "twin_cannot_bypass": True,
            },
        )

    from lumina_core.maturity.milestone_hooks import hook_human_real_approval
    from lumina_core.maturity.continuum import mark_phase_completed
    from lumina_core.risk.real_multi_gate import evaluate_real_capital_readiness

    hook_human_real_approval(root, source="command_deck")
    try:
        mark_phase_completed(
            root,
            "real",
            learned={"note": "Human REAL approval recorded"},
            exit_proofs=["human_real_approval"],
        )
    except Exception:
        pass
    progress = sync_maturation_from_birth_state(root)
    readiness = evaluate_real_capital_readiness(root)
    return {
        "ok": True,
        "current_phase": progress.current_phase.value,
        "milestones_reached": list(progress.milestones_reached),
        "real_readiness": readiness,
        "twin_cannot_bypass": True,
    }


@router.get("/real-gate-status")
async def get_real_gate_status() -> dict[str, Any]:
    """H2: REAL multi-gate readiness (maturation + human; Twin cannot bypass)."""
    from lumina_core.risk.real_multi_gate import evaluate_real_capital_readiness

    root = birth_service.workspace_root
    return evaluate_real_capital_readiness(root)


@router.get("/telegram-pending")
async def get_telegram_pending_advance() -> dict[str, Any]:
    """Peek pending telegram advance (no raw token leak)."""
    _configure_service()
    hub = maturity_service.get_hub()
    pending = hub.get("pending_advance")
    if not isinstance(pending, dict):
        return {"ok": True, "pending": None}
    return {
        "ok": True,
        "pending": {
            "from": pending.get("from"),
            "to": pending.get("to"),
            "created_at": pending.get("created_at"),
            "expires_at": pending.get("expires_at"),
            "expired": bool(pending.get("expired")),
            "has_token": bool(pending.get("has_token")),
        },
    }


@router.post("/telegram-confirm")
async def telegram_confirm_advance(
    token: str = Query(..., min_length=8, description="Token from Telegram message"),
) -> dict[str, Any]:
    """Confirm next phase via Telegram token (or hub paste). Rejects expired TTL."""
    _configure_service()
    result = maturity_service.advance(confirm=True, telegram_token=token)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/refresh-advance")
async def refresh_telegram_advance() -> dict[str, Any]:
    """Re-issue a TTL-limited Telegram advance token for the next phase."""
    _configure_service()
    from lumina_core.maturity.advance_policy import reissue_telegram_advance

    result = reissue_telegram_advance(maturity_service.workspace_root)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result
