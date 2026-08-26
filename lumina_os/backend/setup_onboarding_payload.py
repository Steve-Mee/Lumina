"""Onboarding payload builders extracted from setup_endpoints."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

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
from lumina_launcher.services.birth_service import birth_service as _default_birth_service
from lumina_launcher.services.hardware_service import HardwareService
from lumina_launcher.services.model_service import ModelService
from lumina_launcher.services.setup_persist import (
    build_credentials_env_snapshot,
    is_sim_envelope_sealed,
    scan_missing_credentials,
)
from lumina_launcher.services.smart_setup_service import SmartSetupService

logger = logging.getLogger(__name__)


def _setup_endpoints_mod() -> Any | None:
    import sys

    return sys.modules.get("backend.setup_endpoints")


def _resolve_birth_service() -> Any:
    """Prefer ``backend.setup_endpoints.birth_service`` when patched by tests."""
    mod = _setup_endpoints_mod()
    if mod is not None:
        patched = getattr(mod, "birth_service", None)
        if patched is not None:
            return patched
    return _default_birth_service


def _workspace_root() -> Path:
    return resolve_birth_workspace_root(_resolve_birth_service().workspace_root)


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
    birth_exit_ok: bool | None = None,
    twin_base_ready: bool | None = None,
) -> list[dict[str, str]]:
    birth_ready = bool(birth_exit_ok)
    _ = artifacts_ok
    _ = certificate_ok
    intel_missing = [item for item in intelligence.get("missing", []) if item != "setup_complete"]
    if twin_base_ready is None:
        try:
            from lumina_core.evolution.twin_base_training import is_twin_birth_ready

            twin_base_ready = bool(is_twin_birth_ready())
        except Exception:
            twin_base_ready = False
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
            "id": "twin_base",
            "label": "Twin base training",
            "status": "ok" if twin_base_ready else "missing",
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
    _ep = _setup_endpoints_mod()
    _svc = getattr(_ep, "_services", _services) if _ep is not None else _services
    _root_fn = getattr(_ep, "_workspace_root", _workspace_root) if _ep is not None else _workspace_root
    setup, config_manager, _, smart, hardware, model_service = _svc()
    root = _root_fn()
    base_url = (backend_url or os.getenv("LUMINA_BACKEND_URL", "http://127.0.0.1:8000")).strip()
    _probe = getattr(_ep, "_probe_backend", _probe_backend) if _ep is not None else _probe_backend
    backend = (
        {"reachable": True, "url": base_url, "latency_ms": 0}
        if serving_request
        else _probe(base_url)
    )

    intel_status = smart.get_setup_status()
    intelligence_missing = [
        item for item in intel_status.get("missing", []) if item != "setup_complete"
    ]
    credentials_missing = scan_missing_credentials(config_manager)
    setup_complete = setup.is_setup_complete()
    _birth = _resolve_birth_service()
    birth_raw = _birth.get_status()
    if not isinstance(birth_raw, dict):
        birth_raw = {}
    birth_status = str(birth_raw.get("status", "idle"))
    artifacts_ok = _birth.artifacts_ok()
    certificate_ok = _birth.certificate_ok()
    from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

    birth_exit_ok = bool(is_birth_exit_sufficient(_workspace_root()))
    from lumina_core.birth.birth_certificate import validate_certificate_artifacts
    from lumina_core.birth.config import load_birth_v2_config

    thresholds = load_birth_v2_config(_workspace_root()).certificate_thresholds
    _cert_valid, certificate_reason, _cert = validate_certificate_artifacts(
        _workspace_root(),
        thresholds=thresholds,
    )

    # Prefer setup_endpoints flag when that module is loaded (tests may patch it).
    import sys

    _ep = sys.modules.get("backend.setup_endpoints")
    smart_setup_running = bool(getattr(_ep, "_smart_setup_running", False)) if _ep else False
    required_steps, step_status = compute_onboarding_steps(
        backend_reachable=bool(backend.get("reachable")),
        setup_complete=setup_complete,
        intelligence_missing=intelligence_missing,
        credentials_missing=credentials_missing,
        birth_status=birth_status,
        artifacts_ok=artifacts_ok,
        certificate_ok=certificate_ok,
        birth_exit_ok=birth_exit_ok,
        smart_setup_running=smart_setup_running,
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
        birth_exit_ok=birth_exit_ok,
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
            birth_exit_ok=birth_exit_ok,
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
            "birth_exit_ok": birth_exit_ok,
            "certificate_reason": certificate_reason,
            "evolution_proof_ok": _birth.evolution_proof_ok(),
            "real_trading_eligible": _birth.real_trading_eligible(),
        },
        "intelligence": intelligence_payload,
        "model_catalog": (
            getattr(_ep, "_model_catalog_payload", _model_catalog_payload)(hardware, model_service)
            if _ep is not None
            else _model_catalog_payload(hardware, model_service)
        ),
        "readiness": _readiness_summary(
            backend=backend,
            intelligence=intelligence_payload,
            credentials_missing=credentials_missing,
            setup_complete=setup_complete,
            birth_status=birth_status,
            artifacts_ok=artifacts_ok,
            certificate_ok=certificate_ok,
            birth_exit_ok=birth_exit_ok,
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
        "smart_setup_running": smart_setup_running,
        "sim_envelope_sealed": is_sim_envelope_sealed(root),
        "workspace_root": str(root),
        "twin": _twin_foundation_payload(),
    }


def _twin_foundation_payload() -> dict[str, Any]:
    """Operator Vault foundation: Twin base curriculum status (ADR-0037)."""
    try:
        from lumina_core.evolution.twin_base_training import is_twin_birth_ready, load_birth_readiness

        ready = bool(is_twin_birth_ready())
        raw = load_birth_readiness()
        return {
            "birth_ready": ready,
            "base_trained": ready or bool(raw.get("base_trained")),
            "base_training_completion_pct": 100.0 if ready else 0.0,
            "curriculum_version": raw.get("curriculum_version"),
            "local_only": True,
        }
    except Exception:
        return {
            "birth_ready": False,
            "base_trained": False,
            "base_training_completion_pct": 0.0,
            "local_only": True,
        }


