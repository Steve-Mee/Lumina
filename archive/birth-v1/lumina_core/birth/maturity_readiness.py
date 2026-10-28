"""Birth → certificate / Perfect Birth readiness telemetry (Phase D).

Honest absence only — never hollow-declare Perfect Birth or Certificate v2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


from lumina_core.birth.foundation_metrics import FOUNDATION_STAGE_COUNT


def certificate_readiness_blockers(
    *,
    stages_passed_count: int,
    plateau_active: bool,
    expectancy_stall: bool,
    needs_attention: bool,
    certificate_present: bool,
    curriculum_stages_required: int = FOUNDATION_STAGE_COUNT,
) -> list[str]:
    """Ordered blocker codes for operator UI / progress scorecard."""
    blockers: list[str] = []
    need = max(1, int(curriculum_stages_required))
    done = max(0, int(stages_passed_count))
    if done < need:
        blockers.append(f"curriculum_stages_{done}/{need}")
    if plateau_active:
        blockers.append("plateau_active")
    if expectancy_stall:
        blockers.append("expectancy_stall")
    if needs_attention:
        blockers.append("needs_attention")
    if not certificate_present:
        blockers.append("certificate_absent")
    return blockers


def certificate_path_ready(
    *,
    stages_passed_count: int,
    plateau_active: bool,
    needs_attention: bool,
    curriculum_stages_required: int = FOUNDATION_STAGE_COUNT,
) -> bool:
    """True only when curriculum complete and not mid thrash (still no hollow cert)."""
    need = max(1, int(curriculum_stages_required))
    return (
        int(stages_passed_count) >= need
        and not bool(plateau_active)
        and not bool(needs_attention)
    )


def maturity_artifact_presence(workspace_root: Path | str) -> dict[str, Any]:
    """File presence SSOT for certificate / proof / Perfect Birth flag."""
    root = Path(workspace_root)
    cert = root / "state" / "lumina_birth_certificate.json"
    proof = root / "state" / "lumina_evolution_proof.json"
    pb = root / "state" / "perfect_birth_complete.flag"
    return {
        "certificate_present": cert.is_file(),
        "evolution_proof_present": proof.is_file(),
        "perfect_birth_flag_present": pb.is_file(),
        "certificate_path": str(cert),
        "evolution_proof_path": str(proof),
        "perfect_birth_flag_path": str(pb),
    }


__all__ = [
    "certificate_path_ready",
    "certificate_readiness_blockers",
    "maturity_artifact_presence",
]
