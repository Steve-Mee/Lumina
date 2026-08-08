"""StageLoopSessionRunnerMixin — session.run() body (Wave H AST phases).

Sequential: init → resume → prepare → _run_main_loop.
Early returns from phases propagate.
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.stage_loop_session_phase_init import SessionPhaseInitMixin
from lumina_core.birth.stage_loop_session_phase_resume import SessionPhaseResumeMixin
from lumina_core.birth.stage_loop_session_phase_prepare import SessionPhasePrepareMixin

__all__ = ["StageLoopSessionRunnerMixin"]


class StageLoopSessionRunnerMixin(
    SessionPhaseInitMixin,
    SessionPhaseResumeMixin,
    SessionPhasePrepareMixin,
):
    """Owns StageLoopSession.run(); see StageLoopSession for attributes."""

    def run(self) -> dict[str, Any] | None:
        early = self._session_phase_init()
        if early is not None:
            return early
        early = self._session_phase_resume()
        if early is not None:
            return early
        return self._session_phase_prepare()
