from __future__ import annotations

from lumina_core.first_boot_progress import (
    resolve_ppo_progress_interval,
    resolve_ppo_training_progress,
    resolve_first_boot_completed_trades,
    resolve_first_boot_stage,
    resolve_first_boot_target_trades,
)


def test_resolve_completed_trades_prefers_runtime_keys() -> None:
    payload = {"cumulative_trades": 5400, "sim_trades": 5300, "trades": 5200}
    assert resolve_first_boot_completed_trades(payload) == 5200


def test_resolve_completed_trades_falls_back_safely() -> None:
    assert resolve_first_boot_completed_trades({}) == 0
    assert resolve_first_boot_completed_trades({"trades_done": "42"}) == 42


def test_resolve_target_trades_from_config_and_default() -> None:
    assert resolve_first_boot_target_trades({"first_boot": {"training_trades": 15000}}) == 15000
    assert resolve_first_boot_target_trades({}) == 5000


def test_resolve_stage_normalization() -> None:
    assert resolve_first_boot_stage({"stage": " Training_Running "}) == "training_running"
    assert resolve_first_boot_stage({}) == ""


def test_resolve_ppo_training_progress_defaults_and_pct() -> None:
    steps, total, pct = resolve_ppo_training_progress({"ppo_steps": 120000, "ppo_timesteps_total": 300000})
    assert steps == 120000
    assert total == 300000
    assert pct == 40.0


def test_resolve_ppo_progress_interval_clamps() -> None:
    assert resolve_ppo_progress_interval({}) == 10000
    assert resolve_ppo_progress_interval({"first_boot": {"ppo_progress_interval": 500}}) == 1000
    assert resolve_ppo_progress_interval({"first_boot": {"ppo_progress_interval": 250000}}) == 100000
