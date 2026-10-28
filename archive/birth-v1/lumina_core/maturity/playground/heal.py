"""Reopen a continuum Playground stamp that fails ADR-0050. Birth + Awakening stay intact."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import (
    OPERATOR_PHASES,
    load_continuum,
    save_continuum,
)

logger = get_logger("lumina.maturity.playground.heal")

LATER_THAN_PLAYGROUND = tuple(
    p for p in OPERATOR_PHASES if OPERATOR_PHASES.index(p) > OPERATOR_PHASES.index("playground")
)


def heal_playground_from_law(workspace_root: Path | str) -> dict[str, Any]:
    """If continuum lists playground completed but the law fails, reopen it.

    Does not touch Birth or Awakening artefacts.
    """
    root = Path(workspace_root)
    from lumina_core.maturity.playground.law import evaluate_playground_exit

    data = load_continuum(root)
    completed = list(data.get("completed_phases") or [])
    if "playground" not in completed:
        return {"ok": True, "healed": False, "reason": "not_marked_complete"}

    ok, missing, learned = evaluate_playground_exit(root)
    if ok:
        return {"ok": True, "healed": False, "reason": "law_still_passed"}

    kept = [p for p in completed if p != "playground" and p not in LATER_THAN_PLAYGROUND]
    data["completed_phases"] = [p for p in OPERATOR_PHASES if p in set(kept)]
    if data.get("active_phase") in {"playground", *LATER_THAN_PLAYGROUND}:
        data["active_phase"] = None
    rec = dict((data.get("phase_records") or {}).get("playground") or {})
    rec["status"] = "incomplete"
    rec["error"] = "playground_reopened_adr_0050:" + ",".join(missing[:8])
    rec["healed_from"] = "completed_without_law"
    rec["learned"] = {**(rec.get("learned") or {}), **learned}
    data.setdefault("phase_records", {})["playground"] = rec
    save_continuum(root, data)
    logger.warning("playground.heal.reopened missing=%s birth_awakening_intact=true", missing[:8])
    return {
        "ok": True,
        "healed": True,
        "missing": missing,
        "completed_phases": list(data.get("completed_phases") or []),
    }
