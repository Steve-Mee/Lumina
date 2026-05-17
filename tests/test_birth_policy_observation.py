from __future__ import annotations

import numpy as np
import pytest

from lumina_core.birth_policy_observation import BIRTH_RL_OBS_DIM, build_birth_rl_observation_vector


@pytest.mark.unit
def test_build_birth_rl_observation_vector_has_28_dimensions() -> None:
    tick = {"last": 5000.0, "regime": "TRENDING", "imbalance": 1.1, "volume": 12}
    obs = build_birth_rl_observation_vector(
        tick=tick,
        position=None,
        tick_index=10,
        tick_count=100,
    )
    assert obs.shape == (BIRTH_RL_OBS_DIM,)
    assert obs.dtype == np.float32
    assert float(obs[0]) == 5000.0


@pytest.mark.unit
def test_build_birth_rl_observation_vector_includes_position_state() -> None:
    tick = {"last": 5010.0, "regime": "NEUTRAL", "imbalance": 1.0, "volume": 5}
    position = {"side": "BUY", "qty": 2, "entry_price": 5005.0, "stop": 4990.0, "target": 5030.0}
    obs = build_birth_rl_observation_vector(
        tick=tick,
        position=position,
        tick_index=3,
        tick_count=50,
        recent_pnl=[1.0, -0.5, 2.0, 1.5, 0.25],
    )
    assert float(obs[16]) == 1.0
    assert float(obs[17]) == 2.0
    assert float(obs[18]) == 5005.0
