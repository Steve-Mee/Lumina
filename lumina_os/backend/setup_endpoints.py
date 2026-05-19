"""FastAPI setup/onboarding endpoints for the Tauri Neural Command Deck."""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lumina_core.engine.setup_service import SetupService
from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.core.onboarding import (
    compute_onboarding_steps,
    extract_config_defaults,
    should_skip_wizard,
)
from lumina_launcher.core.workspace_root import resolve_birth_workspace_root
from lumina_launcher.services.birth_service import birth_service
from lumina_launcher.services.hardware_service import HardwareService
from lumina_launcher.services.model_service import ModelService
from lumina_launcher.services.setup_persist import (
    persist_tauri_quick_config,
    scan_missing_credentials,
)
from lumina_launcher.services.smart_setup_service import SmartSetupOptions, SmartSetupService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["setup"])

_smart_setup_lock = threading.Lock()
_smart_setup_running = False


def _workspace_root() -> Path:
    return resolve_birth_workspace_root(birth_service.workspace_root)


def _services() -> tuple[SetupService, ConfigManager, FirstBootManager, SmartSetupService, HardwareService, ModelService]:
    root = _workspace_root()
    setup = SetupService(
        workspace_root=root,
        config_path=root / "config.yaml",
        env_path=root / ".env",
    )
    config_manager = ConfigManager(root / ".env", root / "config.yaml")
    first_boot = FirstBootManager(root)
    smart = SmartSetupService(root, setup_service=setup)
    hardware = HardwareService(root)
    model = ModelService(root / "lumina_model_catalog.json")
    return setup, config_manager, first_boot, smart, hardware, model


def _probe_backend(base_url: str) -> dict[str, Any]:
    url = base_url.rstrip("/")
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(f"{url}/api/monitoring/health")
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "reachable": response.status_code < 500,
                "url": url,
                "latency_ms": latency_ms,
                "status_code": response.status_code,
            }
    except Exception as exc:
        return {
            "reachable": False,
            "url": url,
            "error": str(exc),
        }


def build_onboarding_payload(*, backend_url: str | None = None, serving_request: bool = False) -> dict[str, Any]:
    setup, config_manager, _, smart, _, _ = _services()
    root = _workspace_root()
    base_url = (backend_url or os.getenv("LUMINA_BACKEND_URL", "http://127.0.0.1:8000")).strip()
    backend = (
        {"reachable": True, "url": base_url, "latency_ms": 0}
        if serving_request
        else _probe_backend(base_url)
    )

    intel_status = smart.get_setup_status()
    intelligence_missing = [
        item for item in intel_status.get("missing", []) if item != "setup_complete"
    ]
    credentials_missing = scan_missing_credentials(config_manager)
    setup_complete = setup.is_setup_complete()
    birth_raw = birth_service.get_status()
    birth_status = str(birth_raw.get("status", "idle"))
    artifacts_ok = birth_service.artifacts_ok()

    global _smart_setup_running
    required_steps, step_status = compute_onboarding_steps(
        backend_reachable=bool(backend.get("reachable")),
        setup_complete=setup_complete,
        intelligence_missing=intelligence_missing,
        credentials_missing=credentials_missing,
        birth_status=birth_status,
        artifacts_ok=artifacts_ok,
        smart_setup_running=_smart_setup_running,
    )

    config = config_manager.load_yaml_config()
    env_values = config_manager.parse_env_file()

    return {
        "backend": backend,
        "setup_complete": setup_complete,
        "skip_wizard": should_skip_wizard(
            setup_complete=setup_complete,
            birth_status=birth_status,
            artifacts_ok=artifacts_ok,
            required_steps=required_steps,
        ),
        "birth": {
            "status": birth_status,
            "message": birth_raw.get("message", ""),
            "progress": birth_raw.get("progress"),
            "artifacts_ok": artifacts_ok,
            "artifacts_label": "Artifacts OK" if artifacts_ok else "Artifacts missing",
        },
        "intelligence": {
            "ollama_installed": bool(intel_status.get("ollama_installed")),
            "ollama_required": bool(intel_status.get("ollama_required")),
            "recommended_model_key": str(intel_status.get("recommended_model_key", "")),
            "recommended_ollama_tag": str(intel_status.get("recommended_ollama_tag", "")),
            "recommended_model_present": bool(intel_status.get("recommended_model_present")),
            "recommended_provider": str(intel_status.get("recommended_provider", "ollama")),
            "hardware": intel_status.get("hardware", {}),
            "adaptive_intelligence": intel_status.get("adaptive_intelligence", {}),
            "missing": intelligence_missing,
        },
        "credentials": {
            "missing": credentials_missing,
            "has_admin_api_key": bool(str(env_values.get("LUMINA_ADMIN_API_KEY", "")).strip()),
        },
        "required_steps": required_steps,
        "step_status": step_status,
        "defaults": extract_config_defaults(config),
        "smart_setup_running": _smart_setup_running,
        "workspace_root": str(root),
    }


@router.get("/onboarding")
async def get_onboarding_status() -> dict[str, Any]:
    return build_onboarding_payload(serving_request=True)


class SmartSetupRequest(BaseModel):
    install_ollama: bool = True
    download_recommended_model: bool = True
    force_high_tier: bool = False
    pull_extra_models: bool = False


@router.post("/smart-setup")
async def start_smart_setup(body: SmartSetupRequest | None = None) -> dict[str, Any]:
    global _smart_setup_running
    opts = body or SmartSetupRequest()
    setup, _, _, smart, _, _ = _services()

    with _smart_setup_lock:
        if _smart_setup_running:
            return {"status": "running", "message": "Smart setup already in progress"}
        _smart_setup_running = True

    def _run() -> None:
        global _smart_setup_running
        try:
            smart.run_smart_setup(
                options=SmartSetupOptions(
                    install_ollama=opts.install_ollama,
                    download_recommended_model=opts.download_recommended_model,
                    force_high_tier=opts.force_high_tier,
                    pull_extra_models=opts.pull_extra_models,
                    graceful_degrade=True,
                ),
                mark_complete=False,
            )
        except Exception as exc:
            logger.exception("smart_setup.background_failed detail=%s", exc)
            setup.save_status({"smart_setup_error": str(exc), "phase": "failed"})
        finally:
            _smart_setup_running = False

    threading.Thread(target=_run, daemon=True, name="lumina-smart-setup").start()
    return {"status": "started", "message": "Smart setup started in background"}


@router.get("/smart-setup/progress")
async def get_smart_setup_progress() -> dict[str, Any]:
    setup, _, _, smart, _, _ = _services()
    status_file = setup.load_status()
    instructions = smart.get_install_instructions()
    return {
        "running": _smart_setup_running,
        "status": status_file,
        "instructions": instructions,
        "intelligence": smart.get_setup_status(),
    }


class ConfigureCredentials(BaseModel):
    LUMINA_JWT_SECRET_KEY: str = ""
    CROSSTRADE_TOKEN: str = ""
    CROSSTRADE_ACCOUNT: str = ""
    LUMINA_ADMIN_API_KEY: str = ""


class ConfigureRisk(BaseModel):
    kelly_fraction: float = Field(default=1.0, ge=0.05, le=1.0)
    daily_loss_cap: float | None = None
    max_total_open_risk: float = Field(default=3000.0, ge=50.0)
    real_capital_safety_threshold_usd: float = Field(default=1000.0, ge=100.0)


class ConfigureEvolution(BaseModel):
    approval_required: bool = True
    aggressive_evolution: bool = False


class ConfigureTraining(BaseModel):
    training_trades: int = Field(default=25000, ge=1000, le=2_000_000)
    prefer_real_data_only: bool = True
    max_real_days: int = Field(default=56, ge=30, le=3650)
    allow_minimal_synthetic_fallback: bool = False
    require_real_simulator_data: bool = True


class ConfigureRequest(BaseModel):
    mode: str = "sim"
    credentials: ConfigureCredentials = Field(default_factory=ConfigureCredentials)
    risk: ConfigureRisk = Field(default_factory=ConfigureRisk)
    evolution: ConfigureEvolution = Field(default_factory=ConfigureEvolution)
    training: ConfigureTraining = Field(default_factory=ConfigureTraining)
    selected_model_key: str | None = None


@router.post("/configure")
async def configure_setup(body: ConfigureRequest) -> dict[str, Any]:
    setup, config_manager, first_boot, _, hardware, model_service = _services()
    root = _workspace_root()

    missing = scan_missing_credentials(config_manager)
    creds = body.credentials.model_dump()
    for key in ("LUMINA_JWT_SECRET_KEY", "CROSSTRADE_TOKEN", "CROSSTRADE_ACCOUNT"):
        if not str(creds.get(key, "")).strip() and key in missing:
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
