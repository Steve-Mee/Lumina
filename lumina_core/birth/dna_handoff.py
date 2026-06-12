"""Register generation-0 DNA from Birth Certificate v2."""

from __future__ import annotations

from pathlib import Path

from lumina_core.birth.birth_certificate import BirthCertificateV2
from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.dna_handoff")


def register_birth_gen0_dna(workspace_root: Path | str, certificate: BirthCertificateV2) -> None:
    root = Path(workspace_root)
    registry = DNARegistry(
        jsonl_path=root / "state" / "dna_registry.jsonl",
        sqlite_path=root / "state" / "dna_registry.sqlite3",
    )
    if registry.get_latest_dna(version="active") is not None:
        logger.info("birth.dna_handoff.skip_active_exists")
        return

    lineage = certificate.policy_sha256[:16]
    content = {
        "candidate_name": "birth_v2_certificate",
        "birth_certificate_version": certificate.version,
        "oos_sharpe": certificate.oos_sharpe,
        "oos_winrate": certificate.oos_winrate,
        "regime_focus": list(certificate.regimes_covered),
        "hyperparam_suggestion": {
            "max_risk_percent": 1.0,
            "drawdown_kill_percent": 8.0,
            "fast_path_threshold": 0.78,
        },
    }
    dna = PolicyDNA.create(
        prompt_id="birth_v2_certificate",
        version="active",
        content=content,
        fitness_score=float(certificate.oos_sharpe),
        generation=0,
        lineage_hash=lineage,
        mutation_rate=0.0,
    )
    registry.register_dna(dna)
    logger.info("birth.dna_handoff.registered lineage=%s", lineage)


def resolve_birth_gen0_dna(registry: DNARegistry) -> PolicyDNA | None:
    """Return active gen-0 DNA registered from Birth Certificate v2, if any."""
    active = registry.get_latest_dna(version="active")
    if active is None:
        return None
    if str(getattr(active, "prompt_id", "") or "") == "birth_v2_certificate":
        return active
    content = active.content if isinstance(active.content, dict) else {}
    if str(content.get("candidate_name", "") or "") == "birth_v2_certificate":
        return active
    if int(getattr(active, "generation", -1) or -1) == 0 and content.get("birth_certificate_version") == "2.0":
        return active
    return None
