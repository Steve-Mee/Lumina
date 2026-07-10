"""Rolling holdout-proxy fitness for birth curriculum alignment."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.stage_scorecard import calculate_simple_slope


def should_run_oos_proxy(
    cumulative_trades: int,
    last_proxy_at_trades: int,
    *,
    cfg: BirthCurriculumConfig,
) -> bool:
    if not cfg.oos_proxy_enabled:
        return False
    interval = max(100, int(cfg.oos_proxy_interval_trades))
    return int(cumulative_trades) - int(last_proxy_at_trades) >= interval


def run_oos_proxy_eval(
    *,
    runtime: Any,
    holdout_ticks: list[dict[str, Any]],
    policy: Any,
    workspace_root: Any,
    constitution_guard: Any,
    cfg: BirthCurriculumConfig,
) -> dict[str, Any]:
    """Lightweight holdout rollout used as a curriculum fitness proxy."""
    sample_trades = max(20, int(cfg.oos_proxy_sample_trades))
    rollout = run_policy_rollout(
        runtime=runtime,
        data=holdout_ticks,
        policy=policy,
        target_trades=sample_trades,
        workspace_root=workspace_root,
        constitution_guard=constitution_guard,
    )
    winrate = float(rollout.wins) / float(max(1, rollout.trades))
    return {
        "oos_proxy_winrate": round(winrate, 4),
        "oos_proxy_trades": int(rollout.trades),
        "oos_proxy_violations": int(rollout.constitution_violations),
    }


def blended_learning_velocity(
    *,
    winrate_history: list[float],
    reward_history: list[float],
    oos_proxy_history: list[float],
    cfg: BirthCurriculumConfig,
) -> float:
    """Blend in-sample velocity with OOS proxy slope when samples exist."""
    from lumina_core.birth.stage_scorecard import combined_learning_velocity

    in_sample = combined_learning_velocity(winrate_history, reward_history)
    if not oos_proxy_history:
        return in_sample
    proxy_slope = calculate_simple_slope(oos_proxy_history)
    weight = max(0.0, min(1.0, float(cfg.oos_proxy_weight)))
    return (1.0 - weight) * in_sample + weight * proxy_slope