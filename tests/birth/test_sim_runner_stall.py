from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim


def _rising_historical_ticks(n: int) -> list[dict]:
    ticks = []
    price = 5000.0
    for i in range(n):
        price += 0.5
        ticks.append(
            {
                "timestamp": f"2026-01-01T{i:04d}:00Z",
                "last": price,
                "bid": price - 0.125,
                "ask": price + 0.125,
                "volume": 100,
                "source": "real_historical",
            }
        )
    return ticks


class _HoldOnlyPolicy:
    def predict(self, observation, *, deterministic: bool = True):
        _ = observation, deterministic
        return __import__("numpy").array([0.0, 0.0, 0.0075, 0.013], dtype=__import__("numpy").float32), None


class _RecordingPolicy:
    def predict(self, observation, *, deterministic: bool = True):
        _ = deterministic
        return __import__("numpy").array([1.0, 0.5, 0.0075, 0.013], dtype=__import__("numpy").float32), None


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(
        detect_market_regime=lambda _df: "NEUTRAL",
        market_data=SimpleNamespace(get_tape_snapshot=lambda: {}),
        get_current_dream_snapshot=lambda: {},
        AI_DRAWN_FIBS={},
        world_model={},
    )


@pytest.mark.unit
def test_hold_only_policy_stalls_with_step_budget(tmp_path: Path) -> None:
    ticks = enrich_ticks_for_sim(_rising_historical_ticks(600))
    result = run_policy_rollout(
        runtime=_runtime(),
        data=ticks,
        policy=_HoldOnlyPolicy(),
        target_trades=100,
        workspace_root=tmp_path,
        rollout_step_budget=120,
        stall_probe_steps=50,
        exploration_steps=0,
    )
    assert result.stalled is True
    assert result.trades == 0
    assert result.rollout_steps == 120
    assert result.stall_reason == "step_budget_exhausted"


@pytest.mark.unit
def test_hold_only_policy_exploration_produces_trades(tmp_path: Path) -> None:
    ticks = enrich_ticks_for_sim(_rising_historical_ticks(600))
    result = run_policy_rollout(
        runtime=_runtime(),
        data=ticks,
        policy=_HoldOnlyPolicy(),
        target_trades=3,
        workspace_root=tmp_path,
        rollout_step_budget=5000,
        stall_probe_steps=80,
        exploration_steps=500,
    )
    assert result.rollout_steps <= 5000
    assert result.exploration_steps_used > 0
    assert result.trades >= 1


@pytest.mark.unit
def test_rollout_progress_callback_fires(tmp_path: Path) -> None:
    ticks = enrich_ticks_for_sim(_rising_historical_ticks(600))
    snapshots: list[dict] = []

    run_policy_rollout(
        runtime=_runtime(),
        data=ticks,
        policy=_RecordingPolicy(),
        target_trades=2,
        workspace_root=tmp_path,
        rollout_step_budget=5000,
        on_progress=lambda payload: snapshots.append(dict(payload)),
    )

    assert snapshots
    assert snapshots[-1]["rollout_steps"] >= snapshots[0]["rollout_steps"]


@pytest.mark.unit
def test_recording_policy_completes_without_stall(tmp_path: Path) -> None:
    ticks = enrich_ticks_for_sim(_rising_historical_ticks(600))
    result = run_policy_rollout(
        runtime=_runtime(),
        data=ticks,
        policy=_RecordingPolicy(),
        target_trades=3,
        workspace_root=tmp_path,
    )
    assert result.stalled is False
    assert result.trades >= 1
