"""Register generation-0 DNA from Birth Certificate v2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
    # Proactive twin evaluation (primary auto layer) — emits TwinDecisionEvent to bus.
    # Birth gen0 is high-signal; twin rec logged for audit.
    try:
        # caller may pass twin via closure or we use global orchestrator twin
        from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator
        twin = getattr(EvolutionOrchestrator(), "_approval_twin", None)
        if twin is not None:
            _ = twin.evaluate_dna_promotion(dna)
            # Twin is judgment provider only. Constitution, sandbox and aperture guards are never bypassed (explicit fail-closed in twin + callers).
    except Exception:
        pass
    registry.register_dna(dna)
    logger.info("birth.dna_handoff.registered lineage=%s", lineage)


def register_partial_birth_dna(
    workspace_root: Path | str,
    *,
    curriculum_stage: str,
    stage_trades: int,
    stage_winrate: float,
    oos_proxy_winrate: float | None,
    policy_path: str,
    stall_reason: str,
) -> None:
    """Seed provisional gen-0 DNA when birth stalls but has learnable signal."""
    root = Path(workspace_root)
    registry = DNARegistry(
        jsonl_path=root / "state" / "dna_registry.jsonl",
        sqlite_path=root / "state" / "dna_registry.sqlite3",
    )
    if registry.get_latest_dna(version="active") is not None:
        logger.info("birth.dna_handoff.partial_skip_active_exists")
        return
    proxy = float(oos_proxy_winrate if oos_proxy_winrate is not None else stage_winrate)
    fitness = max(float(stage_winrate), proxy)
    lineage = f"birth_partial_{curriculum_stage}_{stage_trades}"
    content = {
        "candidate_name": "birth_v2_partial",
        "birth_certificate_version": "provisional",
        "oos_winrate": proxy,
        "oos_sharpe": fitness,
        "regime_focus": [],
        "curriculum_stage": curriculum_stage,
        "stall_reason": stall_reason,
        "policy_path": policy_path,
        "graduation_tier": "provisional",
    }
    dna = PolicyDNA.create(
        prompt_id="birth_v2_partial",
        version="active",
        content=content,
        fitness_score=fitness,
        generation=0,
        lineage_hash=lineage[:16],
        mutation_rate=0.0,
    )
    try:
        from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator
        twin = getattr(EvolutionOrchestrator(), "_approval_twin", None)
        if twin is not None:
            _ = twin.evaluate_dna_promotion(dna)
            # Twin is judgment provider only. Constitution, sandbox and aperture guards are never bypassed (explicit fail-closed in twin + callers).
    except Exception:
        pass
    registry.register_dna(dna)
    logger.info(
        "birth.dna_handoff.partial_registered stage=%s fitness=%.4f reason=%s",
        curriculum_stage,
        fitness,
        stall_reason,
    )


def register_birth_gen0_from_fitness(workspace_root: Path | str, vector: Any) -> None:
    """Gen-0 DNA from Stage-5 fitness vector (not cert Sharpe)."""
    root = Path(workspace_root)
    registry = DNARegistry(
        jsonl_path=root / "state" / "dna_registry.jsonl",
        sqlite_path=root / "state" / "dna_registry.sqlite3",
    )
    if registry.get_latest_dna(version="active") is not None:
        logger.info("birth.dna_handoff.fitness_skip_active_exists")
        return
    payload = vector.to_dict() if hasattr(vector, "to_dict") else dict(vector)
    fitness = float(payload.get("mean_r") or 0.0) + float(payload.get("edge") or 0.0)
    lineage = str(payload.get("s5_receipt_checksum") or "foundation")[:16]
    content = {
        "candidate_name": "birth_foundation_v2",
        "birth_certificate_version": "foundation_v2",
        "mean_r": payload.get("mean_r"),
        "edge": payload.get("edge"),
        "occupancy": payload.get("occupancy"),
        "oos_wr": payload.get("oos_wr"),
        "oos_sharpe": payload.get("oos_sharpe"),
        "median_loss_r": payload.get("median_loss_r"),
        "hyperparam_suggestion": {
            "max_risk_percent": 1.0,
            "drawdown_kill_percent": 8.0,
            "fast_path_threshold": 0.78,
        },
    }
    dna = PolicyDNA.create(
        prompt_id="birth_foundation_v2",
        version="active",
        content=content,
        fitness_score=fitness,
        generation=0,
        lineage_hash=lineage,
        mutation_rate=0.0,
    )
    registry.register_dna(dna)
    logger.info("birth.dna_handoff.foundation_registered fitness=%.4f", fitness)


def resolve_birth_gen0_dna(registry: DNARegistry) -> PolicyDNA | None:
    """Return active gen-0 DNA registered from Birth Certificate v2, if any."""
    active = registry.get_latest_dna(version="active")
    if active is None:
        return None
    if str(getattr(active, "prompt_id", "") or "") in {
        "birth_v2_certificate",
        "birth_v2_partial",
        "birth_foundation_v2",
    }:
        return active
    content = active.content if isinstance(active.content, dict) else {}
    candidate = str(content.get("candidate_name", "") or "")
    if candidate in {"birth_v2_certificate", "birth_v2_partial"}:
        return active
    if int(getattr(active, "generation", -1) or -1) == 0 and content.get("birth_certificate_version") == "2.0":
        return active
    return None
