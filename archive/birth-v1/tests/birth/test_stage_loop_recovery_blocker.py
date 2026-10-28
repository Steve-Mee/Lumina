"""Certified stall blocker must use live process-R, never hollow None/days=0."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_loop_recovery_blocker import fill_pending_stage_blocker


class _Loop:
    def __init__(self) -> None:
        self.stage = CurriculumStage.STAGE4_VIABLE_PLANT
        self.stage_trades = 628
        self.stage_wins = 222
        self.stage_hold_signals = 66814
        self.stage_total_signals = 68036
        self.stage_range_flat_bars = 16980
        self.stage_range_round_trips = 628
        self.stage_range_total_signals = 68036
        self.required = 100
        self.cur_cfg = BirthCurriculumConfig()
        self.stage_val_r = [-1.2] * 300 + [1.1] * 222
        self.stage_val_pnl = [-80.0] * 300 + [28.0] * 222
        self.stage_policy_trades = 628
        self.stage_policy_wins = 222
        self.stage_plant_trades = 0
        self.stage_plant_wins = 0
        self._unique_calendar_days = 186
        self.stage_ticks = [{"ts": i} for i in range(10)]
        self._first_touch_target_hit_rate = 0.2966
        self._birth_trade_geometry = SimpleNamespace(
            stop_pct=0.000497,
            ref_price=7706.75,
            net_rr_after_cost=1.1533,
        )
        self.host = SimpleNamespace(
            ppo_steps=398000,
            _constitution_guard=SimpleNamespace(violations=0),
        )

    def _resolve_policy_entropy(self) -> float:
        return 6.49


@pytest.mark.unit
def test_fill_pending_replaces_hollow_none_days_zero() -> None:
    pending = fill_pending_stage_blocker(
        _Loop(),
        {
            "failure_key": "stage_stalled",
            "blocker_metric": "median_loss_r",
            "blocker_value": 0.0,
            "blocker_reason": (
                "foundation_fail:median_loss_r=None missing_or_gt_1.5;"
                "occupancy=0.24957 not_in_25%-75%;replay_cap trades=628 days=0"
            ),
        },
    )
    reason = str(pending.get("blocker_reason") or "")
    assert "None" not in reason
    assert "days=0" not in reason
    assert "occupancy" in reason or pending.get("blocker_metric") == "occupancy"
