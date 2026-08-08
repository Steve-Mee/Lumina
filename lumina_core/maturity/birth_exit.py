"""H7: Birth exit policy vs post-birth maturation (ADR-0036).

Birth exit means the newborn *survived* the curriculum loop — not that it is a
professional daytrader, Perfect Birth unlock, or REAL-eligible.

Non-goals for Birth exit (must NOT block Birth→Hub):
- Perfect Birth KPI conjunction / Phase 2 flag
- Promotion gate / shadow validation
- OOS WR ≥ 0.48 certificate skill walls (Proving Ground / cert pipeline)
- READY_FOR_REAL multi-day streak
- Twin high-conf primary / full_auto
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

# Proofs that may complete Birth phase (any one sufficient when artifacts honest).
BIRTH_EXIT_PROOFS: frozenset[str] = frozenset(
    {
        "birth_curriculum_complete",  # stages + engine completed
        "birth_artifacts_ok",  # DNA / checkpoint / completed flag
        "birth_certificate_issued",  # cert issued (stronger; still not Perfect Birth)
        "birth_started_with_artifacts",  # started + artifacts after crash recovery
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
            "survive_closed_training_loop",
            "legal_plant_hard_const_ok",
            "curriculum_or_artifacts_or_certificate",
            "return_to_phase_hub",
        ],
        "birth_exit_does_not_require": sorted(POST_BIRTH_ONLY_MILESTONES)
        + [
            "perfect_birth_flag",
            "oos_wr_0_48",
            "twin_full_auto",
            "real_capital",
        ],
        "sufficient_proofs_any_of": sorted(BIRTH_EXIT_PROOFS),
        "survival_vs_skill": {
            "birth_default": "survival",
            "survival_wr_floor": DEFAULT_SURVIVAL_WR_FLOOR,
            "skill_wr_floor_when_survival_off": DEFAULT_SKILL_WR_FLOOR,
            "proving_oos_wr_not_birth_exit": PROVING_OOS_WR_EXAMPLE,
        },
        "after_birth": {
            "surface": "phase_hub",
            "next_phase": MaturationPhase.AWAKENING.value,
            "perfect_birth": "awakening_or_phase2_unlock_not_birth_gate",
            "certificate_skill_walls": "proving_ground_and_cert_pipeline",
        },
        "adr": "0036-birth-exit-vs-maturation",
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
    """Inspect workspace for Birth exit evidence (fail-closed best-effort)."""
    root = Path(workspace_root)
    proofs: list[str] = []
    detail: dict[str, Any] = {}

    progress = load_maturation_progress(root)
    reached = set(progress.milestones_reached)
    detail["milestones"] = sorted(reached)

    if "birth_certificate_issued" in reached:
        proofs.append("birth_certificate_issued")

    # Artifacts: BirthService when available, always OR filesystem probes (tmp/tests)
    artifacts_ok = False
    certificate_ok = False
    engine_completed = False
    try:
        from lumina_launcher.services.birth_service import BirthService

        svc = BirthService()
        svc.configure_workspace(root)
        artifacts_ok = bool(svc.artifacts_ok())
        certificate_ok = bool(svc.certificate_ok())
        engine_completed = bool(svc.is_completed())
    except Exception as exc:
        logger.debug("birth_exit.birth_service_probe_failed: %s", exc)

    fs_artifacts = _fs_birth_artifacts(root)
    fs_certificate = (root / "state" / "birth_certificate.json").is_file() or (
        root / "state" / "lumina_birth_certificate.json"
    ).is_file()
    fs_completed = (root / "state" / "lumina_birth_completed.flag").is_file()
    artifacts_ok = artifacts_ok or fs_artifacts
    certificate_ok = certificate_ok or fs_certificate
    engine_completed = engine_completed or fs_completed

    detail["artifacts_ok"] = artifacts_ok
    detail["certificate_ok"] = certificate_ok
    detail["engine_completed"] = engine_completed
    detail["fs_probes"] = {
        "artifacts": fs_artifacts,
        "certificate": fs_certificate,
        "completed_flag": fs_completed,
    }

    if certificate_ok and "birth_certificate_issued" not in proofs:
        proofs.append("birth_certificate_issued")
    if artifacts_ok:
        proofs.append("birth_artifacts_ok")
    if engine_completed:
        proofs.append("birth_curriculum_complete")
    if "birth_started" in reached and artifacts_ok:
        proofs.append("birth_started_with_artifacts")

    # De-dupe preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for p in proofs:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered, detail


def _fs_birth_artifacts(root: Path) -> bool:
    candidates = [
        root / "state" / "lumina_birth_completed.flag",
        root / "state" / "birth_checkpoint.json",
        root / "state" / "partial_dna.json",
        root / "state" / "lumina_partial_dna.json",
    ]
    return any(p.is_file() for p in candidates)


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
    exited = len(sufficient) > 0
    missing: list[str] = []
    if not exited:
        missing = ["birth_artifacts_or_certificate_or_curriculum_complete"]

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
            else "Birth still in progress — survival loop / artifacts not yet sufficient."
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
