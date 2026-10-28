"""OOS proxy fitness helpers."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.oos_proxy import (
    blended_learning_velocity,
    should_run_oos_proxy,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_should_run_oos_proxy_after_interval() -> None:
    cfg = _cfg(oos_proxy_enabled=True, oos_proxy_interval_trades=500)
    assert not should_run_oos_proxy(400, 0, cfg=cfg)
    assert should_run_oos_proxy(500, 0, cfg=cfg)
    assert not should_run_oos_proxy(900, 500, cfg=cfg)
    assert should_run_oos_proxy(1000, 500, cfg=cfg)


@pytest.mark.unit
def test_blended_learning_velocity_mixes_proxy() -> None:
    cfg = _cfg(oos_proxy_weight=0.5)
    blended = blended_learning_velocity(
        winrate_history=[0.30, 0.31, 0.32, 0.33, 0.34],
        reward_history=[0.1, 0.1, 0.1, 0.1, 0.1],
        oos_proxy_history=[0.20, 0.22, 0.24, 0.26, 0.28],
        cfg=cfg,
    )
    assert blended != 0.0