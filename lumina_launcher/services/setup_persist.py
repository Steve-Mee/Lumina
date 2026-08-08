"""Shared setup persistence helpers (Streamlit wizard + Tauri onboarding).

Split (Wave D): setup_persist_{mode,config,tauri,fabric,credentials,sim}.
"""
from __future__ import annotations

from lumina_launcher.services.setup_persist_config import persist_setup_configuration
from lumina_launcher.services.setup_persist_credentials import (
    CREDENTIAL_ENV_KEYS,
    build_credentials_env_snapshot,
    persist_credentials_only,
    scan_missing_credentials,
)
from lumina_launcher.services.setup_persist_fabric import (
    DEFAULT_FABRIC_JSON,
    apply_fabric_token_side_effects,
    fabric_json_path,
    generate_fabric_token,
    set_user_environment_variable,
    write_fabric_json_defaults,
)
from lumina_launcher.services.setup_persist_mode import resolve_mode_matrix
from lumina_launcher.services.setup_persist_sim import (
    SIM_ENVELOPE_SEALED_FILENAME,
    is_sim_envelope_sealed,
    seed_sim_runtime_and_mark_setup,
    sim_envelope_sealed_path,
    write_sim_envelope_sealed,
)
from lumina_launcher.services.setup_persist_tauri import persist_tauri_quick_config

# Private helper used by config module — re-export for tests
from lumina_launcher.services.setup_persist_mode import _ensure_mapping  # noqa: F401

__all__ = [
    "CREDENTIAL_ENV_KEYS",
    "DEFAULT_FABRIC_JSON",
    "SIM_ENVELOPE_SEALED_FILENAME",
    "apply_fabric_token_side_effects",
    "build_credentials_env_snapshot",
    "fabric_json_path",
    "generate_fabric_token",
    "is_sim_envelope_sealed",
    "persist_credentials_only",
    "persist_setup_configuration",
    "persist_tauri_quick_config",
    "resolve_mode_matrix",
    "scan_missing_credentials",
    "seed_sim_runtime_and_mark_setup",
    "set_user_environment_variable",
    "sim_envelope_sealed_path",
    "write_fabric_json_defaults",
    "write_sim_envelope_sealed",
]
