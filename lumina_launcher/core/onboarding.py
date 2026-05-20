"""Onboarding gate computation for Tauri Neural Command Deck."""

from __future__ import annotations

from typing import Any, Literal

OnboardingStepId = Literal[
    "welcome",
    "backend",
    "ollama",
    "model",
    "credentials",
    "configuration",
    "birth",
]

StepStatus = Literal["pending", "done", "running", "blocked"]


def compute_onboarding_steps(
    *,
    backend_reachable: bool,
    setup_complete: bool,
    intelligence_missing: list[str],
    credentials_missing: list[str],
    birth_status: str,
    artifacts_ok: bool,
    smart_setup_running: bool = False,
) -> tuple[list[OnboardingStepId], dict[str, StepStatus]]:
    """Return required wizard steps and per-step status."""
    step_status: dict[str, StepStatus] = {
        "welcome": "pending",
        "backend": "done" if backend_reachable else "pending",
        "ollama": "done",
        "model": "done",
        "credentials": "done",
        "configuration": "done" if setup_complete else "pending",
        "birth": "done",
    }

    required: list[OnboardingStepId] = ["welcome"]

    if not backend_reachable:
        required.append("backend")
        step_status["backend"] = "pending"
    else:
        step_status["backend"] = "done"

    if "ollama" in intelligence_missing:
        required.append("ollama")
        step_status["ollama"] = "running" if smart_setup_running else "pending"
    if any(item.startswith("model:") for item in intelligence_missing):
        if "ollama" not in required:
            required.append("model")
        step_status["model"] = "running" if smart_setup_running else "pending"

    if credentials_missing and not setup_complete:
        required.append("credentials")
        step_status["credentials"] = "pending"

    if not setup_complete:
        required.append("configuration")
        step_status["configuration"] = "pending"

    birth_idle = birth_status in {"idle", "not_started", "", "interrupted", "error"}
    if setup_complete and birth_idle and not artifacts_ok:
        required.append("birth")
        step_status["birth"] = "pending"
    elif birth_status == "running":
        step_status["birth"] = "running"
    elif artifacts_ok or birth_status in {"completed", "error"}:
        step_status["birth"] = "done"

    return required, step_status


def resolve_credentials_wizard_meta(
    *,
    credentials_missing: list[str],
    setup_complete: bool,
) -> dict[str, Any]:
    """Whether the deck must show the credentials step and why it was skipped."""
    wizard_required = bool(credentials_missing and not setup_complete)
    if wizard_required:
        skip_reason = None
    elif setup_complete:
        skip_reason = "setup_complete"
    else:
        skip_reason = "env_configured"
    return {
        "wizard_required": wizard_required,
        "skip_reason": skip_reason,
    }


def resolve_wizard_steps(required_steps: list[OnboardingStepId]) -> list[OnboardingStepId]:
    """UI sequence: skip Welcome when at most two non-welcome steps remain."""
    pending = [step for step in required_steps if step != "welcome"]
    if len(pending) <= 2:
        return pending
    return required_steps


def should_skip_wizard(
    *,
    setup_complete: bool,
    birth_status: str,
    artifacts_ok: bool,
    required_steps: list[OnboardingStepId],
) -> bool:
    """True when the user can enter the Command Deck without the wizard."""
    if not required_steps or required_steps == ["welcome"]:
        if setup_complete and (birth_status == "running" or artifacts_ok):
            return True
        if setup_complete and birth_status in {"completed", "error"}:
            return True
    pending = [s for s in required_steps if s not in {"welcome"}]
    if not pending and setup_complete:
        return birth_status == "running" or artifacts_ok
    return False


def extract_env_diagnostics(env_values: dict[str, str] | None = None) -> dict[str, Any]:
    """Operator diagnostics toggles persisted in .env (Streamlit sidebar parity)."""
    env = env_values or {}

    def _bool(key: str, default: bool) -> bool:
        raw = str(env.get(key, str(default))).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _int(key: str, default: int, *, lo: int, hi: int) -> int:
        try:
            value = int(str(env.get(key, default)).strip())
        except (TypeError, ValueError):
            value = default
        return max(lo, min(hi, value))

    return {
        "dashboard_enabled": _bool("DASHBOARD_ENABLED", True),
        "runtime_trace": _bool("LUMINA_RUNTIME_TRACE", True),
        "runtime_trace_interval_sec": _int(
            "LUMINA_RUNTIME_TRACE_INTERVAL_SEC", 2, lo=0, hi=10
        ),
        "latency_sla_ms": _int("LUMINA_LATENCY_SLA_MS", 300, lo=150, hi=1000),
    }


def extract_config_defaults(
    config: dict[str, Any],
    *,
    env_values: dict[str, str] | None = None,
) -> dict[str, Any]:
    sim = config.get("sim") if isinstance(config.get("sim"), dict) else {}
    real = config.get("real") if isinstance(config.get("real"), dict) else {}
    evolution = config.get("evolution") if isinstance(config.get("evolution"), dict) else {}
    first_boot = config.get("first_boot") if isinstance(config.get("first_boot"), dict) else {}
    risk_controller = config.get("risk_controller") if isinstance(config.get("risk_controller"), dict) else {}
    return {
        "mode": str(config.get("mode", "sim")),
        "sim": {
            "kelly_fraction": sim.get("kelly_fraction", 1.0),
            "daily_loss_cap": sim.get("daily_loss_cap"),
            "max_total_open_risk": sim.get("max_total_open_risk", 3000.0),
            "aggressive_evolution": sim.get("aggressive_evolution", True),
            "approval_required": sim.get("approval_required", False),
            "max_mutation_depth": sim.get("max_mutation_depth", "radical"),
        },
        "real": {
            "kelly_fraction": real.get("kelly_fraction", 0.25),
            "daily_loss_cap": real.get("daily_loss_cap", -150.0),
            "max_total_open_risk": real.get("max_total_open_risk", 150.0),
            "aggressive_evolution": real.get("aggressive_evolution", False),
            "approval_required": real.get("approval_required", True),
            "max_mutation_depth": real.get("max_mutation_depth", "conservative"),
        },
        "evolution": {
            "approval_required": evolution.get("approval_required", True),
            "aggressive_evolution": sim.get("aggressive_evolution", True),
        },
        "first_boot": {
            "training_trades": first_boot.get("training_trades", 25000),
            "prefer_real_data_only": first_boot.get("prefer_real_data_only", True),
            "max_real_days": first_boot.get("max_real_days", 56),
        },
        "risk_controller": {
            "real_capital_safety_threshold_usd": risk_controller.get(
                "real_capital_safety_threshold_usd", 1000.0
            ),
            "max_total_open_risk": risk_controller.get("max_total_open_risk", 3000.0),
        },
        "diagnostics": extract_env_diagnostics(env_values),
    }
