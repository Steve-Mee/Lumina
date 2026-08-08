"""Stage2 occupancy: FORCE_OPEN must survive min-dwell (stop/slippage cannot wipe it)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment


def _flat_ticks(n: int = 200, price: float = 5000.0) -> list[dict]:
    ticks: list[dict] = []
    for i in range(n):
        ticks.append(
            {
                "timestamp": f"2026-01-01T{i:04d}:00Z",
                "close": price,
                "last": price,
                "bid": price - 0.25,
                "ask": price + 0.25,
                "volume": 10,
                "regime": "NEUTRAL",
            }
        )
    return ticks


class _Runtime:
    config = SimpleNamespace(instrument="MES", trade_mode="birth")


@pytest.mark.unit
def test_min_dwell_blocks_stop_exit_under_envelope() -> None:
    """With suppress_random_flatten + min_dwell, stop cannot close before dwell."""
    data = _flat_ticks(120)
    # Extreme entry stop so unprotected path would exit immediately on any move;
    # flat book keeps price constant — we force hit by setting stop after entry.
    cfg = RLConfig(
        trade_mode="birth",
        max_steps=100,
        suppress_random_flatten=True,
        participation_min_dwell_bars=8,
        range_patience_active=True,
    )
    env = RLTradingEnvironment(_Runtime(), data, config=cfg)
    env.reset()
    # Open long with tiny stop; then next bars use hold action.
    open_action = np.array([1.0, 0.5, 0.001, 0.002], dtype=np.float32)
    obs, reward, term, trunc, info = env.step(open_action)
    assert int(env._position) != 0
    assert int(env._bars_held) >= 1

    # Tighten stop to guarantee hit_stop if protect were off.
    env._entry_stop_pct = 0.50  # 50% — price flat would not hit; move entry instead
    env._entry_price = float(data[env._idx]["close"]) * 2.0  # long stop far above market

    hold = np.array([0.0, 0.5, 0.0075, 0.015], dtype=np.float32)
    for _ in range(6):
        env.step(hold)
        assert int(env._position) != 0, "position must survive min dwell under envelope"

    assert int(env._bars_held) >= 7


@pytest.mark.unit
def test_without_protect_stop_can_close() -> None:
    """Without envelope protect, a stop that is already breached closes."""
    data = _flat_ticks(80)
    cfg = RLConfig(
        trade_mode="birth",
        max_steps=80,
        suppress_random_flatten=False,
        participation_min_dwell_bars=0,
    )
    env = RLTradingEnvironment(_Runtime(), data, config=cfg)
    env.reset()
    open_action = np.array([1.0, 0.5, 0.0075, 0.015], dtype=np.float32)
    env.step(open_action)
    assert int(env._position) != 0
    # Long with entry well above market → immediate stop
    env._entry_price = float(data[env._idx]["close"]) * 1.05
    env._entry_stop_pct = 0.01
    hold = np.array([0.0, 0.5, 0.0075, 0.015], dtype=np.float32)
    env.step(hold)
    assert int(env._position) == 0


@pytest.mark.unit
def test_birth_equity_floor_prevents_negative() -> None:
    data = _flat_ticks(80)
    cfg = RLConfig(trade_mode="birth", max_steps=80, birth_equity_floor_ratio=0.10)
    env = RLTradingEnvironment(_Runtime(), data, config=cfg)
    env.reset()
    env._equity = -500.0
    # Hold step still applies floor after PnL update.
    hold = np.array([0.0, 0.5, 0.0075, 0.015], dtype=np.float32)
    env.step(hold)
    assert env._equity >= env._initial_equity * 0.10 - 1e-6
