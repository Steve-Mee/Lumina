"""When the operator should see the Apprenticeship cinematic instead of Phase Hub."""
from __future__ import annotations

from pathlib import Path

from lumina_core.maturity.apprenticeship.progress import load_apprenticeship_progress
from lumina_core.maturity.continuum import load_continuum

CINEMATIC_STATUSES = frozenset({"running", "failed", "incomplete"})


def apprenticeship_cinematic_wanted(workspace_root: Path | str) -> tuple[bool, str]:
    """True once Apprenticeship has started and is not completed. Never-started stays hub."""
    root = Path(workspace_root)
    data = load_continuum(root)
    completed = list(data.get("completed_phases") or [])
    if "apprenticeship" in completed:
        return False, "apprenticeship_complete"
    if "playground" not in completed:
        return False, "playground_pending"
    if data.get("active_phase") == "apprenticeship":
        return True, "apprenticeship_running"
    rec = dict((data.get("phase_records") or {}).get("apprenticeship") or {})
    status = str(rec.get("status") or "")
    if status in CINEMATIC_STATUSES:
        return True, "apprenticeship_incomplete"
    if load_apprenticeship_progress(root):
        return True, "apprenticeship_incomplete"
    return False, "apprenticeship_pending"
