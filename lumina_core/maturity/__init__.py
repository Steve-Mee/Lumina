"""Lumina maturation ladder SSOT (ADR-0027) + organism continuum hub + H7 birth exit."""

from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
    load_maturation_progress,
    maturation_eligible_for_real,
    record_maturation_milestone,
    resolve_current_phase,
    save_maturation_progress,
)

__all__ = [
    "MaturationPhase",
    "evaluate_birth_exit",
    "is_birth_exit_sufficient",
    "load_maturation_progress",
    "maturation_eligible_for_real",
    "record_maturation_milestone",
    "resolve_current_phase",
    "save_maturation_progress",
    "maturity_service",
]


def __getattr__(name: str):
    if name == "maturity_service":
        from lumina_core.maturity.maturity_service import maturity_service

        return maturity_service
    if name in ("evaluate_birth_exit", "is_birth_exit_sufficient"):
        from lumina_core.maturity import birth_exit as _be

        return getattr(_be, name)
    raise AttributeError(name)
