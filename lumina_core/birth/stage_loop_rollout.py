"""Stage loop rollout — thin orchestration entrypoint.

Heavy logic: stage_loop_session + plateau/recovery/progress/meta/data_ops mixins
via BirthBusClient handlers.
"""
from __future__ import annotations

import time

from lumina_core.birth.data_expansion import expand_birth_data
from lumina_core.birth.pattern_miner import mine_winning_patterns
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.stage_loop_session import run_stage_research_loop

__all__ = [
    "expand_birth_data",
    "mine_winning_patterns",
    "run_policy_rollout",
    "run_stage_research_loop",
    "time",
]
