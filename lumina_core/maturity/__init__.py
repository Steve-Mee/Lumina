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
        raise AttributeError("maturity_service archived with Birth-v1")
    if name == "evaluate_birth_exit":
        return lambda *_a, **_k: {"ok": False, "reason": "BIRTH_V1_ARCHIVED"}
    if name == "is_birth_exit_sufficient":
        return lambda *_a, **_k: False
    raise AttributeError(name)
