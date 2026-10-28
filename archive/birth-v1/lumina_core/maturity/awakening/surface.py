"""When the operator should see the Awakening mission instead of Phase Hub."""
from __future__ import annotations

from pathlib import Path

from lumina_core.maturity.awakening.progress import load_awakening_progress
from lumina_core.maturity.continuum import load_continuum

CINEMATIC_STATUSES = frozenset({"running", "failed", "incomplete"})


def awakening_cinematic_wanted(workspace_root: Path | str) -> tuple[bool, str]:
    """True once Awakening has started and is not completed.

    Never-started stays on Phase Hub (ADR-0036 ``hub_after_exit``). The operator
    starts First Watch from that charter. First Watch is the living mission, or
    the screen after a real incomplete or failed attempt — not a Retry for a
    phase that has not been started.
    """
    root = Path(workspace_root)
    data = load_continuum(root)
    completed = list(data.get("completed_phases") or [])
    if "awakening" in completed:
        return False, "awakening_complete"
    if data.get("active_phase") == "awakening":
        return True, "awakening_running"
    rec = dict((data.get("phase_records") or {}).get("awakening") or {})
    status = str(rec.get("status") or "")
    if status in CINEMATIC_STATUSES:
        return True, "awakening_incomplete"
    if load_awakening_progress(root):
        return True, "awakening_incomplete"
    return False, "awakening_pending"
