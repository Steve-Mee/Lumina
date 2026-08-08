"""Wipe single maturation phase or all post-genesis progress (fail-closed)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import (
    load_continuum,
    wipe_all_continuum,
    wipe_phase_record,
)
from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
    load_maturation_progress,
    save_maturation_progress,
)

logger = get_logger("lumina.maturity.wipe")

# Milestones owned primarily by each phase (best-effort scrub).
_PHASE_MILESTONES: dict[str, tuple[str, ...]] = {
    MaturationPhase.BIRTH.value: (
        "birth_started",
        "birth_certificate_issued",
    ),
    MaturationPhase.AWAKENING.value: (
        "evolution_proof_passed",
        "perfect_birth_autonomy_proven",
    ),
    MaturationPhase.PLAYGROUND.value: (
        "deck_unlocked",
        "first_sim_order_placed",
        "sim_mirror_api_ok",
    ),
    MaturationPhase.APPRENTICESHIP.value: ("sim_real_guard_stable",),
    MaturationPhase.PROVING_GROUND.value: (
        "shadow_validation_passed",
        "promotion_gate_passed",
    ),
    MaturationPhase.REAL.value: ("human_real_approval", "real_trading_live"),
}


def wipe_phase(workspace_root: Path | str, phase: str, *, confirm: bool) -> dict[str, Any]:
    if not confirm:
        return {"ok": False, "error": "confirm=true required"}
    root = Path(workspace_root)
    phase = str(phase or "").strip().lower()
    if phase not in _PHASE_MILESTONES and phase != MaturationPhase.GENESIS.value:
        return {"ok": False, "error": f"unknown phase: {phase}"}

    removed: list[str] = []

    if phase == MaturationPhase.BIRTH.value:
        try:
            from lumina_launcher.services.birth_service import BirthService

            svc = BirthService()
            svc.configure_workspace(root)
            result = svc.wipe_all_birth_data(preserve_tick_cache=True)
            removed.append(f"birth_wipe:{result.get('status')}")
        except Exception as exc:
            logger.warning("maturity.wipe.birth_failed: %s", exc)
            removed.append(f"birth_wipe_error:{exc}")

    # Scrub milestones for this phase and later phases if cascading birth wipe
    progress = load_maturation_progress(root)
    drop = set(_PHASE_MILESTONES.get(phase, ()))
    if phase == MaturationPhase.BIRTH.value:
        # Cascade later phase milestones — birth wipe invalidates later ladder
        for later in (
            MaturationPhase.AWAKENING.value,
            MaturationPhase.PLAYGROUND.value,
            MaturationPhase.APPRENTICESHIP.value,
            MaturationPhase.PROVING_GROUND.value,
            MaturationPhase.REAL.value,
        ):
            drop.update(_PHASE_MILESTONES.get(later, ()))
            wipe_phase_record(root, later)
    progress.milestones_reached = [m for m in progress.milestones_reached if m not in drop]
    for mid in drop:
        progress.metadata.pop(mid, None)
    from lumina_core.maturity.maturation_progress import resolve_current_phase

    progress.current_phase = resolve_current_phase(progress)
    save_maturation_progress(root, progress)

    continuum = wipe_phase_record(root, phase)
    if phase == MaturationPhase.BIRTH.value:
        # Also remove later from completed
        continuum = load_continuum(root)
        keep = {"genesis"}
        continuum["completed_phases"] = [p for p in continuum.get("completed_phases") or [] if p in keep or p == "genesis"]
        # re-add genesis if setup
        if MaturationPhase.GENESIS.value not in continuum["completed_phases"]:
            continuum["completed_phases"].insert(0, MaturationPhase.GENESIS.value)
        from lumina_core.maturity.continuum import save_continuum

        save_continuum(root, continuum)

    logger.info("maturity.wipe_phase phase=%s removed_milestones=%s", phase, sorted(drop))
    return {
        "ok": True,
        "phase": phase,
        "removed_milestones": sorted(drop),
        "continuum": continuum,
        "details": removed,
    }


def wipe_all_maturation(workspace_root: Path | str, *, confirm: bool) -> dict[str, Any]:
    if not confirm:
        return {"ok": False, "error": "confirm=true required"}
    root = Path(workspace_root)
    # Birth wipe
    birth_result: dict[str, Any] = {}
    try:
        from lumina_launcher.services.birth_service import BirthService

        svc = BirthService()
        svc.configure_workspace(root)
        birth_result = svc.wipe_all_birth_data(preserve_tick_cache=False)
    except Exception as exc:
        birth_result = {"error": str(exc)}

    # Reset milestones (keep empty / genesis only)
    progress = load_maturation_progress(root)
    progress.milestones_reached = []
    progress.metadata = {}
    from lumina_core.maturity.maturation_progress import MaturationPhase as MP

    progress.current_phase = MP.GENESIS
    save_maturation_progress(root, progress)

    continuum = wipe_all_continuum(root)
    logger.info("maturity.wipe_all ok")
    return {"ok": True, "birth": birth_result, "continuum": continuum}
