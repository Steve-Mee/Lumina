"""Stage-4 mean-R vs mechanical EV — capture controller (ADR-0046).

S4 grades mean R ≥ E_mech − 0.10 on the validation slice. Meta must not HOLD
while that gap is open: HOLD freezes exits that already fail to capture
geometric target R. This module never loosens the slack.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from lumina_core.birth.config_curriculum import BirthRewardConfig
from lumina_core.birth.foundation_metrics import S4_MEAN_R_SLACK


def stage4_mean_r_failing(
    mean_r: float | None,
    e_mech: float | None,
    *,
    slack: float = S4_MEAN_R_SLACK,
) -> bool:
    if mean_r is None or e_mech is None:
        return False
    return float(mean_r) + 1e-12 < float(e_mech) - float(slack)


def stage4_mean_r_gap(
    mean_r: float | None,
    e_mech: float | None,
    *,
    slack: float = S4_MEAN_R_SLACK,
) -> float | None:
    if mean_r is None or e_mech is None:
        return None
    return float(e_mech) - float(slack) - float(mean_r)


def stage4_mean_r_reward_tweak(
    active: BirthRewardConfig,
    *,
    step: float,
    cap: float,
) -> BirthRewardConfig:
    """Raise expectancy + win-capture bonus. Never lowers a coeff."""
    new_coeff = min(float(cap), float(active.expectancy_coeff) + max(0.0, float(step)))
    new_bonus = min(0.50, float(active.quality_win_bonus_coeff) + 0.05)
    return replace(
        active,
        expectancy_coeff=max(float(active.expectancy_coeff), new_coeff),
        quality_win_bonus_coeff=max(float(active.quality_win_bonus_coeff), new_bonus),
    )


def stage4_mean_r_meta_fields(
    *,
    exploration_steps: int,
    strong_recovery_explore_fraction: float,
) -> dict[str, Any]:
    explore = max(200, int(float(exploration_steps) * float(strong_recovery_explore_fraction)))
    return {
        "primary": "reward_shaping_tweak",
        "secondary": ["explore_reduce"],
        "explore_steps": explore,
        "escalation_delta": 1,
        "mine": False,
        "rationale": "stage4_mean_r_capture",
    }


def stage4_mean_r_pre_rollout_fields(
    snap: Any,
    *,
    exploration_steps: int,
    strong_recovery_explore_fraction: float,
    reward_tweak_step: float,
    reward_tweak_cap: float,
    active_reward: Any,
) -> dict[str, Any] | None:
    """None when mean-R already clears slack. Never lowers floors."""
    if not stage4_mean_r_failing(getattr(snap, "mean_r", None), getattr(snap, "e_mech", None)):
        return None
    fields = dict(
        stage4_mean_r_meta_fields(
            exploration_steps=int(exploration_steps),
            strong_recovery_explore_fraction=float(strong_recovery_explore_fraction),
        )
    )
    try:
        fields["reward_tweak"] = stage4_mean_r_reward_tweak(
            active_reward,
            step=float(reward_tweak_step),
            cap=float(reward_tweak_cap),
        )
    except Exception:
        fields["reward_tweak"] = None
    return fields


__all__ = [
    "stage4_mean_r_failing",
    "stage4_mean_r_gap",
    "stage4_mean_r_meta_fields",
    "stage4_mean_r_pre_rollout_fields",
    "stage4_mean_r_reward_tweak",
]
