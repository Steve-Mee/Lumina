"""_session_phase_prepare extracted from StageLoopSessionRunnerMixin.run (M5 façade)."""
from __future__ import annotations

from lumina_core.birth.stage_loop_session_phase_prepare_init import SessionPhasePrepareInitMixin
from lumina_core.birth.stage_loop_session_phase_prepare_plateau import (
    SessionPhasePreparePlateauMixin,
)
from lumina_core.birth.stage_loop_session_phase_prepare_restore import (
    SessionPhasePrepareRestoreMixin,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_session_runner")

__all__ = ["SessionPhasePrepareMixin"]


class SessionPhasePrepareMixin(
    SessionPhasePrepareRestoreMixin,
    SessionPhasePreparePlateauMixin,
    SessionPhasePrepareInitMixin,
):
    """Sequential phase _session_phase_prepare."""

    def _session_phase_prepare(self):
        self._prepare_restore_bus_and_progress()
        self._prepare_restore_plateau_swarm()
        self._prepare_init_pools_and_research()
        return self._run_main_loop()
