"""BirthControlPlane — thin façade over Starship Birth predicates (Phase B4 + gap-fill).

Call-sites import from here so swarm-first / freeze / lift / twin-continue /
pause SSOT stay one hop from SSOT implementations in ``starship_birth``.
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_birth import (
    build_pause_ssot_payload,
    effective_plateau_max_evolution_steps,
    should_block_phoenix_until_swarm,
    should_force_swarm_retearnament,
    should_hard_stop_training_after_swarm_reject,
    should_skip_plateau_ladder_theater,
    should_start_swarm_before_recovery,
    swarm_edgescore_lift,
    swarm_tournament_done,
    swarm_tournament_lift,
    tournament_lift_required_delta,
    tournament_score,
    write_pause_ssot,
)

__all__ = [
    "build_pause_ssot_payload",
    "effective_plateau_max_evolution_steps",
    "fail_closed_missing_frozen_windows",
    "require_frozen_windows_or_fail",
    "should_block_phoenix_until_swarm",
    "should_force_swarm_retearnament",
    "should_hard_stop_training_after_swarm_reject",
    "should_skip_plateau_ladder_theater",
    "should_start_swarm_before_recovery",
    "swarm_edgescore_lift",
    "swarm_tournament_done",
    "swarm_tournament_lift",
    "swarm_tournament_resolved",
    "twin_continue_eligible",
    "tournament_lift_required_delta",
    "tournament_score",
    "write_pause_ssot",
]


def swarm_tournament_resolved(
    *,
    swarm_state: Any,
    host_champion_accepted: bool = False,
    host_committed: bool = False,
) -> bool:
    """CONTINUE-eligible resolution: commit or champion_accepted only (not reject)."""
    if host_champion_accepted or bool(getattr(swarm_state, "champion_accepted", False)):
        return True
    if host_committed:
        return True
    committed = str(getattr(swarm_state, "committed_variant_id", "") or "").strip()
    return bool(committed)


def require_frozen_windows_or_fail(swarm_state: Any) -> bool:
    """True when active swarm has usable in-memory frozen windows."""
    if swarm_state is None or not bool(getattr(swarm_state, "active", False)):
        return True
    windows = getattr(swarm_state, "frozen_tick_windows", None) or []
    return bool(windows) and any(bool(w) for w in windows)


def fail_closed_missing_frozen_windows(swarm_state: Any, *, host: Any | None = None) -> bool:
    """Deactivate + reject when swarm is active without frozen windows.

    Returns True when fail-closed was applied (caller must not use fresh tick pools).
    """
    if require_frozen_windows_or_fail(swarm_state):
        return False
    swarm_state.active = False
    swarm_state.rejected_no_lift = True
    if host is not None:
        try:
            host.swarm_rejected_no_lift = True
        except Exception:
            pass
    return True


def twin_continue_eligible(
    *,
    cfg: BirthCurriculumConfig,
    twin_mode: str,
    twin_executable: bool,
    twin_confidence: float,
    swarm_resolved: bool,
    constitution_risks: bool,
) -> bool:
    """CONTINUE only when full_auto + executable + swarm resolved + clean."""
    if not bool(getattr(cfg, "starship_twin_continue_when_full_auto", True)):
        return False
    if str(twin_mode or "").strip().lower() != "full_auto":
        return False
    if not bool(twin_executable):
        return False
    if float(twin_confidence) < 0.80:
        return False
    if not swarm_resolved:
        return False
    if constitution_risks:
        return False
    return True
