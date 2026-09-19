"""Reopen a continuum Awakening stamp that fails ADR-0049. Birth stays intact."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import (
    OPERATOR_PHASES,
    load_continuum,
    save_continuum,
)

logger = get_logger("lumina.maturity.awakening.heal")

LATER_THAN_AWAKENING = tuple(
    p for p in OPERATOR_PHASES if OPERATOR_PHASES.index(p) > OPERATOR_PHASES.index("awakening")
)


def heal_awakening_from_law(workspace_root: Path | str) -> dict[str, Any]:
    """If continuum lists awakening completed but the law fails, reopen it.

    Also supersedes a disk evolution-proof record that passed under
    ``effective_min_trades`` (n_B < 500). Does not touch Birth artefacts.
    """
    root = Path(workspace_root)
    proof_heal = _supersede_short_proof(root)
    from lumina_core.maturity.awakening.law import evaluate_awakening_exit

    data = load_continuum(root)
    completed = list(data.get("completed_phases") or [])
    if "awakening" not in completed:
        return {"ok": True, "healed": False, "reason": "not_marked_complete", **proof_heal}

    ok, missing, learned = evaluate_awakening_exit(root)
    if ok:
        return {"ok": True, "healed": False, "reason": "law_still_passed", **proof_heal}

    kept = [p for p in completed if p != "awakening" and p not in LATER_THAN_AWAKENING]
    data["completed_phases"] = [p for p in OPERATOR_PHASES if p in set(kept)]
    if data.get("active_phase") in {"awakening", *LATER_THAN_AWAKENING}:
        data["active_phase"] = None
    rec = dict((data.get("phase_records") or {}).get("awakening") or {})
    rec["status"] = "incomplete"
    rec["error"] = "awakening_reopened_adr_0049:" + ",".join(missing[:8])
    rec["healed_from"] = "completed_without_law"
    rec["learned"] = {**(rec.get("learned") or {}), **learned}
    data.setdefault("phase_records", {})["awakening"] = rec
    save_continuum(root, data)
    _scrub_false_evolution_proof_milestone(root)
    logger.warning(
        "awakening.heal.reopened missing=%s birth_intact=true",
        missing[:8],
    )
    return {
        "ok": True,
        "healed": True,
        "missing": missing,
        "completed_phases": list(data.get("completed_phases") or []),
        **proof_heal,
    }


def _supersede_short_proof(workspace_root: Path) -> dict[str, Any]:
    from lumina_core.birth.evolution_proof_gate import (
        N_B_MIN,
        load_evolution_proof_record,
        save_evolution_proof_record,
    )

    rec = load_evolution_proof_record(workspace_root)
    if not rec:
        return {"proof_superseded": False}
    n = int(rec.get("holdout_trades") or 0)
    if n >= N_B_MIN:
        return {"proof_superseded": False, "holdout_trades": n}
    if rec.get("superseded_by") == "adr_0049":
        _scrub_false_evolution_proof_milestone(workspace_root)
        return {"proof_superseded": False, "already_superseded": True, "holdout_trades": n}
    rec["historical_passed"] = bool(rec.get("passed"))
    rec["passed"] = False
    rec["superseded_by"] = "adr_0049"
    rec["supersede_reason"] = f"n_B={n} < {N_B_MIN}"
    save_evolution_proof_record(workspace_root, rec)
    _scrub_false_evolution_proof_milestone(workspace_root)
    return {"proof_superseded": True, "holdout_trades": n}


def _scrub_false_evolution_proof_milestone(workspace_root: Path) -> None:
    try:
        from lumina_core.maturity.maturation_progress import (
            load_maturation_progress,
            resolve_current_phase,
            save_maturation_progress,
        )
    except Exception:
        return
    progress = load_maturation_progress(workspace_root)
    if "evolution_proof_passed" not in progress.milestones_reached:
        return
    progress.milestones_reached = [
        m for m in progress.milestones_reached if m != "evolution_proof_passed"
    ]
    progress.metadata.pop("evolution_proof_passed", None)
    progress.current_phase = resolve_current_phase(progress)
    save_maturation_progress(workspace_root, progress)
