"""Meta-agent evolution configuration helpers."""

from __future__ import annotations

import os
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError

def should_run_multi_gen_nightly(*, mutation_allowed: bool, dry_run: bool, mode_key: str) -> bool:
    """True when the closed-loop multi-gen cycle (incl. dream) should run.

    Nightly sim/paper often pass dry_run True to protect live side-effects; we still
    run this cycle in those modes so dream/SIM evolution paths execute.
    """
    mk = str(mode_key).strip().lower()
    return bool(mutation_allowed and (not dry_run or mk in ("sim", "paper")))


def load_evolution_config(config_path: str = "config.yaml") -> dict[str, Any]:
    import yaml

    if not os.path.exists(config_path):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_CONFIG_FILE_MISSING",
            message=f"Required evolution config file not found: {config_path}",
        )

    with open(config_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_CONFIG_INVALID",
            message="Top-level config.yaml payload must be a mapping.",
        )

    evo = data.get("evolution")
    fine_tuning = data.get("fine_tuning")
    sim_cfg = data.get("sim")
    real_cfg = data.get("real")
    if not isinstance(evo, dict) or not isinstance(fine_tuning, dict):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_CONFIG_SECTIONS_MISSING",
            message="Config requires 'evolution' and 'fine_tuning' mapping sections.",
        )
    if not isinstance(sim_cfg, dict) or not isinstance(real_cfg, dict):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_MODE_CONFIG_MISSING",
            message="Config requires both 'sim' and 'real' mapping sections.",
        )

    mode = str(os.getenv("LUMINA_MODE", data["mode"]))
    mode = mode.strip().lower()
    if mode not in {"sim", "paper", "real"}:
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_MODE_INVALID",
            message=f"Unsupported mode in evolution config: {mode}",
        )

    mode_cfg = sim_cfg if mode == "sim" else real_cfg
    return {
        "enabled": bool(evo["enabled"]),
        "approval_required": bool(mode_cfg["approval_required"]),
        "mode": mode,
        "aggressive_evolution": bool(mode_cfg["aggressive_evolution"]),
        "max_mutation_depth": str(mode_cfg["max_mutation_depth"]),
        "fine_tuning": {
            "auto_trigger": bool(fine_tuning["auto_trigger"]),
            "min_acceptance": float(fine_tuning["min_acceptance"]),
            "drift_threshold": float(fine_tuning["drift_threshold"]),
        },
    }
