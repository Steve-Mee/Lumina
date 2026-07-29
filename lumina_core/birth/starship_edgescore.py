"""Starship Birth EdgeScore + entropy life-support helpers.

Canonical re-export: ``lumina_core.birth.starship_birth``.

Bounded modules: ``starship_edgescore_core``, ``starship_edgescore_champion``,
``starship_edgescore_stage1``, ``starship_edgescore_stage2``, ``starship_edgescore_stage3``.
"""
from __future__ import annotations

from lumina_core.birth.starship_edgescore_champion import (  # noqa: F401
    edgescore_champion_min_trades,
    humanize_edgescore_blocker,
    is_edgescore_champion_eligible,
    sanitize_edgescore_champion,
)
from lumina_core.birth.starship_edgescore_core import (  # noqa: F401
    EdgeScoreResult,
    compute_expectancy_proxy,
    gate_rolling_winrate,
    hygiene_wr_telemetry,
    policy_entropy_alive,
    read_last_ppo_entropy,
    rolling_pass_min_covered,
    rolling_wr_pass_eligible,
    should_force_exploration_burst,
)
from lumina_core.birth.starship_edgescore_stage1 import evaluate_stage1_edgescore  # noqa: F401
from lumina_core.birth.starship_edgescore_stage2 import evaluate_stage2_edgescore  # noqa: F401
from lumina_core.birth.starship_edgescore_stage3 import evaluate_stage3_edgescore  # noqa: F401

__all__ = [
    "EdgeScoreResult",
    "compute_expectancy_proxy",
    "edgescore_champion_min_trades",
    "evaluate_stage1_edgescore",
    "evaluate_stage2_edgescore",
    "evaluate_stage3_edgescore",
    "gate_rolling_winrate",
    "humanize_edgescore_blocker",
    "hygiene_wr_telemetry",
    "is_edgescore_champion_eligible",
    "policy_entropy_alive",
    "read_last_ppo_entropy",
    "rolling_pass_min_covered",
    "rolling_wr_pass_eligible",
    "sanitize_edgescore_champion",
    "should_force_exploration_burst",
]
