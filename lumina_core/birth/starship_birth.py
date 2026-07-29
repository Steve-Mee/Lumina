"""Starship Birth Phase A — EdgeScore, entropy life-support, swarm-first gates.

SIM/birth learning gates only. Certificate OOS thresholds remain untouched.

Bounded modules: ``starship_edgescore``, ``starship_swarm_gates``.
"""
from __future__ import annotations

from lumina_core.birth.starship_edgescore import (  # noqa: F401
    EdgeScoreResult,
    compute_expectancy_proxy,
    edgescore_champion_min_trades,
    evaluate_stage1_edgescore,
    evaluate_stage2_edgescore,
    evaluate_stage3_edgescore,
    gate_rolling_winrate,
    humanize_edgescore_blocker,
    hygiene_wr_telemetry,
    is_edgescore_champion_eligible,
    policy_entropy_alive,
    read_last_ppo_entropy,
    rolling_pass_min_covered,
    rolling_wr_pass_eligible,
    sanitize_edgescore_champion,
    should_force_exploration_burst,
)
from lumina_core.birth.starship_swarm_gates import (  # noqa: F401
    build_pause_ssot_payload,
    edgescore_from_swarm_result,
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
    "EdgeScoreResult",
    "build_pause_ssot_payload",
    "compute_expectancy_proxy",
    "edgescore_champion_min_trades",
    "edgescore_from_swarm_result",
    "effective_plateau_max_evolution_steps",
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
    "should_block_phoenix_until_swarm",
    "should_force_exploration_burst",
    "should_force_swarm_retearnament",
    "should_hard_stop_training_after_swarm_reject",
    "should_skip_plateau_ladder_theater",
    "should_start_swarm_before_recovery",
    "swarm_edgescore_lift",
    "swarm_tournament_done",
    "swarm_tournament_lift",
    "tournament_lift_required_delta",
    "tournament_score",
    "write_pause_ssot",
]
