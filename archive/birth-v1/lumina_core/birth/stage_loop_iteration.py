"""Main stage-loop iteration facade (god-surface split).

Implementation lives in ``stage_loop_iteration_core`` plus pure helpers
(``stage_loop_iteration_helpers``, ``stage_loop_iteration_swarm``).
"""
from __future__ import annotations

from lumina_core.birth.stage_loop_iteration_core import StageLoopIterationMixin

__all__ = ["StageLoopIterationMixin"]
