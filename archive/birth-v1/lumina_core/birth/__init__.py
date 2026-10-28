"""Birth Phase v2 — curriculum training, OOS certificate, evolution handoff.

Bounded context using central EventBus (see docs/adr/0001-...).
CurriculumOrchestrator is intentionally thin and event-only.
Curriculum, plateau, remediation, phoenix, and intra-stage logic live in
dedicated single-responsibility modules (handlers).
"""

from lumina_core.birth.birth_certificate import (
    BirthCertificateV2,
    BirthCertificateThresholds,
    certificate_path,
    load_certificate,
    validate_certificate_artifacts,
    write_certificate,
)
from lumina_core.birth.config import BirthV2Config, load_birth_v2_config

__all__ = [
    "BirthCertificateThresholds",
    "BirthCertificateV2",
    "BirthPhaseEngineV2",
    "BirthV2Config",
    "ConstitutionEnforcer",
    "CurriculumOrchestrator",
    "CurriculumStageHandler",
    "certificate_path",
    "load_birth_v2_config",
    "load_certificate",
    "validate_certificate_artifacts",
    "write_certificate",
]


def __getattr__(name: str):
    if name == "BirthPhaseEngineV2":
        from lumina_core.birth.engine import BirthPhaseEngineV2

        return BirthPhaseEngineV2
    if name == "CurriculumOrchestrator":
        from lumina_core.birth.curriculum_orchestrator import CurriculumOrchestrator

        return CurriculumOrchestrator
    if name == "CurriculumStageHandler":
        from lumina_core.birth.curriculum_stage_handler import CurriculumStageHandler

        return CurriculumStageHandler
    if name == "ConstitutionEnforcer":
        from lumina_core.birth.constitution_enforcer import ConstitutionEnforcer

        return ConstitutionEnforcer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
