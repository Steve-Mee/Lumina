"""Phase-2 stall remediation ladder tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.stall_remediation import (
    HUMAN_GATE_REASON,
    PHOENIX_CYCLE_REASON,
    StallRemediationAction,
    StallRemediationState,
    action_for_step,
    begin_remediation_cycle,
    can_start_remediation,
    curate_buffer_bottom_half,
    curate_buffer_top_quartile,
    is_remediation_exhausted,
    should_run_remediation_instead_of_human_gate,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = dict(
        stall_remediation_enabled=True,
        stall_remediation_max_cycles=1,
        stall_remediation_max_steps=4,
        stall_remediation_rollouts_per_step=12,
        velocity_stall_epsilon=0.002,
    )
    base.update(overrides)
    return BirthCurriculumConfig(**base)


@pytest.mark.unit
def test_can_start_remediation_once() -> None:
    state = StallRemediationState()
    cfg = _cfg()
    assert can_start_remediation(state, cfg=cfg) is True
    begin_remediation_cycle(state, stage_trades=300, stage_wins=100)
    assert state.remediation_cycle == 1
    assert can_start_remediation(state, cfg=cfg) is False


@pytest.mark.unit
def test_remediation_ladder_actions() -> None:
    assert action_for_step(1) == StallRemediationAction.EXPAND_AND_RETRY
    assert action_for_step(2) == StallRemediationAction.BUFFER_CURATE_ORACLE
    assert action_for_step(3) == StallRemediationAction.REGIME_DIVERSE_SLICE
    assert action_for_step(4) == StallRemediationAction.META_SWEEP
    assert action_for_step(5) == StallRemediationAction.ORACLE_DISTILL


@pytest.mark.unit
def test_remediation_exhausted_at_max_steps() -> None:
    cfg = _cfg(stall_remediation_max_steps=5)
    state = StallRemediationState(active=True, remediation_step=5)
    assert is_remediation_exhausted(state, cfg=cfg) is True


@pytest.mark.unit
def test_curate_buffer_top_quartile() -> None:
    class _Buf:
        trajectories = [{"reward": float(i)} for i in range(8)]
        priorities = [1.0] * 8

    buf = _Buf()
    removed = curate_buffer_top_quartile(buf, keep_pct=0.25)
    assert removed == 6
    assert len(buf.trajectories) == 2


@pytest.mark.unit
def test_should_run_when_plateau_exhausted() -> None:
    state = StallRemediationState()
    cfg = _cfg()
    assert should_run_remediation_instead_of_human_gate(
        state, cfg=cfg, plateau_exhausted=True
    )


@pytest.mark.unit
def test_curate_buffer_removes_half() -> None:
    class _Buf:
        def __init__(self) -> None:
            self.trajectories = [{"reward": i} for i in range(8)]
            self.priorities = [1.0] * 8

    buf = _Buf()
    removed = curate_buffer_bottom_half(buf)
    assert removed == 4
    assert len(buf.trajectories) == 4
    assert all(t["reward"] >= 4 for t in buf.trajectories)


@pytest.mark.unit
def test_human_gate_reason_constant() -> None:
    assert HUMAN_GATE_REASON == "stall_remediation_exhausted"


@pytest.mark.unit
def test_phoenix_cycle_reason_constant() -> None:
    assert PHOENIX_CYCLE_REASON == "phoenix_cycle"
