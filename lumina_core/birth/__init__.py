"""Birth Phase v2 — curriculum training, OOS certificate, evolution handoff."""

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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
