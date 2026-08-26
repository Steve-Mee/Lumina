"""Stage-2 action head reinit detox (no floor theater)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.stage2_policy_bootstrap import (
    curate_buffer_for_stage2_bootstrap,
    reinit_policy_action_head,
)


@pytest.mark.unit
def test_reinit_noop_without_model() -> None:
    out = reinit_policy_action_head(None)
    assert out["ok"] is False
    assert out["reason"] == "no_model"


@pytest.mark.unit
def test_reinit_resets_linear_action_net() -> None:
    torch = pytest.importorskip("torch")
    import torch.nn as nn

    action_net = nn.Sequential(nn.Linear(8, 4), nn.Tanh(), nn.Linear(4, 4))
    # Poison weights
    with torch.no_grad():
        for p in action_net.parameters():
            p.fill_(3.14)
    policy = SimpleNamespace(action_net=action_net, value_net=nn.Linear(8, 1), log_std=None)
    model = SimpleNamespace(policy=policy)
    out = reinit_policy_action_head(model, reinit_value_net=True)
    assert out["ok"] is True
    assert out["action_modules"] >= 2
    # Weights no longer all 3.14
    w = list(action_net.parameters())[0]
    assert not torch.allclose(w, torch.full_like(w, 3.14))


@pytest.mark.unit
def test_curate_buffer_list_keeps_positive() -> None:
    buf = [
        {"reward": -1.0, "pnl": -1},
        {"reward": 0.5, "pnl": 1},
        {"reward": 2.0, "pnl": 2},
    ]
    out = curate_buffer_for_stage2_bootstrap(buf, min_reward=0.0, max_keep=10)
    assert out["kept"] == 2
    assert out["removed"] == 1
    assert len(buf) == 2
