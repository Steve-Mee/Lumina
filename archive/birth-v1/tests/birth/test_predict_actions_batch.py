"""Batched policy.predict — one forward for n observations."""
from __future__ import annotations

import numpy as np

from lumina_core.birth.sim_runner_actions import predict_action, predict_actions


class _BatchPolicy:
    def predict(self, obs, deterministic=True):  # noqa: ANN001
        del deterministic
        arr = np.asarray(obs, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        n = arr.shape[0]
        actions = np.zeros((n, 4), dtype=np.float32)
        actions[:, 0] = 1.0
        actions[:, 1] = 0.5
        actions[:, 2] = 0.001
        actions[:, 3] = 0.002
        return actions, None


def test_predict_actions_batch_shape() -> None:
    obs = np.zeros((8, 43), dtype=np.float32)
    out = predict_actions(_BatchPolicy(), obs, deterministic=True)
    assert out.shape == (8, 4)
    assert float(out[0, 0]) == 1.0


def test_predict_action_uses_batch_path() -> None:
    action = predict_action(_BatchPolicy(), np.zeros(43, dtype=np.float32))
    assert action.shape == (4,)
    assert float(action[0]) == 1.0


def test_predict_actions_none_policy_returns_hold_batch() -> None:
    out = predict_actions(None, np.zeros((3, 6), dtype=np.float32))
    assert out.shape == (3, 4)
    assert float(out[0, 0]) == 0.0
