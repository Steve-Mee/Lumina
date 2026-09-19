"""S5 holdout probe is one-shot: no adaptive recovery circus on fail."""

from __future__ import annotations

from types import SimpleNamespace

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_loop_iteration_stagnation import StageLoopIterationStagnationMixin
from lumina_core.rl.ppo_device import _scale_timesteps_for_device


def test_scale_timesteps_does_not_double_on_any_device() -> None:
    assert _scale_timesteps_for_device(3000) == 3000
    assert _scale_timesteps_for_device(1) == 1


def test_s5_eval_only_max_rollouts_keeps_open_on_thin_policy() -> None:
    """Live 19:11: 50 volume / 44 policy must not freeze the holdout probe."""

    class Thin(StageLoopIterationStagnationMixin):
        def __init__(self) -> None:
            self.attempt = 1
            self.allow_provisional = False
            self.stage_trades = 50
            self.required = 50
            self._foundation_eval_only = True
            self.stage = CurriculumStage.STAGE5_PROBE_HANDOFF
            self.cur_cfg = SimpleNamespace()
            self.original_rollout_chunk = 250
            self.stage_started_at = 0.0
            self.stage_policy_trades = 44
            self.data_exhausted = False
            self.participation_last_mode = "PASSTHROUGH"
            self.s3_inband_idle_armed = False
            self.occupancy_control_flat = 0.2764
            self.stage_range_flat_bars = 2246
            self.stage_range_total_signals = 8127
            self.stage_val_pnl = []

        def _effective_max_rollouts(self) -> int:
            return 1

        def _would_certified_stage_stall(self, **kwargs: object) -> dict[str, str]:
            return {"failure_key": "policy_sample"}

        def _finalize_certified_stage_stall(self, *args: object, **kwargs: object) -> dict[str, str]:
            raise AssertionError("must not freeze while policy sample is thin")

        def _try_adaptive_stall_recovery(self, **kwargs: object) -> bool:
            raise AssertionError("must not recover")

    action, payload = Thin()._iteration_handle_max_rollouts()
    assert action == "continue"
    assert payload is None


def test_s5_eval_only_max_rollouts_freezes_without_recovery() -> None:
    calls: list[object] = []

    class Fake(StageLoopIterationStagnationMixin):
        def __init__(self) -> None:
            self.attempt = 1
            self.allow_provisional = False
            self.stage_trades = 150
            self.required = 50
            self._foundation_eval_only = True
            self.stage = CurriculumStage.STAGE5_PROBE_HANDOFF
            self.cur_cfg = SimpleNamespace()
            self.original_rollout_chunk = 250
            self.stage_started_at = 0.0
            self.stage_policy_trades = 150
            self.data_exhausted = False
            self.stage_val_pnl = []
            self.participation_last_mode = "PASSTHROUGH"
            self.s3_inband_idle_armed = False
            self.occupancy_control_flat = 0.50
            self.stage_range_flat_bars = 100
            self.stage_range_total_signals = 200

        def _effective_max_rollouts(self) -> int:
            return 1

        def _would_certified_stage_stall(self, **kwargs: object) -> dict[str, str]:
            return {"failure_key": "oos_sharpe"}

        def _finalize_certified_stage_stall(
            self, pending: dict[str, object], *, human_gate: bool = False
        ) -> dict[str, str]:
            calls.append(("finalize", dict(pending), human_gate))
            return {"status": "stage_stalled"}

        def _try_adaptive_stall_recovery(self, **kwargs: object) -> bool:
            calls.append("recovery")
            return True

    action, payload = Fake()._iteration_handle_max_rollouts()
    assert action == "return"
    assert payload == {"status": "stage_stalled"}
    assert calls[0][0] == "finalize"
    assert "recovery" not in calls


def test_s5_eval_only_skips_mine_expand_and_never_stop() -> None:
    from lumina_core.birth.stage_loop_data_cache import StageLoopDataCacheMixin
    from lumina_core.birth.stage_loop_recovery_adaptation import (
        StageLoopRecoveryAdaptationMixin,
    )

    class MineFake(StageLoopDataCacheMixin):
        def __init__(self) -> None:
            self._foundation_eval_only = True
            self.data_exhausted = False
            self.current_intra_sample_pool = [{"x": 1}]
            self.active_train = [{"x": 1}]
            self.active_stage_ticks = [{"x": 1}]
            self.hb = 0

        def _oracle_scan_heartbeat(self) -> None:
            self.hb += 1

    mine = MineFake()
    assert mine._mine_and_inject() == 0
    assert mine.hb == 0
    assert mine._maybe_expand_data() is False

    class RecovFake(StageLoopRecoveryAdaptationMixin):
        def __init__(self) -> None:
            self._foundation_eval_only = True
            self.cur_cfg = SimpleNamespace(adaptation_enabled=True, wall_behavior="adaptive")

        def _maybe_extend_trade_budget(self) -> bool:
            raise AssertionError("must not recover on S5")

    recov = RecovFake()
    assert recov._try_adaptive_stall_recovery(failure_key="x") is False
    assert recov._force_never_stop_recovery(failure_key="x") is False


def test_s5_dd_breach_freezes_before_max_rollouts() -> None:
    """Live 22:25: DD 62% of $50k after 13 holdout restarts — stop at 25%."""
    calls: list[object] = []

    class Dd(StageLoopIterationStagnationMixin):
        def __init__(self) -> None:
            self.attempt = 2
            self.allow_provisional = False
            self.stage_trades = 400
            self.required = 50
            self._foundation_eval_only = True
            self.stage = CurriculumStage.STAGE5_PROBE_HANDOFF
            self.cur_cfg = SimpleNamespace()
            self.original_rollout_chunk = 250
            self.stage_started_at = 0.0
            self.stage_policy_trades = 390
            self.data_exhausted = False
            self.participation_last_mode = "PASSTHROUGH"
            self.s3_inband_idle_armed = False
            self.occupancy_control_flat = 0.28
            self.stage_range_flat_bars = 100
            self.stage_range_total_signals = 400
            self.stage_val_pnl = [-500.0] * 30  # $15k / $50k = 30% DD

        def _effective_max_rollouts(self) -> int:
            return 200

        def _would_certified_stage_stall(self, **kwargs: object) -> dict[str, str]:
            raise AssertionError("dd gate must freeze before max-rollouts stall")

        def _finalize_certified_stage_stall(
            self, pending: dict[str, object], *, human_gate: bool = False
        ) -> dict[str, str]:
            calls.append(("finalize", dict(pending), human_gate))
            return {"status": "stage_stalled", "reason": str(pending.get("terminal_stall_reason"))}

        def _try_adaptive_stall_recovery(self, **kwargs: object) -> bool:
            raise AssertionError("must not recover on S5 DD breach")

    action, payload = Dd()._iteration_handle_max_rollouts()
    assert action == "return"
    assert payload is not None
    assert payload["reason"] == "s5_holdout_dd_exceeded"
    assert calls[0][1]["failure_key"] == "oos_dd"
    assert "recovery" not in str(calls)


def test_s5_tick_pool_ignores_escalation_and_advances_cursor() -> None:
    from lumina_core.birth.engine_trajectory import EngineTrajectoryMixin

    class Host(EngineTrajectoryMixin):
        birth_config = SimpleNamespace(curriculum=SimpleNamespace())

    host = Host()
    hold = [{"i": i} for i in range(10)]
    train = [{"t": i} for i in range(100)]
    kwargs = dict(
        stage=CurriculumStage.STAGE5_PROBE_HANDOFF,
        stage_ticks=hold,
        train_ticks=train,
        escalation_level=4,
        attempt=12,
    )
    assert host._stage_tick_pool(**kwargs) == hold
    host._s5_holdout_cursor = 4
    assert [row["i"] for row in host._stage_tick_pool(**kwargs)] == [4, 5, 6, 7, 8, 9]
