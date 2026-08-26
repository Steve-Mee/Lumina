"""Defense-in-depth guards against empty birth market data (IndexError regression)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment


@pytest.mark.unit
def test_gym_empty_data_clear_error() -> None:
    env = RLTradingEnvironment(SimpleNamespace(), [], config=RLConfig())
    with pytest.raises(ValueError, match="empty market data"):
        env.reset()


@pytest.mark.unit
def test_sim_runner_empty_data_guard() -> None:
    result = run_policy_rollout(
        runtime=SimpleNamespace(),
        data=[],
        policy=None,
        target_trades=8,
    )
    assert result.stalled is True
    assert result.stall_reason == "empty_data"
    assert result.trades == 0
    assert result.partial_complete is True
