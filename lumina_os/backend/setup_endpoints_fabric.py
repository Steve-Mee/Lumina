"""Setup fabric/configure endpoints (M5)."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

import os
from typing import Literal

from lumina_launcher.services.setup_persist import (
    persist_tauri_quick_config,
    scan_missing_credentials,
)
from lumina_os.backend.setup_onboarding_payload import (
    _services,
    _workspace_root,
    build_onboarding_payload,
)

logger = logging.getLogger(__name__)

class ConfigureCredentials(BaseModel):
    LUMINA_JWT_SECRET_KEY: str = ""
    CROSSTRADE_TOKEN: str = ""
    CROSSTRADE_ACCOUNT: str = ""
    LUMINA_ADMIN_API_KEY: str = ""
    LUMINA_FABRIC_TOKEN: str = ""
    XAI_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

class ConfigureRisk(BaseModel):
    kelly_fraction: float = Field(default=1.0, ge=0.05, le=1.0)
    daily_loss_cap: float | None = None
    max_total_open_risk: float = Field(default=3000.0, ge=50.0)
    real_capital_safety_threshold_usd: float = Field(default=1000.0, ge=100.0)

class ConfigureEvolution(BaseModel):
    approval_required: bool = True
    aggressive_evolution: bool = False
    max_mutation_depth: Literal["conservative", "moderate", "radical"] = "conservative"

class ConfigureTraining(BaseModel):
    training_trades: int = Field(default=25000, ge=1000, le=2_000_000)
    prefer_real_data_only: bool = True
    max_real_days: int = Field(default=56, ge=30, le=3650)
    allow_minimal_synthetic_fallback: bool = False
    require_real_simulator_data: bool = True
    stage1_winrate_pass_threshold: float | None = Field(default=None, ge=0.35, le=0.45)

class ConfigureRequest(BaseModel):
    mode: str = "sim"
    credentials: ConfigureCredentials = Field(default_factory=ConfigureCredentials)
    risk: ConfigureRisk = Field(default_factory=ConfigureRisk)
    evolution: ConfigureEvolution = Field(default_factory=ConfigureEvolution)
    training: ConfigureTraining = Field(default_factory=ConfigureTraining)
    selected_model_key: str | None = None

class FabricConnectionTestRequest(BaseModel):
    include_safe_mode: bool = True
    instrument: str = Field(default="MES", min_length=1, max_length=32)

async def fabric_connection_test(body: FabricConnectionTestRequest | None = None) -> dict[str, Any]:
    """Run SIM-only Execution Fabric diagnostics (Brain ↔ NT8 Fabric, not CrossTrade)."""
    from lumina_launcher.services.fabric_connection_diagnostics import (
        run_fabric_connection_diagnostics,
    )
    from lumina_launcher.services.fabric_link_certificate import write_certificate

    req = body or FabricConnectionTestRequest()
    instrument = str(req.instrument or "MES").strip().upper() or "MES"
    try:
        report = run_fabric_connection_diagnostics(
            include_safe_mode=bool(req.include_safe_mode),
            instrument=instrument,
        )
    except Exception as exc:
        logger.exception("fabric-connection-test failed")
        raise HTTPException(status_code=500, detail=f"Fabric diagnostics failed: {exc}") from exc
    payload = report.to_dict()
    certified = False
    if str(payload.get("overall", "")).lower() == "green":
        token = str(os.getenv("LUMINA_FABRIC_TOKEN") or os.getenv("LUMINA_NT8_API_KEY") or "").strip()
        write_certificate(
            overall="green",
            target=str(payload.get("target") or ""),
            token=token,
            workspace_root=_workspace_root(),
        )
        certified = True
    payload["certified"] = certified
    return payload

async def fabric_bootstrap() -> dict[str, Any]:
    """Zero-touch token + fabric.json + AddOn deploy (idempotent)."""
    from lumina_launcher.services.fabric_bootstrap import run_fabric_bootstrap
    from lumina_launcher.services.fabric_link_certificate import (
        is_fabric_link_green,
        is_halt_active,
        read_certificate,
        read_halt,
    )

    _, config_manager, _, _, _, _ = _services()
    root = _workspace_root()
    result = run_fabric_bootstrap(root, config_manager)
    ok, reason = is_fabric_link_green(workspace_root=root)
    result["fabric_link_green"] = ok
    result["fabric_link_reason"] = reason
    result["certificate"] = read_certificate(root)
    result["halt"] = read_halt(root) if is_halt_active(root) else None
    return result

async def fabric_link_status() -> dict[str, Any]:
    from lumina_launcher.services.fabric_link_certificate import (
        is_fabric_link_green,
        is_halt_active,
        read_certificate,
        read_halt,
    )

    root = _workspace_root()
    ok, reason = is_fabric_link_green(workspace_root=root)
    return {
        "green": ok,
        "reason": reason,
        "certificate": read_certificate(root),
        "halt": read_halt(root) if is_halt_active(root) else None,
    }

async def fabric_nt_watch() -> dict[str, Any]:
    """Detect NT8 binary changes and re-probe Fabric (fail-closed halt on failure)."""
    from lumina_launcher.services.ninjatrader_watch import check_ninjatrader_update_and_reprobe

    return check_ninjatrader_update_and_reprobe(_workspace_root())

async def configure_setup(body: ConfigureRequest) -> dict[str, Any]:
    setup, config_manager, first_boot, _, hardware, model_service = _services()
    root = _workspace_root()

    missing = scan_missing_credentials(config_manager)
    creds = body.credentials.model_dump()
    for key in ("LUMINA_JWT_SECRET_KEY", "LUMINA_FABRIC_TOKEN"):
        if not str(creds.get(key, "")).strip() and key in missing:
            # process env may satisfy FABRIC token after bootstrap
            if key == "LUMINA_FABRIC_TOKEN" and str(os.getenv("LUMINA_FABRIC_TOKEN", "") or "").strip():
                continue
            if key == "LUMINA_JWT_SECRET_KEY":
                raise HTTPException(status_code=400, detail=f"Missing required credential: {key}")

    snapshot = hardware.get_snapshot(refresh=True)
    steps = persist_tauri_quick_config(
        workspace_root=root,
        setup_service=setup,
        config_manager=config_manager,
        first_boot_manager=first_boot,
        model_service=model_service,
        snapshot=snapshot,
        mode_selection=body.mode,
        credentials=creds,
        risk=body.risk.model_dump(),
        evolution=body.evolution.model_dump(),
        training=body.training.model_dump(),
        selected_model_key=body.selected_model_key,
    )
    failures = [s for s in steps if not s.get("success")]
    return {
        "success": not failures,
        "steps": steps,
        "onboarding": build_onboarding_payload(serving_request=True),
    }

class TauriSigningRequest(BaseModel):
    force: bool = False

async def generate_tauri_signing(body: TauriSigningRequest | None = None) -> dict[str, Any]:
    from lumina_launcher.services.tauri_signing_service import TauriSigningService

    _, config_manager, _, _, _, _ = _services()
    service = TauriSigningService(_workspace_root())
    result = service.generate_keypair(
        config_manager=config_manager,
        force=bool(body.force if body else False),
    )
    payload = result.to_dict()
    if not result.success:
        raise HTTPException(status_code=422, detail=result.message)
    return payload
