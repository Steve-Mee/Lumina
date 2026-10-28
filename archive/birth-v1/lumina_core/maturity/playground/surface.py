"""When the operator should inhabit Playground (Command Deck) instead of Phase Hub."""
from __future__ import annotations

from pathlib import Path

from lumina_core.maturity.continuum import load_continuum
from lumina_core.maturity.playground.progress import load_playground_progress

HABITAT_STATUSES = frozenset({"running", "failed", "incomplete"})


def playground_habitat_wanted(workspace_root: Path | str) -> tuple[bool, str]:
    """True once Playground has started and is not completed. Never-started stays hub."""
    root = Path(workspace_root)
    data = load_continuum(root)
    completed = list(data.get("completed_phases") or [])
    if "playground" in completed:
        return False, "playground_complete"
    if "awakening" not in completed:
        return False, "awakening_pending"
    if data.get("active_phase") == "playground":
        return True, "playground_running"
    rec = dict((data.get("phase_records") or {}).get("playground") or {})
    status = str(rec.get("status") or "")
    if status in HABITAT_STATUSES:
        return True, "playground_incomplete"
    if load_playground_progress(root):
        return True, "playground_incomplete"
    return False, "playground_pending"
