"""Continuum migrate/wipe helpers (global residual)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lumina_core.maturity.maturation_progress import (
    PHASE_ORDER,
    MaturationPhase,
    load_maturation_progress,
)

logger = logging.getLogger(__name__)


def _c():
    """Lazy continuum module (avoids import cycle with continuum re-exports)."""
    from lumina_core.maturity import continuum as c
    return c

def migrate_from_milestones(workspace_root: Path | str) -> dict[str, Any]:
    """Build continuum from existing maturation milestones (best-effort)."""
    data = _c()._empty_continuum()
    progress = load_maturation_progress(workspace_root)
    reached = set(progress.milestones_reached)
    completed: list[str] = []

    # Genesis
    if "genesis_contract_signed" in reached or progress.current_phase != MaturationPhase.GENESIS:
        completed.append(MaturationPhase.GENESIS.value)
        data["phase_records"][MaturationPhase.GENESIS.value] = {
            "status": "completed",
            "learned": {"note": "Setup / maturity contract present"},
            "exit_proofs": ["genesis_contract_signed"] if "genesis_contract_signed" in reached else [],
        }

    # Birth (H7 / ADR-0036): survival exit SSOT — not Perfect Birth / promotion
    try:
        from lumina_core.maturity.birth_exit import evaluate_birth_exit

        birth_decision = evaluate_birth_exit(workspace_root)
        birth_done = bool(birth_decision.exited)
        birth_proofs = list(birth_decision.proofs)
    except Exception:
        birth_done = False
        birth_proofs = []

    if birth_done:
        if MaturationPhase.BIRTH.value not in completed:
            completed.append(MaturationPhase.BIRTH.value)
        data["phase_records"][MaturationPhase.BIRTH.value] = {
            "status": "completed",
            "learned": _c()._birth_learned_snapshot(workspace_root),
            "exit_proofs": birth_proofs,
        }
    elif "birth_started" in reached:
        data["phase_records"][MaturationPhase.BIRTH.value] = {
            "status": "running",
            "learned": _c()._birth_learned_snapshot(workspace_root),
            "exit_proofs": [],
        }
        data["active_phase"] = MaturationPhase.BIRTH.value

    # Later phases from milestones
    mapping = [
        (MaturationPhase.AWAKENING.value, ("evolution_proof_passed", "perfect_birth_autonomy_proven")),
        (MaturationPhase.PLAYGROUND.value, ("deck_unlocked", "first_sim_order_placed", "sim_mirror_api_ok")),
        (MaturationPhase.APPRENTICESHIP.value, ("sim_real_guard_stable",)),
        (MaturationPhase.PROVING_GROUND.value, ("shadow_validation_passed", "promotion_gate_passed")),
        (MaturationPhase.REAL.value, ("human_real_approval", "real_trading_live")),
    ]
    for phase_id, proofs in mapping:
        hit = [p for p in proofs if p in reached]
        if not hit:
            continue
        # Require birth complete before counting later phases
        if MaturationPhase.BIRTH.value not in completed and phase_id != MaturationPhase.BIRTH.value:
            if not _c()._birth_artifacts_ok(workspace_root):
                continue
            if MaturationPhase.BIRTH.value not in completed:
                completed.append(MaturationPhase.BIRTH.value)
        # Awakening needs at least evolution proof for full complete; deck alone is playground
        if phase_id == MaturationPhase.AWAKENING.value and "evolution_proof_passed" not in hit:
            if "birth_certificate_issued" in reached:
                data["phase_records"][phase_id] = {
                    "status": "pending",
                    "learned": {},
                    "exit_proofs": hit,
                }
            continue
        if phase_id == MaturationPhase.PLAYGROUND.value:
            # deck_unlocked alone enough for MVP complete if birth artifacts ok
            if "deck_unlocked" in hit or "first_sim_order_placed" in hit:
                if phase_id not in completed:
                    completed.append(phase_id)
                data["phase_records"][phase_id] = {
                    "status": "completed",
                    "learned": {"milestones": hit},
                    "exit_proofs": hit,
                }
            continue
        if phase_id not in completed:
            completed.append(phase_id)
        data["phase_records"][phase_id] = {
            "status": "completed",
            "learned": {"milestones": hit},
            "exit_proofs": hit,
        }

    # Ordered unique completed
    order = [p.value for p in PHASE_ORDER]
    data["completed_phases"] = [p for p in order if p in set(completed)]
    data["updated_at"] = _c()._utcnow()
    try:
        _c().save_continuum(workspace_root, data)
    except Exception as exc:
        logger.debug("maturity.continuum.migrate_save_failed: %s", exc)
    return data

def wipe_phase_record(workspace_root: Path | str, phase: str) -> dict[str, Any]:
    data = _c().load_continuum(workspace_root)
    data["completed_phases"] = [p for p in (data.get("completed_phases") or []) if p != phase]
    if data.get("active_phase") == phase:
        data["active_phase"] = None
    if phase in (data.get("phase_records") or {}):
        data["phase_records"][phase] = {
            "status": "wiped",
            "wiped_at": _c()._utcnow(),
            "learned": {},
            "exit_proofs": [],
        }
    pending = data.get("pending_advance")
    if isinstance(pending, dict) and (
        pending.get("from") == phase or pending.get("to") == phase
    ):
        data["pending_advance"] = None
    _c().save_continuum(workspace_root, data)
    return data

def wipe_all_continuum(workspace_root: Path | str) -> dict[str, Any]:
    data = _c()._empty_continuum()
    # Keep genesis if setup complete
    try:
        setup = Path(workspace_root) / "state" / "lumina_setup_complete.json"
        if setup.is_file():
            data["completed_phases"] = [MaturationPhase.GENESIS.value]
            data["phase_records"][MaturationPhase.GENESIS.value] = {
                "status": "completed",
                "learned": {"note": "Setup retained after maturation wipe"},
                "exit_proofs": ["setup_complete"],
            }
    except Exception:
        pass
    _c().save_continuum(workspace_root, data)
    return data
