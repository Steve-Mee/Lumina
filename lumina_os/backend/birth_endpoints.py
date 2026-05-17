"""FastAPI Birth Phase endpoints — start and poll LuminaBirthEngine via BirthService."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from lumina_launcher.services.birth_service import birth_service

router = APIRouter(prefix="/api/birth", tags=["birth"])


def _enrich_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach SSOT artifact readiness (completion flag + policy zip)."""
    payload["artifacts_ok"] = birth_service.artifacts_ok()
    payload["artifacts_label"] = (
        "Artifacts OK" if payload["artifacts_ok"] else "Artifacts missing"
    )
    payload["phase_label"] = "Birth Phase"
    return payload


@router.post("/start")
async def start_birth(
    target_trades: int = Query(25000, ge=1000, le=5_000_000),
    force: bool = Query(False),
) -> dict[str, Any]:
    return birth_service.start_birth(target_trades=target_trades, force=force)


@router.get("/status")
async def get_birth_status() -> dict[str, Any]:
    return _enrich_status(birth_service.get_status())
