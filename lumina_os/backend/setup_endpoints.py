"""FastAPI setup/onboarding endpoints for the Tauri Neural Command Deck."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from lumina_launcher.services.setup_persist import (
    build_credentials_env_snapshot,
    persist_credentials_only,
    scan_missing_credentials,
    seed_sim_runtime_and_mark_setup,
)
from lumina_launcher.services.birth_service import birth_service
from lumina_launcher.services.smart_setup_service import SmartSetupOptions

from lumina_launcher.core.onboarding import resolve_app_surface
from .setup_onboarding_payload import (
    _model_catalog_payload,
    _probe_backend,
    _readiness_summary,
    _services,
    _workspace_root,
    build_onboarding_payload,
)

logger = logging.getLogger(__name__)

__all__ = [
    "birth_service",
    "build_onboarding_payload",
    "resolve_app_surface",
    "router",
    "_probe_backend",
    "_services",
    "_workspace_root",
    "_model_catalog_payload",
    "_readiness_summary",
]

router = APIRouter(prefix="/api/setup", tags=["setup"])

_smart_setup_lock = threading.Lock()
_smart_setup_running = False


def _is_loopback_client(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    host = (client.host or "").strip().lower()
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


@router.get("/deck-credentials-prefill")
async def get_deck_credentials_prefill(request: Request) -> dict[str, Any]:
    """Expose .env credential values to local Tauri deck only (Streamlit wizard parity)."""
    if not _is_loopback_client(request):
        raise HTTPException(status_code=403, detail="Localhost clients only")
    _, config_manager, _, _, _, _ = _services()
    return build_credentials_env_snapshot(config_manager)


@router.get("/deck-api-key")
async def get_deck_api_key(request: Request) -> dict[str, Any]:
    """Expose admin API key to local Tauri deck only (Streamlit .env parity)."""
    if not _is_loopback_client(request):
        raise HTTPException(status_code=403, detail="Localhost clients only")
    _, config_manager, _, _, _, _ = _services()
    env_values = config_manager.parse_env_file()
    api_key = str(env_values.get("LUMINA_ADMIN_API_KEY", "")).strip()
    if not api_key:
        return {"configured": False}
    return {"configured": True, "api_key": api_key}


@router.get("/onboarding")
async def get_onboarding_status() -> dict[str, Any]:
    # Payload builds birth status + hardware probes — never block the event loop.
    return await asyncio.to_thread(build_onboarding_payload, serving_request=True)


class SmartSetupRequest(BaseModel):
    install_ollama: bool = True
    download_recommended_model: bool = True
    force_high_tier: bool = False
    pull_extra_models: bool = False
    selected_model_key: str | None = None


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
            _, _, _, _, hardware, model_service = _services()
            result = smart.run_smart_setup(
                options=SmartSetupOptions(
                    install_ollama=opts.install_ollama,
                    download_recommended_model=opts.download_recommended_model,
                    force_high_tier=opts.force_high_tier,
                    pull_extra_models=opts.pull_extra_models,
                    graceful_degrade=True,
                ),
                mark_complete=False,
            )
            if opts.selected_model_key and result.success:
                selected = model_service.get_model(opts.selected_model_key)
                recommended_key = str(
                    smart.get_setup_status().get("recommended_model_key", "")
                )
                if selected and selected.key != recommended_key:
                    snapshot = hardware.get_snapshot()
                    pull_step = setup.pull_model(selected)
                    if pull_step.success:
                        setup.apply_recommended_config(hardware=snapshot, model=selected)
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


@router.post("/ready-for-birth")
async def ready_for_birth() -> dict[str, Any]:
    """Mark setup complete with SIM defaults when Vault credentials are already present.

    Used when the credentials wizard is skipped (env already configured) so operators
    can enter Birth without the pre-birth Risk Envelope step.
    """

    def _run() -> dict[str, Any]:
        setup, config_manager, first_boot, _, hardware, model_service = _services()
        missing = scan_missing_credentials(config_manager)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Vault incomplete — missing: {', '.join(missing)}",
            )
        snapshot = hardware.get_snapshot(refresh=True)
        steps = seed_sim_runtime_and_mark_setup(
            workspace_root=_workspace_root(),
            setup_service=setup,
            config_manager=config_manager,
            first_boot_manager=first_boot,
            model_service=model_service,
            snapshot=snapshot,
            force_envelope_unsealed=True,
        )
        return {
            "success": True,
            "steps": steps,
            "onboarding": build_onboarding_payload(serving_request=True),
        }

    return await asyncio.to_thread(_run)


@router.post("/credentials")
async def save_credentials(body: ConfigureCredentials) -> dict[str, Any]:
    setup, config_manager, first_boot, _, hardware, model_service = _services()
    creds = body.model_dump()
    # Fabric-first: JWT required; Crosstrade optional emergency feed.
    if not str(creds.get("LUMINA_JWT_SECRET_KEY", "")).strip():
        raise HTTPException(status_code=400, detail="Missing required credential: LUMINA_JWT_SECRET_KEY")
    still_missing = persist_credentials_only(config_manager, creds)
    seed_steps: list[dict[str, Any]] = []
    if not still_missing:
        snapshot = hardware.get_snapshot(refresh=True)
        seed_steps = seed_sim_runtime_and_mark_setup(
            workspace_root=_workspace_root(),
            setup_service=setup,
            config_manager=config_manager,
            first_boot_manager=first_boot,
            model_service=model_service,
            snapshot=snapshot,
            force_envelope_unsealed=True,
        )
    return {
        "success": not still_missing,
        "missing": still_missing,
        "seed_steps": seed_steps,
        "onboarding": build_onboarding_payload(serving_request=True),
    }




from lumina_os.backend.setup_endpoints_fabric import (  # noqa: E402
    configure_setup,
    fabric_bootstrap,
    fabric_connection_test,
    fabric_link_status,
    fabric_nt_watch,
    generate_tauri_signing,
)

fabric_connection_test = router.post("/fabric-connection-test")(fabric_connection_test)
fabric_bootstrap = router.post("/fabric-bootstrap")(fabric_bootstrap)
fabric_link_status = router.get("/fabric-link-status")(fabric_link_status)
fabric_nt_watch = router.post("/fabric-nt-watch")(fabric_nt_watch)
configure_setup = router.post("/configure")(configure_setup)
generate_tauri_signing = router.post("/tauri-signing/generate")(generate_tauri_signing)
