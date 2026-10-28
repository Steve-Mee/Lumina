"""Stage rollout executor — thin delegate to stage_loop_rollout."""

from __future__ import annotations

from lumina_core.birth import stage_loop_rollout as _impl
from lumina_core.birth.stage_loop_rollout import (
    expand_birth_data,
    mine_winning_patterns,
    run_policy_rollout,
    run_stage_research_loop,
)

time = _impl.time

__all__ = [
    "expand_birth_data",
    "mine_winning_patterns",
    "run_policy_rollout",
    "run_stage_research_loop",
    "time",
]
