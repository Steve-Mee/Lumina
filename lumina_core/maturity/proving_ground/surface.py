"""When the operator should see the Proving Ground cinematic instead of Phase Hub."""
from __future__ import annotations

from pathlib import Path

from lumina_core.maturity.continuum import load_continuum
from lumina_core.maturity.proving_ground.progress import load_proving_ground_progress

CINEMATIC_STATUSES = frozenset({"running", "failed", "incomplete"})


def proving_ground_cinematic_wanted(workspace_root: Path | str) -> tuple[bool, str]:
    """True once Proving Ground has started and is not completed. Never-started stays hub."""
    root = Path(workspace_root)
    data = load_continuum(root)
    completed = list(data.get("completed_phases") or [])
    if "proving_ground" in completed:
        return False, "proving_ground_complete"
    if "apprenticeship" not in completed:
        return False, "apprenticeship_pending"
    if data.get("active_phase") == "proving_ground":
        return True, "proving_ground_running"
    rec = dict((data.get("phase_records") or {}).get("proving_ground") or {})
    status = str(rec.get("status") or "")
    if status in CINEMATIC_STATUSES:
        return True, "proving_ground_incomplete"
    if load_proving_ground_progress(root):
        return True, "proving_ground_incomplete"
    return False, "proving_ground_pending"
