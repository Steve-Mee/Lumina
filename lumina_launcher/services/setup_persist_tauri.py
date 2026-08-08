"""Tauri quick-config persistence."""
from __future__ import annotations

import json
import logging
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.hardware_inspector import HardwareSnapshot
from lumina_core.engine.setup_service import SetupService
from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.model_service import ModelService

logger = logging.getLogger(__name__)

from lumina_launcher.services.setup_persist_mode import resolve_mode_matrix, _ensure_mapping  # noqa: E402
from lumina_launcher.services.setup_persist_sim import (  # noqa: E402
    is_sim_envelope_sealed,
    sim_envelope_sealed_path,
    write_sim_envelope_sealed,
)


def persist_tauri_quick_config(
    *,
    workspace_root: Path,
    setup_service: SetupService,
    config_manager: ConfigManager,
    first_boot_manager: FirstBootManager,
    model_service: ModelService,
    snapshot: HardwareSnapshot,
    mode_selection: str,
    credentials: dict[str, str],
    risk: dict[str, Any],
    evolution: dict[str, Any],
    training: dict[str, Any],
    selected_model_key: str | None = None,
) -> list[dict[str, Any]]:
    """Streamlined configure path for the Tauri onboarding wizard."""
    mode_value, broker_backend = resolve_mode_matrix(mode_selection)
    birth_mode_value, birth_backend = resolve_mode_matrix("sim")
    admin_api_key = str(credentials.get("LUMINA_ADMIN_API_KEY", "")).strip() or f"sk_{secrets.token_hex(32)}"

    env_updates: dict[str, str] = {
        "TRADE_MODE": birth_mode_value,
        "LUMINA_MODE": birth_mode_value,
        "BROKER_BACKEND": birth_backend,
        "LUMINA_ADMIN_API_KEY": admin_api_key,
    }
    for key in (
        "CROSSTRADE_TOKEN",
        "CROSSTRADE_ACCOUNT",
        "LUMINA_JWT_SECRET_KEY",
    ):
        value = str(credentials.get(key, "")).strip()
        if value:
            env_updates[key] = value

    steps: list[dict[str, Any]] = []
    config_manager.write_env_file(env_updates)
    steps.append({"name": "env_update", "success": True, "message": "Environment values written"})

    config_payload = config_manager.load_yaml_config()
    config_payload["mode"] = mode_value
    broker = _ensure_mapping(config_payload, "broker")
    broker["backend"] = broker_backend

    mode_section = _ensure_mapping(config_payload, mode_value if mode_value in {"sim", "real"} else "sim")
    if "kelly_fraction" in risk:
        mode_section["kelly_fraction"] = float(risk["kelly_fraction"])
    if "daily_loss_cap" in risk and risk["daily_loss_cap"] is not None:
        mode_section["daily_loss_cap"] = float(risk["daily_loss_cap"])
    if "max_total_open_risk" in risk:
        mode_section["max_total_open_risk"] = float(risk["max_total_open_risk"])
    if "aggressive_evolution" in evolution:
        mode_section["aggressive_evolution"] = bool(evolution["aggressive_evolution"])
    if "approval_required" in evolution:
        mode_section["approval_required"] = bool(evolution["approval_required"])
    if "max_mutation_depth" in evolution:
        mode_section["max_mutation_depth"] = str(evolution["max_mutation_depth"]).strip().lower()

    risk_controller = _ensure_mapping(config_payload, "risk_controller")
    if "real_capital_safety_threshold_usd" in risk:
        risk_controller["real_capital_safety_threshold_usd"] = float(risk["real_capital_safety_threshold_usd"])
    if "max_total_open_risk" in risk:
        risk_controller["max_total_open_risk"] = float(risk["max_total_open_risk"])

    evolution_section = _ensure_mapping(config_payload, "evolution")
    if "approval_required" in evolution:
        evolution_section["approval_required"] = bool(evolution["approval_required"])

    config_manager.save_yaml_config(config_payload)
    steps.append({"name": "runtime_mode", "success": True, "message": f"Mode and risk config saved ({mode_value})"})

    gate_raw = training.get("stage1_winrate_pass_threshold")
    gate_threshold = float(gate_raw) if gate_raw is not None else None
    first_boot_manager.save_full_settings(
        training_trades=int(training["training_trades"]),
        prefer_real_data_only=bool(training.get("prefer_real_data_only", True)),
        max_real_days=int(training.get("max_real_days", 56)),
        allow_minimal_synthetic_fallback=bool(training.get("allow_minimal_synthetic_fallback", False)),
        require_real_simulator_data=bool(training.get("require_real_simulator_data", True)),
        stage1_winrate_pass_threshold=gate_threshold,
        mark_user_configured=True,
    )
    steps.append({"name": "first_boot_config", "success": True, "message": "Birth training settings saved"})
    try:
        from lumina_core.maturity.milestone_hooks import try_record_milestone

        try_record_milestone(workspace_root, "genesis_contract_signed")
    except Exception:
        pass

    recommended = model_service.get_recommended(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    model_key = selected_model_key or recommended.key
    model = model_service.get_model(model_key) or recommended
    model_result = setup_service.apply_recommended_config(hardware=snapshot, model=model)
    steps.append(model_result.to_dict())
    model_service.save_state(workspace_root / "state" / "model_catalog_state.json", model.key)

    ConfigLoader.invalidate()
    setup_service.save_status(
        {
            "steps": steps,
            "selected_mode": mode_value,
            "selected_model": model.key,
            "hardware_tier": getattr(snapshot, "profile_tier", "unknown"),
            "source": "tauri_onboarding",
        }
    )

    required = {"env_update", "runtime_mode", "first_boot_config", "config_update"}
    ok_names = {step.get("name") for step in steps if step.get("success")}
    if required.issubset(ok_names):
        setup_service.mark_complete(hardware=snapshot, model=model)
        # Defer Playground Risk Envelope seal unless operator already sealed.
        seal_path = sim_envelope_sealed_path(workspace_root)
        if not seal_path.is_file() or not is_sim_envelope_sealed(workspace_root):
            write_sim_envelope_sealed(
                workspace_root, sealed=False, source="tauri_quick_config"
            )
    return steps


