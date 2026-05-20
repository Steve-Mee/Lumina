"""Post-birth bot configuration persistence (YAML-only, no env mode reset)."""

from __future__ import annotations

from typing import Any

from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.services.setup_persist import _ensure_mapping, resolve_mode_matrix

MUTATION_DEPTHS = frozenset({"conservative", "moderate", "radical"})


def validate_bot_config(mode: str, evolution: dict[str, Any]) -> None:
    mode_value = str(mode or "sim").strip().lower()
    depth = str(evolution.get("max_mutation_depth", "conservative")).strip().lower()
    if depth not in MUTATION_DEPTHS:
        raise ValueError(f"Invalid max_mutation_depth: {depth}")
    if mode_value == "real" and depth == "radical":
        raise ValueError("REAL mode cannot use radical mutation depth (constitution enforced)")


def persist_bot_config(
    *,
    config_manager: ConfigManager,
    mode_selection: str,
    risk: dict[str, Any],
    evolution: dict[str, Any],
    preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update config.yaml bot settings without touching .env runtime mode."""
    validate_bot_config(mode_selection, evolution)

    mode_value, broker_backend = resolve_mode_matrix(mode_selection)
    if mode_value not in {"sim", "real"}:
        mode_value = "sim"

    config_payload = config_manager.load_yaml_config()
    config_payload["mode"] = mode_value
    broker = _ensure_mapping(config_payload, "broker")
    broker["backend"] = broker_backend

    prefs = preferences or {}
    env_updates: dict[str, str] = {}
    if "instrument" in prefs:
        env_updates["INSTRUMENT"] = str(prefs["instrument"]).strip().upper()
    if "voice_enabled" in prefs:
        env_updates["VOICE_ENABLED"] = str(bool(prefs["voice_enabled"])).lower()
    if "screen_share_enabled" in prefs:
        env_updates["SCREEN_SHARE_ENABLED"] = str(bool(prefs["screen_share_enabled"])).lower()
    if "dashboard_enabled" in prefs:
        env_updates["DASHBOARD_ENABLED"] = str(bool(prefs["dashboard_enabled"])).lower()
    if "runtime_trace" in prefs:
        env_updates["LUMINA_RUNTIME_TRACE"] = str(bool(prefs["runtime_trace"])).lower()
    if "runtime_trace_interval_sec" in prefs:
        env_updates["LUMINA_RUNTIME_TRACE_INTERVAL_SEC"] = str(
            int(prefs["runtime_trace_interval_sec"])
        )
    if "latency_sla_ms" in prefs:
        env_updates["LUMINA_LATENCY_SLA_MS"] = str(int(prefs["latency_sla_ms"]))
    if env_updates:
        config_manager.write_env_file(env_updates)

    mode_section = _ensure_mapping(config_payload, mode_value)
    if "kelly_fraction" in risk:
        mode_section["kelly_fraction"] = float(risk["kelly_fraction"])
    if "daily_loss_cap" in risk and risk["daily_loss_cap"] is not None:
        mode_section["daily_loss_cap"] = float(risk["daily_loss_cap"])
    elif "daily_loss_cap" in risk and risk["daily_loss_cap"] is None:
        mode_section["daily_loss_cap"] = None
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
        risk_controller["real_capital_safety_threshold_usd"] = float(
            risk["real_capital_safety_threshold_usd"]
        )
    if "max_total_open_risk" in risk:
        risk_controller["max_total_open_risk"] = float(risk["max_total_open_risk"])

    evolution_section = _ensure_mapping(config_payload, "evolution")
    if "approval_required" in evolution:
        evolution_section["approval_required"] = bool(evolution["approval_required"])

    config_manager.save_yaml_config(config_payload)
    return config_payload
