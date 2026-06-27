from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.first_boot_progress import (
    ensure_first_boot_hardware_profile,
    is_sim_trades_complete,
    resolve_first_boot_target_for_display,
    resolve_ppo_batch_progress,
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


def test_resolve_ppo_training_progress_uses_cumulative_without_double_batch() -> None:
    steps, total, pct = resolve_ppo_training_progress(
        {
            "ppo_steps_cumulative": 175000,
            "ppo_timesteps_planned_total": 225000,
            "ppo_batch_steps": 20000,
            "ppo_batch_total": 25000,
        }
    )
    assert steps == 175000
    assert total == 225000
    assert pct is not None and 77.0 <= pct <= 78.0


def test_resolve_ppo_training_progress_legacy_fallback() -> None:
    steps, total, pct = resolve_ppo_training_progress({"ppo_steps": 120000, "ppo_timesteps_total": 300000})
    assert steps == 120000
    assert total == 300000
    assert pct == 40.0


def test_resolve_ppo_batch_progress() -> None:
    steps, total, pct = resolve_ppo_batch_progress(
        {"ppo_batch_steps": 20000, "ppo_batch_total": 25000, "ppo_batch_progress_pct": 80.0}
    )
    assert steps == 20000
    assert total == 25000
    assert pct == 80.0


def test_is_sim_trades_complete_flag_and_trades() -> None:
    assert is_sim_trades_complete({"sim_trades_complete": True}) is True
    assert is_sim_trades_complete({"target_trades": 100, "trades": 100}) is True
    assert is_sim_trades_complete({"target_trades": 100, "trades": 50}) is False


def test_resolve_ppo_progress_interval_clamps() -> None:
    assert resolve_ppo_progress_interval({}) == 10000
    assert resolve_ppo_progress_interval({"first_boot": {"ppo_progress_interval": 500}}) == 1000
    assert resolve_ppo_progress_interval({"first_boot": {"ppo_progress_interval": 250000}}) == 100000


def test_resolve_first_boot_target_for_display_prefers_session_draft_when_idle() -> None:
    target = resolve_first_boot_target_for_display(
        progress={"stage": "idle", "target_trades": 0},
        config_payload={"first_boot": {"training_trades": 25000}},
        session_trades=100000,
    )
    assert target == 100000


def test_resolve_first_boot_target_for_display_prefers_active_progress_target() -> None:
    target = resolve_first_boot_target_for_display(
        progress={"stage": "training_running", "target_trades": 30000},
        config_payload={"first_boot": {"training_trades": 25000}},
        session_trades=100000,
    )
    assert target == 30000


def test_ensure_first_boot_hardware_profile_delegates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "profile": "gpu_accelerated",
        "detection": {"recommended_profile": "gpu_accelerated"},
        "tuning": {"rollout_chunk_trades": 250},
    }
    monkeypatch.setattr(
        "lumina_core.first_boot_progress.get_or_create_hardware_profile",
        lambda workspace_root: expected,
    )

    result = ensure_first_boot_hardware_profile(tmp_path)

    assert result == expected
    assert result["profile"] == "gpu_accelerated"
