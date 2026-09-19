"""Reopen a continuum Proving Ground stamp that fails ADR-0052. Earlier phases stay intact."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import (
    OPERATOR_PHASES,
    load_continuum,
    save_continuum,
)

logger = get_logger("lumina.maturity.proving_ground.heal")

LATER_THAN_PROVING_GROUND = tuple(
    p
    for p in OPERATOR_PHASES
    if OPERATOR_PHASES.index(p) > OPERATOR_PHASES.index("proving_ground")
)


def heal_proving_ground_from_law(workspace_root: Path | str) -> dict[str, Any]:
    """If continuum lists proving_ground completed but the law fails, reopen it.

    Does not touch Genesis, Birth, Awakening, Playground, or Apprenticeship artefacts.
    """
    root = Path(workspace_root)
    from lumina_core.maturity.proving_ground.law import evaluate_proving_ground_exit

    data = load_continuum(root)
    completed = list(data.get("completed_phases") or [])
    if "proving_ground" not in completed:
        return {"ok": True, "healed": False, "reason": "not_marked_complete"}

    ok, missing, learned = evaluate_proving_ground_exit(root)
    if ok:
        return {"ok": True, "healed": False, "reason": "law_still_passed"}

    kept = [p for p in completed if p != "proving_ground" and p not in LATER_THAN_PROVING_GROUND]
    data["completed_phases"] = [p for p in OPERATOR_PHASES if p in set(kept)]
    if data.get("active_phase") in {"proving_ground", *LATER_THAN_PROVING_GROUND}:
        data["active_phase"] = None
    rec = dict((data.get("phase_records") or {}).get("proving_ground") or {})
    rec["status"] = "incomplete"
    rec["error"] = "proving_ground_reopened_adr_0052:" + ",".join(missing[:8])
    rec["healed_from"] = "completed_without_law"
    rec["learned"] = {**(rec.get("learned") or {}), **learned}
    data.setdefault("phase_records", {})["proving_ground"] = rec
    save_continuum(root, data)
    _scrub_false_promotion_milestones(root)
    logger.warning(
        "proving_ground.heal.reopened missing=%s earlier_phases_intact=true",
        missing[:8],
    )
    return {
        "ok": True,
        "healed": True,
        "missing": missing,
        "completed_phases": list(data.get("completed_phases") or []),
    }


def _scrub_false_promotion_milestones(workspace_root: Path) -> None:
    try:
        from lumina_core.maturity.maturation_progress import (
            load_maturation_progress,
            resolve_current_phase,
            save_maturation_progress,
        )
    except Exception:
        return
    progress = load_maturation_progress(workspace_root)
    drop = {"shadow_validation_passed", "promotion_gate_passed"}
    if not drop.intersection(progress.milestones_reached):
        return
    progress.milestones_reached = [m for m in progress.milestones_reached if m not in drop]
    for mid in drop:
        progress.metadata.pop(mid, None)
    progress.current_phase = resolve_current_phase(progress)
    save_maturation_progress(workspace_root, progress)
