from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
import pytest

from lumina_core.ppo_evolution_logger import (
    PPOEvolutionLogger,
    RollingStepMetrics,
    compute_action_distribution,
    compute_avg_pct,
    compute_rolling_sharpe,
    compute_rolling_winrate,
)


def test_compute_rolling_winrate_deterministic() -> None:
    outcomes = deque([1, 0, 1, 1, 0])
    assert compute_rolling_winrate(outcomes) == 0.6


def test_compute_rolling_winrate_empty() -> None:
    assert compute_rolling_winrate(deque()) == 0.0


def test_compute_rolling_sharpe_from_env_samples() -> None:
    sharpe = deque([1.1, 1.3, 1.5])
    assert compute_rolling_sharpe(sharpe, deque()) == 1.3


def test_compute_rolling_sharpe_from_equity_returns() -> None:
    returns = deque([0.01, -0.005, 0.008, 0.002])
    sharpe = compute_rolling_sharpe(deque(), returns)
    assert sharpe > 0.0


def test_compute_action_distribution_normalized() -> None:
    dist = compute_action_distribution({"hold": 1, "long": 6, "short": 3})
    assert dist == {"long": 0.6, "short": 0.3, "hold": 0.1}
    assert round(sum(dist.values()), 2) == 1.0


def test_rolling_step_metrics_records_actions_and_info() -> None:
    rolling = RollingStepMetrics(window=100)
    rolling.record_action(np.array([1.0, 0.5, 0.01, 0.02], dtype=np.float32))
    rolling.record_action(np.array([2.0, 0.2, 0.012, 0.025], dtype=np.float32))
    rolling.record_info({"model_close_gross_pnl_usd": 12.5, "sharpe": 1.4, "equity": 50100.0})
    rolling.record_info({"model_close_gross_pnl_usd": -3.0, "equity": 50050.0})

    assert rolling.side_counts["long"] == 1
    assert rolling.side_counts["short"] == 1
    assert len(rolling.trade_outcomes) == 2
    assert compute_rolling_winrate(rolling.trade_outcomes) == 0.5
    assert compute_avg_pct(rolling.stop_pcts, default=0.0) == pytest.approx(0.011, abs=0.001)


def test_ppo_evolution_logger_writes_jsonl(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("stable_baselines3")

    log_path = tmp_path / "state" / "ppo_training_log.jsonl"
    logger = PPOEvolutionLogger(log_path=log_path, log_interval=1)

    class _FakeLogger:
        name_to_value = {
            "rollout/ep_rew_mean": 1.25,
            "train/policy_loss": 0.04,
            "train/value_loss": 0.11,
            "train/entropy": 0.33,
            "train/explained_variance": 0.72,
        }

    logger.model = type("_M", (), {"logger": _FakeLogger()})()
    logger.num_timesteps = 5000
    logger.last_log_step = 0
    logger._rolling.record_action(np.array([1.0, 0.4, 0.009, 0.018], dtype=np.float32))
    logger._rolling.record_info({"model_close_gross_pnl_usd": 5.0, "sharpe": 1.2})

    monkeypatch.setattr(
        "lumina_core.ppo_evolution_logger._broadcast_entry_async",
        lambda _payload: None,
    )

    assert logger._on_step() is True
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    required = {
        "timestamp",
        "step",
        "mean_reward",
        "policy_loss",
        "value_loss",
        "entropy",
        "explained_variance",
        "winrate_rolling_5k",
        "sharpe_rolling_5k",
        "action_distribution",
        "avg_stop_pct",
        "avg_target_pct",
    }
    assert required.issubset(entry.keys())
    assert entry["step"] == 5000
    assert entry["mean_reward"] == 1.25
    assert entry["entropy"] == 0.33
    assert entry["policy_loss"] == 0.04
    assert entry["action_distribution"]["long"] == 1.0
    assert entry["winrate_rolling_5k"] == 1.0


def test_ppo_evolution_logger_flushes_on_training_end(tmp_path: Path, monkeypatch) -> None:
    """Short birth bursts (< log_interval) must still emit entropy at learn() end."""
    pytest.importorskip("stable_baselines3")

    log_path = tmp_path / "state" / "ppo_training_log.jsonl"
    logger = PPOEvolutionLogger(log_path=log_path, log_interval=5000)

    class _FakeLogger:
        name_to_value = {
            "rollout/ep_rew_mean": 0.1,
            "train/entropy_loss": -0.33,
            "train/policy_gradient_loss": 0.01,
            "train/value_loss": 1.0,
            "train/explained_variance": 0.0,
        }

    logger.model = type("_M", (), {"logger": _FakeLogger()})()
    logger.num_timesteps = 3000
    logger.last_log_step = 0
    monkeypatch.setattr(
        "lumina_core.ppo_evolution_logger._broadcast_entry_async",
        lambda _payload: None,
    )
    assert logger._on_step() is True
    assert not log_path.exists()
    logger._on_training_end()
    assert log_path.exists()
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["step"] == 3000
    assert entry["entropy"] == pytest.approx(0.33)
    assert logger.last_entropy == pytest.approx(0.33)


def test_resolve_entropy_prefers_sb3_28_entropy_loss() -> None:
    logs = {"train/entropy_loss": -0.42, "train/entropy": 0.0}
    assert PPOEvolutionLogger._resolve_entropy(logs) == pytest.approx(0.42)


def test_resolve_policy_loss_prefers_sb3_28_policy_gradient_loss() -> None:
    logs = {"train/policy_gradient_loss": 0.07, "train/policy_loss": 0.0}
    assert PPOEvolutionLogger._resolve_policy_loss(logs) == pytest.approx(0.07)


def test_ppo_evolution_logger_sb3_28_keys(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("stable_baselines3")

    log_path = tmp_path / "state" / "ppo_training_log.jsonl"
    logger = PPOEvolutionLogger(log_path=log_path, log_interval=1)

    class _FakeLogger:
        name_to_value = {
            "rollout/ep_rew_mean": 0.5,
            "train/policy_gradient_loss": 0.08,
            "train/value_loss": 12.0,
            "train/entropy_loss": -0.55,
            "train/explained_variance": 0.02,
        }

    logger.model = type("_M", (), {"logger": _FakeLogger()})()
    logger.num_timesteps = 1000
    logger.last_log_step = 0
    monkeypatch.setattr(
        "lumina_core.ppo_evolution_logger._broadcast_entry_async",
        lambda _payload: None,
    )
    assert logger._on_step() is True
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["entropy"] == pytest.approx(0.55)
    assert entry["policy_loss"] == pytest.approx(0.08)
