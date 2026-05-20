"""FastAPI Birth Phase endpoints — start and poll LuminaBirthEngine via BirthService."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

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
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
    force: bool = Query(False),
    practice_mode: bool = Query(False),
    explicit_user_start: bool = Query(True),
    continue_training: bool = Query(False),
) -> dict[str, Any]:
    return birth_service.start_birth(
        target_trades=target_trades,
        force=force,
        practice_mode=practice_mode,
        explicit_user_start=explicit_user_start,
        continue_training=continue_training,
    )


@router.post("/stop")
async def stop_birth() -> dict[str, Any]:
    return birth_service.stop_birth()


@router.post("/extra-training")
async def extra_training() -> dict[str, Any]:
    """Clear birth completion artifacts so operator can run extra training."""
    from lumina_launcher.core.first_boot import FirstBootManager

    root = birth_service.workspace_root
    FirstBootManager(root).clear_completion_artifacts_for_extra_training()
    return {"ok": True, "message": "Completion artifacts cleared — start birth with continue_training"}


@router.get("/status")
async def get_birth_status() -> dict[str, Any]:
    return _enrich_status(birth_service.get_status())


class BirthSettingsRequest(BaseModel):
    training_trades: int = Field(ge=500, le=2_000_000)
    prefer_real_data_only: bool = True
    max_real_days: int = Field(ge=30, le=3650)
    allow_minimal_synthetic_fallback: bool = False
    require_real_simulator_data: bool = True


@router.post("/settings")
async def save_birth_settings(body: BirthSettingsRequest) -> dict[str, Any]:
    from lumina_launcher.core.first_boot import FirstBootManager

    root = birth_service.workspace_root
    manager = FirstBootManager(root)
    status = birth_service.get_status()
    if str(status.get("status", "")).lower() in {"running", "active", "started"}:
        raise HTTPException(
            status_code=409,
            detail="Cannot change settings while birth training is active",
        )
    manager.save_full_settings(
        training_trades=body.training_trades,
        prefer_real_data_only=body.prefer_real_data_only,
        max_real_days=body.max_real_days,
        allow_minimal_synthetic_fallback=body.allow_minimal_synthetic_fallback,
        require_real_simulator_data=body.require_real_simulator_data,
        mark_user_configured=True,
    )
    return {"ok": True, "settings": manager.read_settings()}


@router.post("/adjust-max-days")
async def adjust_max_real_days() -> dict[str, Any]:
    """Raise max_real_days to estimated window (Streamlit 'Pas max days aan' parity)."""
    from lumina_core.first_boot_ui import estimate_first_boot_real_days
    from lumina_launcher.core.first_boot import FirstBootManager

    root = birth_service.workspace_root
    manager = FirstBootManager(root)
    settings = manager.read_settings()
    estimate_days = int(
        estimate_first_boot_real_days(int(settings.get("training_trades", 25000)))
    )
    new_max = max(int(settings.get("max_real_days", 30)), estimate_days)
    manager.save_full_settings(
        training_trades=int(settings.get("training_trades", 25000)),
        prefer_real_data_only=bool(settings.get("prefer_real_data_only", True)),
        max_real_days=new_max,
        allow_minimal_synthetic_fallback=bool(settings.get("allow_minimal_synthetic_fallback", False)),
        require_real_simulator_data=bool(settings.get("require_real_simulator_data", True)),
        mark_user_configured=True,
    )
    return {"ok": True, "max_real_days": new_max, "estimated_days": estimate_days}


@router.get("/logs-tail")
async def get_birth_logs_tail(limit: int = Query(40, ge=5, le=200)) -> dict[str, Any]:
    root = Path(birth_service.workspace_root)
    logs_dir = root / "logs"
    stderr_candidates = sorted(logs_dir.glob("runtime_stderr*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    stderr_tail: list[str] = []
    stderr_path = str(stderr_candidates[0]) if stderr_candidates else ""
    if stderr_path:
        try:
            lines = Path(stderr_path).read_text(encoding="utf-8", errors="replace").splitlines()
            stderr_tail = lines[-limit:]
        except OSError:
            stderr_tail = []
    full_log = logs_dir / "lumina_full_log.csv"
    full_tail: list[str] = []
    if full_log.is_file():
        try:
            full_tail = full_log.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        except OSError:
            full_tail = []
    return {
        "stderr_path": stderr_path,
        "stderr_tail": stderr_tail,
        "full_log_path": str(full_log),
        "full_log_tail": full_tail,
    }
