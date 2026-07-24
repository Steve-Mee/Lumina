"""FastAPI setup/onboarding endpoints for the Tauri Neural Command Deck."""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from lumina_core.engine.setup_service import SetupService
from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.core.onboarding import (
    compute_onboarding_steps,
    extract_config_defaults,
    resolve_app_surface,
    resolve_credentials_wizard_meta,
    resolve_wizard_steps,
    should_skip_wizard,
)
from lumina_launcher.core.workspace_root import resolve_birth_workspace_root
from lumina_launcher.services.birth_service import birth_service
from lumina_launcher.services.hardware_service import HardwareService
from lumina_launcher.services.model_service import ModelService
from lumina_launcher.services.setup_persist import (
    build_credentials_env_snapshot,
    is_sim_envelope_sealed,
    persist_credentials_only,
    persist_tauri_quick_config,
    scan_missing_credentials,
    seed_sim_runtime_and_mark_setup,
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


def _model_catalog_payload(hardware: HardwareService, model_service: ModelService) -> list[dict[str, Any]]:
    snapshot = hardware.get_snapshot()
    recommended = model_service.get_recommended(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    catalog: list[dict[str, Any]] = []
    for descriptor in model_service.get_all_models():
        if descriptor.recommended_provider != "ollama" or not descriptor.tested_by_lumina:
            continue
        catalog.append(
            {
                "key": descriptor.key,
                "display_name": descriptor.display_name,
                "ollama_tag": descriptor.ollama_tag,
                "recommended_tier": descriptor.recommended_tier,
                "parameter_size_b": descriptor.parameter_size_b,
                "fits_hardware": hardware.fits_hardware(descriptor),
                "is_recommended": descriptor.key == recommended.key,
            }
        )
    catalog.sort(key=lambda item: (not item["is_recommended"], item["display_name"]))
    return catalog


def _readiness_summary(
    *,
    backend: dict[str, Any],
    intelligence: dict[str, Any],
    credentials_missing: list[str],
    setup_complete: bool,
    birth_status: str,
    artifacts_ok: bool,
    certificate_ok: bool | None = None,
) -> list[dict[str, str]]:
    birth_ready = certificate_ok if certificate_ok is not None else artifacts_ok
    intel_missing = [item for item in intelligence.get("missing", []) if item != "setup_complete"]
    rows = [
        {
            "id": "backend",
            "label": "Python backend",
            "status": "ok" if backend.get("reachable") else "missing",
        },
        {
            "id": "ollama",
            "label": "Ollama runtime",
            "status": "ok" if intelligence.get("ollama_installed") else "missing",
        },
        {
            "id": "model",
            "label": "Trading model",
            "status": "ok" if intelligence.get("recommended_model_present") else "missing",
        },
        {
            "id": "credentials",
            "label": "API credentials",
            "status": "ok" if not credentials_missing else "missing",
        },
        {
            "id": "configuration",
            "label": "Risk envelope (post-birth)",
            "status": "ok" if setup_complete else "pending",
        },
        {
            "id": "birth",
            "label": "Birth Phase",
            "status": "ok" if birth_ready or birth_status == "running" else "pending",
        },
    ]
    if intel_missing and rows[1]["status"] == "ok" and rows[2]["status"] == "ok":
        pass
    return rows


def build_onboarding_payload(*, backend_url: str | None = None, serving_request: bool = False) -> dict[str, Any]:
    setup, config_manager, _, smart, hardware, model_service = _services()
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
    certificate_ok = birth_service.certificate_ok()
    from lumina_core.birth.birth_certificate import validate_certificate_artifacts
    from lumina_core.birth.config import load_birth_v2_config

    thresholds = load_birth_v2_config(_workspace_root()).certificate_thresholds
    _cert_valid, certificate_reason, _cert = validate_certificate_artifacts(
        _workspace_root(),
        thresholds=thresholds,
    )

    global _smart_setup_running
    required_steps, step_status = compute_onboarding_steps(
        backend_reachable=bool(backend.get("reachable")),
        setup_complete=setup_complete,
        intelligence_missing=intelligence_missing,
        credentials_missing=credentials_missing,
        birth_status=birth_status,
        artifacts_ok=artifacts_ok,
        certificate_ok=certificate_ok,
        smart_setup_running=_smart_setup_running,
    )

    config = config_manager.load_yaml_config()
    env_values = config_manager.parse_env_file()
    creds_snapshot = build_credentials_env_snapshot(config_manager)
    credentials_meta = resolve_credentials_wizard_meta(
        credentials_missing=credentials_missing,
        setup_complete=setup_complete,
    )
    intelligence_payload = {
        "ollama_installed": bool(intel_status.get("ollama_installed")),
        "ollama_required": bool(intel_status.get("ollama_required")),
        "recommended_model_key": str(intel_status.get("recommended_model_key", "")),
        "recommended_ollama_tag": str(intel_status.get("recommended_ollama_tag", "")),
        "recommended_model_present": bool(intel_status.get("recommended_model_present")),
        "recommended_provider": str(intel_status.get("recommended_provider", "ollama")),
        "hardware": intel_status.get("hardware", {}),
        "adaptive_intelligence": intel_status.get("adaptive_intelligence", {}),
        "missing": intelligence_missing,
    }
    wizard_steps = resolve_wizard_steps(required_steps)
    backend_reachable = bool(backend.get("reachable"))
    app_surface, app_surface_reason = resolve_app_surface(
        setup_complete=setup_complete,
        birth_status=birth_status,
        artifacts_ok=artifacts_ok,
        certificate_ok=certificate_ok,
        backend_reachable=backend_reachable,
        required_steps=required_steps,
    )

    return {
        "backend": backend,
        "setup_complete": setup_complete,
        "app_surface": app_surface,
        "app_surface_reason": app_surface_reason,
        "skip_wizard": should_skip_wizard(
            setup_complete=setup_complete,
            birth_status=birth_status,
            artifacts_ok=artifacts_ok,
            certificate_ok=certificate_ok,
            required_steps=required_steps,
            backend_reachable=backend_reachable,
        ),
        "birth": {
            "status": birth_status,
            "message": birth_raw.get("message", ""),
            "progress": birth_raw.get("progress"),
            "artifacts_ok": artifacts_ok,
            "artifacts_label": "Artifacts OK" if artifacts_ok else "Artifacts missing",
            "certificate_ok": certificate_ok,
            "certificate_reason": certificate_reason,
            "evolution_proof_ok": birth_service.evolution_proof_ok(),
            "real_trading_eligible": birth_service.real_trading_eligible(),
        },
        "intelligence": intelligence_payload,
        "model_catalog": _model_catalog_payload(hardware, model_service),
        "readiness": _readiness_summary(
            backend=backend,
            intelligence=intelligence_payload,
            credentials_missing=credentials_missing,
            setup_complete=setup_complete,
            birth_status=birth_status,
            artifacts_ok=artifacts_ok,
            certificate_ok=certificate_ok,
        ),
        "credentials": {
            "missing": credentials_missing,
            "has_admin_api_key": bool(str(env_values.get("LUMINA_ADMIN_API_KEY", "")).strip()),
            "env_path": creds_snapshot["env_path"],
            "present": creds_snapshot["present"],
            "wizard_required": credentials_meta["wizard_required"],
            "skip_reason": credentials_meta["skip_reason"],
        },
        "required_steps": required_steps,
        "wizard_steps": wizard_steps,
        "step_status": step_status,
        "defaults": extract_config_defaults(config, env_values=env_values),
        "smart_setup_running": _smart_setup_running,
        "sim_envelope_sealed": is_sim_envelope_sealed(root),
        "workspace_root": str(root),
    }


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
    return build_onboarding_payload(serving_request=True)


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


class FabricConnectionTestRequest(BaseModel):
    include_safe_mode: bool = True
    instrument: str = Field(default="MES", min_length=1, max_length=32)


@router.post("/fabric-connection-test")
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


@router.post("/fabric-bootstrap")
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


@router.get("/fabric-link-status")
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


@router.post("/fabric-nt-watch")
async def fabric_nt_watch() -> dict[str, Any]:
    """Detect NT8 binary changes and re-probe Fabric (fail-closed halt on failure)."""
    from lumina_launcher.services.ninjatrader_watch import check_ninjatrader_update_and_reprobe

    return check_ninjatrader_update_and_reprobe(_workspace_root())


@router.post("/configure")
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


@router.post("/tauri-signing/generate")
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
