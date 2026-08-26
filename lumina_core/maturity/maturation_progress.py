"""Post-birth maturation phase tracking (ADR-0027)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.maturity")


class MaturationPhase(str, Enum):
    GENESIS = "genesis"
    BIRTH = "birth"
    AWAKENING = "awakening"
    PLAYGROUND = "playground"
    APPRENTICESHIP = "apprenticeship"
    PROVING_GROUND = "proving_ground"
    REAL = "real"


PHASE_ORDER: tuple[MaturationPhase, ...] = (
    MaturationPhase.GENESIS,
    MaturationPhase.BIRTH,
    MaturationPhase.AWAKENING,
    MaturationPhase.PLAYGROUND,
    MaturationPhase.APPRENTICESHIP,
    MaturationPhase.PROVING_GROUND,
    MaturationPhase.REAL,
)

REAL_ELIGIBILITY_MILESTONES: tuple[str, ...] = (
    "birth_certificate_issued",
    "evolution_proof_passed",
    "sim_real_guard_stable",
    "promotion_gate_passed",
    "perfect_birth_autonomy_proven",  # Perfect Birth Phase graduation (twin accuracy + autonomy + alignment KPIs met)
)

MILESTONE_LABELS: dict[str, str] = {
    "birth_certificate_issued": "Birth Certificate v2 issued",
    "evolution_proof_passed": "Evolution Proof passed",
    "sim_real_guard_stable": "SIM stability READY_FOR_REAL (5-day green streak)",
    "promotion_gate_passed": "Promotion gate passed (shadow validation)",
    "human_real_approval": "Operator REAL approval recorded",
    "perfect_birth_autonomy_proven": "Perfect Birth Phase complete (twin vs Steve accuracy + never-stop recovery + auto-approval + shadow alignment)",
}

MILESTONE_TO_PHASE: dict[str, MaturationPhase] = {
    "genesis_contract_signed": MaturationPhase.GENESIS,
    "birth_started": MaturationPhase.BIRTH,
    "birth_certificate_issued": MaturationPhase.AWAKENING,
    "evolution_proof_passed": MaturationPhase.AWAKENING,
    "perfect_birth_autonomy_proven": MaturationPhase.AWAKENING,
    "deck_unlocked": MaturationPhase.PLAYGROUND,
    "first_sim_order_placed": MaturationPhase.PLAYGROUND,
    "sim_mirror_api_ok": MaturationPhase.PLAYGROUND,
    "sim_real_guard_stable": MaturationPhase.APPRENTICESHIP,
    "shadow_validation_passed": MaturationPhase.PROVING_GROUND,
    "promotion_gate_passed": MaturationPhase.PROVING_GROUND,
    "human_real_approval": MaturationPhase.REAL,
    "real_trading_live": MaturationPhase.REAL,
}


def maturation_state_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_maturity_progress.json"


@dataclass(slots=True)
class MaturationProgress:
    current_phase: MaturationPhase = MaturationPhase.GENESIS
    milestones_reached: list[str] = field(default_factory=list)
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_phase": self.current_phase.value,
            "milestones_reached": list(self.milestones_reached),
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> MaturationProgress:
        if not isinstance(raw, dict):
            return cls()
        phase_raw = str(raw.get("current_phase", MaturationPhase.GENESIS.value) or "")
        try:
            phase = MaturationPhase(phase_raw)
        except ValueError:
            phase = MaturationPhase.GENESIS
        milestones = raw.get("milestones_reached")
        return cls(
            current_phase=phase,
            milestones_reached=[str(x) for x in milestones if x] if isinstance(milestones, list) else [],
            updated_at=str(raw.get("updated_at", "") or ""),
            metadata=dict(raw.get("metadata") or {}) if isinstance(raw.get("metadata"), dict) else {},
        )


def load_maturation_progress(workspace_root: Path | str) -> MaturationProgress:
    path = maturation_state_path(workspace_root)
    if not path.is_file():
        return MaturationProgress()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return MaturationProgress.from_dict(raw if isinstance(raw, dict) else {})
    except Exception:
        return MaturationProgress()


def save_maturation_progress(workspace_root: Path | str, progress: MaturationProgress) -> None:
    path = maturation_state_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    progress.updated_at = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(progress.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")


def _phase_rank(phase: MaturationPhase) -> int:
    try:
        return PHASE_ORDER.index(phase)
    except ValueError:
        return 0


def resolve_current_phase(progress: MaturationProgress) -> MaturationPhase:
    highest = MaturationPhase.GENESIS
    for mid in progress.milestones_reached:
        candidate = MILESTONE_TO_PHASE.get(str(mid))
        if candidate is not None and _phase_rank(candidate) > _phase_rank(highest):
            highest = candidate
    return highest


def record_maturation_milestone(
    workspace_root: Path | str,
    milestone_id: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> MaturationProgress:
    progress = load_maturation_progress(workspace_root)
    mid = str(milestone_id or "").strip()
    if mid and mid not in progress.milestones_reached:
        progress.milestones_reached.append(mid)
        if metadata:
            progress.metadata[mid] = dict(metadata)
        progress.current_phase = resolve_current_phase(progress)
        save_maturation_progress(workspace_root, progress)
        logger.info(
            "maturity.milestone_reached id=%s phase=%s",
            mid,
            progress.current_phase.value,
        )
    return progress


def sync_stability_milestone(workspace_root: Path | str) -> None:
    """Record sim_real_guard_stable when stability report is READY_FOR_REAL."""
    import os

    root = Path(workspace_root).resolve()
    previous_cwd = Path.cwd()
    try:
        os.chdir(root)
        from lumina_core.engine.sim_stability_checker import generate_stability_report
        from lumina_core.maturity.milestone_hooks import hook_sim_real_guard_stable

        report = generate_stability_report()
        if bool(report.get("READY_FOR_REAL")):
            hook_sim_real_guard_stable(
                root,
                consecutive_green_days=int(report.get("consecutive_green_days", 0) or 0),
            )
    except Exception as exc:
        logger.debug("maturity.stability_sync_failed: %s", exc)
    finally:
        try:
            os.chdir(previous_cwd)
        except Exception:
            pass


def maturation_eligible_for_real(workspace_root: Path | str) -> tuple[bool, list[str]]:
    """Fail-closed REAL eligibility from maturation milestones (ADR-0027)."""
    root = Path(workspace_root)
    sync_maturation_from_birth_state(root)
    sync_stability_milestone(root)
    progress = load_maturation_progress(root)
    reached = set(progress.milestones_reached)
    blockers: list[str] = []
    for mid in REAL_ELIGIBILITY_MILESTONES:
        if mid not in reached:
            blockers.append(MILESTONE_LABELS.get(mid, mid))
    return len(blockers) == 0, blockers


def sync_maturation_from_birth_state(workspace_root: Path | str) -> MaturationProgress:
    """Best-effort sync of maturation milestones from birth artifacts."""
    from lumina_core.birth.evolution_proof_gate import evolution_proof_passed, load_evolution_proof_record
    from lumina_launcher.services.birth_service import BirthService

    progress = load_maturation_progress(workspace_root)
    svc = BirthService()
    svc.configure_workspace(Path(workspace_root))

    if svc.certificate_ok():
        if "birth_certificate_issued" not in progress.milestones_reached:
            progress.milestones_reached.append("birth_certificate_issued")
    if evolution_proof_passed(workspace_root):
        proof = load_evolution_proof_record(workspace_root)
        if proof and "evolution_proof_passed" not in progress.milestones_reached:
            progress.milestones_reached.append("evolution_proof_passed")
    if svc.artifacts_ok():
        from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

        if is_birth_exit_sufficient(workspace_root):
            if "deck_unlocked" not in progress.milestones_reached:
                progress.milestones_reached.append("deck_unlocked")
    progress.current_phase = resolve_current_phase(progress)
    save_maturation_progress(workspace_root, progress)
    return progress
