"""H7: Birth exit policy vs post-birth maturation (ADR-0036 + ADR-0046).

Birth exit means the plant is *evolvable* — five foundation receipts + fitness
vector — not a professional daytrader, Perfect Birth, or REAL-eligible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
    load_maturation_progress,
)

logger = get_logger("lumina.maturity.birth_exit")

# Explicit: these milestones advance maturation AFTER birth — never Birth exit bars.
POST_BIRTH_ONLY_MILESTONES: frozenset[str] = frozenset(
    {
        "evolution_proof_passed",
        "perfect_birth_autonomy_proven",
        "deck_unlocked",
        "first_sim_order_placed",
        "sim_mirror_api_ok",
        "sim_real_guard_stable",
        "shadow_validation_passed",
        "promotion_gate_passed",
        "human_real_approval",
        "real_trading_live",
    }
)

# Proofs that must ALL hold for Birth phase exit (ADR-0046). Any-of artifacts is closed.
BIRTH_EXIT_PROOFS: frozenset[str] = frozenset(
    {
        "foundation_five_receipts_v2",
        "foundation_fitness_vector",
    }
)

# Floors that belong to Birth survival grading (EdgeScore), not Proving Ground.
DEFAULT_SURVIVAL_WR_FLOOR = 0.20
DEFAULT_SURVIVAL_EXPECTANCY_FLOOR = -0.50
DEFAULT_SKILL_WR_FLOOR = 0.35
DEFAULT_SKILL_EXPECTANCY_FLOOR = -0.15
# Proving / cert skill walls — documented as NOT birth exit
PROVING_OOS_WR_EXAMPLE = 0.48


@dataclass(frozen=True, slots=True)
class BirthSurvivalFloors:
    """Stage-1 EdgeScore floors while ``birth_survival_pass_enabled`` is true."""

    wr_floor: float = DEFAULT_SURVIVAL_WR_FLOOR
    expectancy_floor: float = DEFAULT_SURVIVAL_EXPECTANCY_FLOOR
    plant_soft_block_rate_max_per_1k: float = 100.0
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "birth_survival_pass_enabled": self.enabled,
            "wr_floor": self.wr_floor,
            "expectancy_floor": self.expectancy_floor,
            "plant_soft_block_rate_max_per_1k": self.plant_soft_block_rate_max_per_1k,
            "note": (
                "Survival floors for Birth EdgeScore only. "
                f"Skill WR floor {DEFAULT_SKILL_WR_FLOOR} applies when survival mode off; "
                f"OOS {PROVING_OOS_WR_EXAMPLE} is Proving Ground / cert — not Birth exit."
            ),
        }


@dataclass(frozen=True, slots=True)
class BirthExitDecision:
    exited: bool
    proofs: tuple[str, ...]
    missing: tuple[str, ...]
    survival: BirthSurvivalFloors
    conflation_blockers: tuple[str, ...]
    next_phase: str = MaturationPhase.AWAKENING.value
    hub_after_exit: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "birth_exit_v1",
            "exited": self.exited,
            "proofs": list(self.proofs),
            "missing": list(self.missing),
            "survival": self.survival.to_dict(),
            "conflation_blockers": list(self.conflation_blockers),
            "next_phase": self.next_phase if self.exited else None,
            "hub_after_exit": self.hub_after_exit,
            "policy": birth_exit_policy_dict(),
        }


def birth_exit_policy_dict() -> dict[str, Any]:
    """Operator-facing contract: what Birth exit is and is not."""
    return {
        "birth_exit_means": [
            "five_foundation_v2_receipts",
            "fitness_vector_checksum_ok",
            "legal_plant_hard_const_ok",
            "return_to_phase_hub",
        ],
        "birth_exit_does_not_require": sorted(POST_BIRTH_ONLY_MILESTONES)
        + [
            "perfect_birth_flag",
            "oos_wr_0_48",
            "twin_full_auto",
            "real_capital",
        ],
        "after_birth": {
            "surface": "phase_hub",
            "next_phase": MaturationPhase.AWAKENING.value,
            "perfect_birth": "awakening_or_phase2_unlock_not_birth_gate",
            "certificate_skill_walls": "proving_ground_and_cert_pipeline",
            "economic_viability": "playground",
            "risk_discipline": "apprenticeship",
            "evolution_proof": "awakening",
        },
        "adr": ["0036-birth-exit-vs-maturation", "0046-birth-foundation-evolvable-plant"],
        "sufficient_proofs_all_of": sorted(BIRTH_EXIT_PROOFS),
    }


def survival_floors_from_cfg(cfg: Any | None = None) -> BirthSurvivalFloors:
    if cfg is None:
        return BirthSurvivalFloors()
    return BirthSurvivalFloors(
        enabled=bool(getattr(cfg, "birth_survival_pass_enabled", True)),
        wr_floor=float(getattr(cfg, "birth_survival_wr_floor", DEFAULT_SURVIVAL_WR_FLOOR)),
        expectancy_floor=float(
            getattr(cfg, "birth_survival_expectancy_floor", DEFAULT_SURVIVAL_EXPECTANCY_FLOOR)
        ),
        plant_soft_block_rate_max_per_1k=float(
            getattr(cfg, "birth_plant_soft_block_rate_max_per_1k", 100.0)
        ),
    )


def skill_floors_from_cfg(cfg: Any | None = None) -> dict[str, float]:
    if cfg is None:
        return {
            "wr_floor": DEFAULT_SKILL_WR_FLOOR,
            "expectancy_floor": DEFAULT_SKILL_EXPECTANCY_FLOOR,
        }
    return {
        "wr_floor": float(getattr(cfg, "stage1_winrate_pass_floor", DEFAULT_SKILL_WR_FLOOR)),
        "expectancy_floor": float(
            getattr(cfg, "stage1_expectancy_floor", DEFAULT_SKILL_EXPECTANCY_FLOOR)
        ),
    }


def effective_stage1_floors(cfg: Any | None = None) -> dict[str, Any]:
    """Floors EdgeScore should use — survival when enabled, else skill."""
    surv = survival_floors_from_cfg(cfg)
    skill = skill_floors_from_cfg(cfg)
    if surv.enabled:
        return {
            "mode": "survival",
            "wr_floor": surv.wr_floor,
            "expectancy_floor": surv.expectancy_floor,
            "skill_floors_deferred": skill,
        }
    return {
        "mode": "skill",
        "wr_floor": skill["wr_floor"],
        "expectancy_floor": skill["expectancy_floor"],
        "survival": surv.to_dict(),
    }


def collect_birth_exit_proofs(workspace_root: Path | str) -> tuple[list[str], dict[str, Any]]:
    """Foundation exit: five v2 receipts + fitness vector. Artifacts-only is not enough."""
    root = Path(workspace_root)
    proofs: list[str] = []
    detail: dict[str, Any] = {}

    from lumina_core.birth.config import BirthCurriculumConfig
    from lumina_core.birth.curriculum_types import ordered_stages
    from lumina_core.birth.fitness_vector import load_fitness_vector, receipt_checksum
    from lumina_core.birth.foundation_metrics import FOUNDATION_SCHEMA
    from lumina_core.birth.progress import read_birth_progress
    from lumina_core.birth.stage_pass_receipt_types import (
        parse_stage_pass_receipts,
        receipt_for_stage,
    )

    progress = read_birth_progress(root)
    receipts = parse_stage_pass_receipts(progress.get("stage_pass_receipts"))
    if not receipts:
        ckpt = root / "state" / "lumina_birth_checkpoint.json"
        if ckpt.is_file():
            try:
                import json

                raw = json.loads(ckpt.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    receipts = parse_stage_pass_receipts(raw.get("stage_pass_receipts"))
            except (OSError, ValueError):
                receipts = []

    required = [s.value for s in ordered_stages()]
    missing_stages: list[str] = []
    cfg = BirthCurriculumConfig()
    try:
        from lumina_core.birth.config import load_birth_v2_config

        cfg = load_birth_v2_config(root).curriculum
    except Exception:
        cfg = BirthCurriculumConfig()
    from lumina_core.birth.curriculum_types import CurriculumStage
    from lumina_core.birth.stage_pass_receipt_verify import verify_stage_pass_receipt

    for stage_value in required:
        rec = receipt_for_stage(receipts, stage_value)
        if rec is None or str(getattr(rec, "schema", "") or "") != FOUNDATION_SCHEMA:
            missing_stages.append(stage_value)
            continue
        stage_enum = CurriculumStage(stage_value)
        ok, reason = verify_stage_pass_receipt(
            stage_enum,
            rec,
            cfg=cfg,
            training_mode="certified",
        )
        if not ok:
            missing_stages.append(stage_value)
            detail.setdefault("receipt_verify_failures", {})[stage_value] = reason
    detail["required_stages"] = required
    detail["missing_foundation_stages"] = missing_stages
    if not missing_stages:
        proofs.append("foundation_five_receipts_v2")

    vector = load_fitness_vector(root)
    s5 = receipt_for_stage(receipts, "stage5_probe_handoff")
    vector_ok = False
    if vector is not None and s5 is not None:
        expected = receipt_checksum(s5.to_dict())
        vector_ok = str(vector.s5_receipt_checksum) == expected
        detail["fitness_checksum_ok"] = vector_ok
        detail["fitness_checksum"] = vector.s5_receipt_checksum
        detail["s5_checksum"] = expected
    else:
        detail["fitness_vector_present"] = vector is not None
        detail["s5_receipt_present"] = s5 is not None
    if vector_ok:
        proofs.append("foundation_fitness_vector")

    detail["completed_flag"] = (root / "state" / "lumina_birth_completed.flag").is_file()
    detail["artifacts_insufficient_alone"] = True

    seen: set[str] = set()
    ordered: list[str] = []
    for p in proofs:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered, detail


def evaluate_birth_exit(
    workspace_root: Path | str,
    *,
    cfg: Any | None = None,
) -> BirthExitDecision:
    """Whether Birth phase may complete and return operator to Phase Hub.

    Never requires Perfect Birth, promotion, READY_FOR_REAL, or OOS skill walls.
    """
    proofs, detail = collect_birth_exit_proofs(workspace_root)
    survival = survival_floors_from_cfg(cfg)

    # Conflation: report post-birth milestones present but do not require them
    progress = load_maturation_progress(workspace_root)
    reached = set(progress.milestones_reached)
    post = sorted(POST_BIRTH_ONLY_MILESTONES & reached)

    sufficient = [p for p in proofs if p in BIRTH_EXIT_PROOFS]
    exited = set(BIRTH_EXIT_PROOFS).issubset(set(sufficient))
    missing: list[str] = []
    if not exited:
        missing = sorted(BIRTH_EXIT_PROOFS - set(sufficient))

    return BirthExitDecision(
        exited=exited,
        proofs=tuple(sufficient),
        missing=tuple(missing),
        survival=survival,
        conflation_blockers=tuple(post),  # informational: present but not required
    )


def birth_exit_status_payload(
    workspace_root: Path | str,
    *,
    cfg: Any | None = None,
) -> dict[str, Any]:
    """API/hub panel for Birth exit vs maturation."""
    if cfg is None:
        try:
            from lumina_core.birth.config import load_birth_v2_config

            cfg = load_birth_v2_config(Path(workspace_root)).curriculum
        except Exception:
            cfg = None

    decision = evaluate_birth_exit(workspace_root, cfg=cfg)
    floors = effective_stage1_floors(cfg)
    continuum_birth_done = False
    try:
        from lumina_core.maturity.continuum import load_continuum

        cont = load_continuum(workspace_root)
        continuum_birth_done = MaturationPhase.BIRTH.value in set(
            cont.get("completed_phases") or []
        )
    except Exception:
        pass

    # Perfect Birth is orthogonal
    perfect_flag = Path(workspace_root) / "state" / "perfect_birth_complete.flag"
    return {
        **decision.to_dict(),
        "stage1_floors_effective": floors,
        "continuum_birth_completed": continuum_birth_done,
        "perfect_birth_flag_present": perfect_flag.is_file(),
        "perfect_birth_required_for_birth_exit": False,
        "real_eligible_required_for_birth_exit": False,
        "message": (
            "Birth exit satisfied — return to Phase Hub; next is Awakening."
            if decision.exited
            else "Birth Foundation incomplete — need five v2 receipts + fitness vector."
        ),
    }


def is_birth_exit_sufficient(workspace_root: Path | str) -> bool:
    return evaluate_birth_exit(workspace_root).exited


def assert_milestone_not_birth_exit_gate(milestone_id: str) -> bool:
    """True if milestone must not be used as Birth exit requirement."""
    return str(milestone_id) in POST_BIRTH_ONLY_MILESTONES


__all__ = [
    "BIRTH_EXIT_PROOFS",
    "POST_BIRTH_ONLY_MILESTONES",
    "BirthExitDecision",
    "BirthSurvivalFloors",
    "assert_milestone_not_birth_exit_gate",
    "birth_exit_policy_dict",
    "birth_exit_status_payload",
    "collect_birth_exit_proofs",
    "effective_stage1_floors",
    "evaluate_birth_exit",
    "is_birth_exit_sufficient",
    "skill_floors_from_cfg",
    "survival_floors_from_cfg",
]
