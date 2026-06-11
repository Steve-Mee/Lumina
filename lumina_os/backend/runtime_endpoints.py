"""Runtime engine control endpoints for the Neural Command Deck."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from lumina_launcher.core.process_manager import ProcessManager

router = APIRouter(prefix="/api/runtime", tags=["runtime"])

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_ENTRY = Path("lumina_core/engine/runtime_entrypoint.py")
_process_manager: ProcessManager | None = None


def _get_process_manager() -> ProcessManager:
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager(_REPO_ROOT, _RUNTIME_ENTRY)
    return _process_manager


def _check_api_key(x_api_key: str | None) -> None:
    from backend.app import SECURITY

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    key_meta = SECURITY["api_key"].verify_api_key(x_api_key)
    if not key_meta:
        raise HTTPException(status_code=401, detail="Invalid API key")


class RuntimeStartRequest(BaseModel):
    mode: str = Field(default="auto", description="Runtime mode: auto, sim, paper, real")


class RuntimeStatusResponse(BaseModel):
    alive: bool
    pid: int | None = None
    mode: str | None = None
    message: str = ""


@router.get("/status", response_model=RuntimeStatusResponse)
async def get_runtime_status(
    x_api_key: str | None = Header(None),
) -> RuntimeStatusResponse:
    _check_api_key(x_api_key)
    pm = _get_process_manager()
    alive = pm.is_process_alive()
    state = pm._load_process_state()
    pid = int(state.get("pid", 0) or 0) or None
    mode = str(state.get("mode") or "") or None
    return RuntimeStatusResponse(
        alive=alive,
        pid=pid if alive else None,
        mode=mode,
        message="Engine running" if alive else "Engine stopped",
    )


@router.post("/start")
async def start_runtime(
    body: RuntimeStartRequest | None = None,
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    pm = _get_process_manager()
    mode = (body.mode if body else "auto") or "auto"
    ok, message = pm.start_bot(mode=mode)
    if not ok:
        raise HTTPException(status_code=500, detail=message)
    state = pm._load_process_state()
    return {"ok": True, "message": message, "pid": int(state.get("pid", 0) or 0)}


@router.post("/stop")
async def stop_runtime(
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    pm = _get_process_manager()
    ok, message = pm.stop_bot()
    if not ok:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/overnight-sim")
async def run_overnight_sim(
    duration_minutes: int = Query(240, ge=30, le=480),
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    pm = _get_process_manager()
    if pm.is_process_alive():
        raise HTTPException(status_code=409, detail="Stop the running engine before overnight SIM")

    cmd = [
        sys.executable,
        "-m",
        "lumina_launcher",
        "--headless",
        "--mode=sim",
        f"--duration={duration_minutes}",
        "--overnight-sim",
        "--stability-check",
    ]
    env = os.environ.copy()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(_REPO_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to launch overnight SIM: {exc}") from exc
    return {
        "ok": True,
        "pid": proc.pid,
        "message": f"Overnight SIM started ({duration_minutes}m)",
    }


def _get_first_boot_manager():
    from lumina_launcher.core.first_boot import FirstBootManager

    return FirstBootManager(_REPO_ROOT)


@router.post("/stop-all")
async def stop_all_activities(
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    emergency: dict[str, Any] = {}
    try:
        from backend.app import _execute_cancel_all_orders, _execute_emergency_flatten

        cancel_result = _execute_cancel_all_orders()
        flatten_result = _execute_emergency_flatten()
        emergency = {
            "cancelled_count": int(cancel_result.get("cancelled_count", 0) or 0),
            "flattened_count": int(flatten_result.get("flattened_count", 0) or 0),
        }
    except Exception as exc:
        emergency = {"warning": str(exc)}

    pm = _get_process_manager()
    ok, message = pm.stop_all_activities()
    if not ok:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message, "emergency": emergency}


@router.post("/training-pause")
async def training_pause(
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    _get_first_boot_manager().request_pause()
    return {"ok": True, "message": "Training pause requested"}


@router.post("/training-resume")
async def training_resume(
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    _get_first_boot_manager().clear_pause_request()
    return {"ok": True, "message": "Training pause cleared"}


@router.post("/go-live")
async def go_live_real(
    confirm: bool = Query(False),
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    if not confirm:
        raise HTTPException(status_code=400, detail="Operator confirmation required (confirm=true)")

    from lumina_core.engine.sim_stability_checker import generate_stability_report
    from lumina_launcher.core.config_manager import ConfigManager

    report = generate_stability_report()
    if not bool(report.get("READY_FOR_REAL")):
        raise HTTPException(
            status_code=422,
            detail="Stability report not READY_FOR_REAL — complete 5-day green streak first",
        )

    config_manager = ConfigManager(_REPO_ROOT / ".env", _REPO_ROOT / "config.yaml")
    config_manager.write_env_file({"LUMINA_MODE": "real", "TRADE_MODE": "real"})
    return {
        "ok": True,
        "message": "LUMINA_MODE=real written to .env — restart engine to activate REAL mode",
        "consecutive_green_days": report.get("consecutive_green_days"),
    }


@router.post("/pause-trading")
async def pause_trading_safely(
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    """Flatten/cancel orders and stop runtime (REAL operations parity with Streamlit sidebar)."""
    _check_api_key(x_api_key)

    def _emergency() -> dict[str, Any]:
        try:
            from backend.app import _execute_cancel_all_orders, _execute_emergency_flatten

            cancel_result = _execute_cancel_all_orders()
            flatten_result = _execute_emergency_flatten()
            return {
                "ok": True,
                "cancelled_count": int(cancel_result.get("cancelled_count", 0) or 0),
                "flattened_count": int(flatten_result.get("flattened_count", 0) or 0),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    pm = _get_process_manager()
    ok, message = pm.pause_trading_safely(
        emergency_action=_emergency,
        require_emergency_success=True,
    )
    if not ok:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/reset-first-boot")
async def reset_first_boot(
    phrase: str = Query(..., min_length=1),
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    if phrase.strip() != "RESET FIRST BOOT":
        raise HTTPException(status_code=400, detail="Confirmation phrase mismatch")
    from lumina_launcher.core.blank_reset import run_post_setup_blank_reset

    pm = _get_process_manager()
    pm.stop_bot()
    result = run_post_setup_blank_reset(_REPO_ROOT)
    return {"ok": True, "result": result}
