"""Reset the current curriculum-stage sample after airframe-poisoned trades.

Keeps stages_passed, tape, expansion_step, and cumulative budget spent.
Zeros occupancy IMU, skill clocks, and swarm-no-lift flags that belonged
to the poisoned sample. Never lowers pass floors.
"""

from __future__ import annotations

from typing import Any

_ZERO_INT_KEYS = (
    "stage_trades",
    "stage_wins",
    "stage_hold_signals",
    "stage_total_signals",
    "stage_range_hold_signals",
    "stage_range_total_signals",
    "stage_range_flat_bars",
    "stage_range_round_trips",
    "stage_policy_trades",
    "stage_policy_wins",
    "stage_plant_trades",
    "stage_plant_wins",
    "skill_metric_trades",
    "skill_metric_wins",
    "participation_force_exit",
    "participation_force_open",
    "participation_force_hold",
    "participation_force_flat",
    "participation_passthrough",
    "participation_overrides_total",
    "passthrough_range_flat_bars",
    "passthrough_range_total_signals",
    "exam_passthrough_flat_bars",
    "exam_passthrough_total_signals",
    "closes_stop",
    "closes_target",
    "closes_flatten",
    "closes_time_stop",
    "closes_unknown",
    "stage_closes_stop_cum",
    "stage_closes_target_cum",
    "stage_closes_flatten_cum",
    "stage_closes_time_stop_cum",
    "stage_closes_unknown_cum",
)

_CLEAR_LIST_KEYS = (
    "winrate_history",
    "stage_val_pnl",
    "stage_val_r",
    "reward_history",
    "rolling_trade_chunks",
    "adaptation_history",
)

_CLEAR_DICT_KEYS = ("wins_at_trade_milestones", "occupancy_exam_window")

_CLEAR_OPTIONAL_KEYS = (
    "occupancy",
    "occupancy_control_flat",
    "envelope_override_fraction",
    "airframe_override_fraction",
    "edge_vs_first_touch",
    "mean_r",
    "median_loss_r",
    "pass_reason",
    "stage_blocker_metric",
    "stage_blocker_value",
)


def reset_current_stage_sample(metrics: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy of stage_metrics with the current-stage sample zeroed."""
    out = dict(metrics or {})
    retries = max(0, int(out.get("retries_this_stage", 0) or 0)) + 1
    for key in _ZERO_INT_KEYS:
        if key in out:
            out[key] = 0
    for key in _CLEAR_LIST_KEYS:
        if key in out:
            out[key] = []
    for key in _CLEAR_DICT_KEYS:
        if key in out:
            out[key] = {} if key != "occupancy_exam_window" else None
    for key in _CLEAR_OPTIONAL_KEYS:
        if key in out:
            out[key] = None
    out["occupancy_exam_armed"] = False
    out["swarm_rejected_no_lift"] = False
    out["policy_swarm_rejected_no_lift"] = False
    out["swarm_champion_accepted"] = False
    out["policy_swarm_champion_accepted"] = False
    out["pending_data_expand"] = False
    out["phoenix_cycle"] = False
    out["stage_sample_reset"] = True
    out["stage_sample_reset_reason"] = "occupancy_fencepost"
    out["retries_this_stage"] = retries
    return out


__all__ = ["reset_current_stage_sample"]
