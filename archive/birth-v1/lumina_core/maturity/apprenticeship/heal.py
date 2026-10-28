"""Reopen a continuum Apprenticeship stamp that fails ADR-0051. Earlier phases stay intact."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import (
    OPERATOR_PHASES,
    load_continuum,
    save_continuum,
)

logger = get_logger("lumina.maturity.apprenticeship.heal")

LATER_THAN_APPRENTICESHIP = tuple(
    p
    for p in OPERATOR_PHASES
    if OPERATOR_PHASES.index(p) > OPERATOR_PHASES.index("apprenticeship")
)


def heal_apprenticeship_from_law(workspace_root: Path | str) -> dict[str, Any]:
    """If continuum lists apprenticeship completed but the law fails, reopen it.

    Does not touch Genesis, Birth, Awakening, or Playground artefacts.
    """
    root = Path(workspace_root)
    from lumina_core.maturity.apprenticeship.law import evaluate_apprenticeship_exit

    data = load_continuum(root)
    completed = list(data.get("completed_phases") or [])
    if "apprenticeship" not in completed:
        return {"ok": True, "healed": False, "reason": "not_marked_complete"}

    ok, missing, learned = evaluate_apprenticeship_exit(root)
    if ok:
        return {"ok": True, "healed": False, "reason": "law_still_passed"}

    kept = [p for p in completed if p != "apprenticeship" and p not in LATER_THAN_APPRENTICESHIP]
    data["completed_phases"] = [p for p in OPERATOR_PHASES if p in set(kept)]
    if data.get("active_phase") in {"apprenticeship", *LATER_THAN_APPRENTICESHIP}:
        data["active_phase"] = None
    rec = dict((data.get("phase_records") or {}).get("apprenticeship") or {})
    rec["status"] = "incomplete"
    rec["error"] = "apprenticeship_reopened_adr_0051:" + ",".join(missing[:8])
    rec["healed_from"] = "completed_without_law"
    rec["learned"] = {**(rec.get("learned") or {}), **learned}
    data.setdefault("phase_records", {})["apprenticeship"] = rec
    save_continuum(root, data)
    _scrub_false_ready_milestone(root)
    logger.warning(
        "apprenticeship.heal.reopened missing=%s earlier_phases_intact=true",
        missing[:8],
    )
    return {
        "ok": True,
        "healed": True,
        "missing": missing,
        "completed_phases": list(data.get("completed_phases") or []),
    }


def _scrub_false_ready_milestone(workspace_root: Path) -> None:
    try:
        from lumina_core.maturity.maturation_progress import (
            load_maturation_progress,
            resolve_current_phase,
            save_maturation_progress,
        )
    except Exception:
        return
    progress = load_maturation_progress(workspace_root)
    if "sim_real_guard_stable" not in progress.milestones_reached:
        return
    progress.milestones_reached = [
        m for m in progress.milestones_reached if m != "sim_real_guard_stable"
    ]
    progress.metadata.pop("sim_real_guard_stable", None)
    progress.current_phase = resolve_current_phase(progress)
    save_maturation_progress(workspace_root, progress)
