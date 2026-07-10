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

AppSurface = Literal["setup", "birth", "deck"]
AppSurfaceReason = Literal[
    "fresh_install",
    "setup_incomplete",
    "birth_pending",
    "birth_running",
    "birth_interrupted",
    "birth_error",
    "certificate_failed",
    "birth_complete",
    "backend_unreachable",
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
    certificate_ok: bool | None = None,
    smart_setup_running: bool = False,
) -> tuple[list[OnboardingStepId], dict[str, StepStatus]]:
    """Return required wizard steps and per-step status."""
    birth_ready = certificate_ok if certificate_ok is not None else artifacts_ok
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
    if setup_complete and birth_idle and not birth_ready:
        required.append("birth")
        step_status["birth"] = "pending"
    elif birth_status == "running":
        step_status["birth"] = "running"
    elif birth_status == "certificate_failed":
        required.append("birth")
        step_status["birth"] = "pending"
    elif birth_ready or birth_status == "completed":
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
    backend_reachable: bool = True,
    certificate_ok: bool | None = None,
) -> bool:
    """True when the user can enter the Command Deck without the wizard (fail-closed on artifacts)."""
    surface, _ = resolve_app_surface(
        setup_complete=setup_complete,
        birth_status=birth_status,
        artifacts_ok=artifacts_ok,
        certificate_ok=certificate_ok,
        backend_reachable=backend_reachable,
        required_steps=required_steps,
    )
    return surface == "deck"


def _has_pending_setup_steps(required_steps: list[OnboardingStepId]) -> bool:
    setup_steps = {"backend", "ollama", "model", "credentials", "configuration"}
    return any(step in setup_steps for step in required_steps)


def resolve_app_surface(
    *,
    setup_complete: bool,
    birth_status: str,
    artifacts_ok: bool,
    backend_reachable: bool,
    required_steps: list[OnboardingStepId],
    certificate_ok: bool | None = None,
) -> tuple[AppSurface, AppSurfaceReason]:
    """Canonical lifecycle surface for cold start (Phase 1 SSOT). Fail-closed on certificate."""
    if not backend_reachable:
        return "setup", "backend_unreachable"

    if not setup_complete or _has_pending_setup_steps(required_steps):
        return "setup", "setup_incomplete" if setup_complete else "fresh_install"

    birth_ready = certificate_ok if certificate_ok is not None else artifacts_ok
    if not birth_ready:
        if birth_status == "running":
            return "birth", "birth_running"
        if birth_status == "interrupted":
            return "birth", "birth_interrupted"
        if birth_status == "error":
            return "birth", "birth_error"
        if birth_status == "certificate_failed":
            return "birth", "certificate_failed"
        if birth_status == "completed" and certificate_ok is False:
            return "birth", "certificate_failed"
        return "birth", "birth_pending"

    return "deck", "birth_complete"


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


def _extract_birth_v2_defaults(config: dict[str, Any]) -> dict[str, Any]:
    birth_v2 = config.get("birth_v2") if isinstance(config.get("birth_v2"), dict) else {}
    curriculum = (
        birth_v2.get("curriculum") if isinstance(birth_v2.get("curriculum"), dict) else {}
    )
    return {
        "stage1_winrate_pass_threshold": float(
            curriculum.get("stage1_winrate_pass_threshold", 0.45)
        ),
        "stage1_winrate_recommended": float(
            curriculum.get("stage1_winrate_recommended", 0.45)
        ),
        "stage1_winrate_pass_floor": float(curriculum.get("stage1_winrate_pass_floor", 0.35)),
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
            "approval_required": evolution.get("approval_required", False),
            "aggressive_evolution": sim.get("aggressive_evolution", True),
        },
        "first_boot": {
            "training_trades": first_boot.get("training_trades", 25000),
            "prefer_real_data_only": first_boot.get("prefer_real_data_only", True),
            "max_real_days": first_boot.get("max_real_days", 56),
            "allow_minimal_synthetic_fallback": first_boot.get(
                "allow_minimal_synthetic_fallback", False
            ),
        },
        "birth_v2": _extract_birth_v2_defaults(config),
        "risk_controller": {
            "real_capital_safety_threshold_usd": risk_controller.get(
                "real_capital_safety_threshold_usd", 1000.0
            ),
            "max_total_open_risk": risk_controller.get("max_total_open_risk", 3000.0),
        },
        "diagnostics": extract_env_diagnostics(env_values),
    }
