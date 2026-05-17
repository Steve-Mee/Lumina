"""
High-quality unit tests for FirstBootManager.
"""

import tempfile
from pathlib import Path

from lumina_launcher.core.first_boot import (
    FirstBootManager,
    build_first_boot_settings_signature,
    build_first_boot_settings_signature_from_settings,
    first_boot_settings_match_saved,
)


def test_first_boot_manager_initialization():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manager = FirstBootManager(root)
        assert manager.workspace_root == root


def test_save_and_read_settings():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manager = FirstBootManager(root)

        # Gebruiker kiest zelf het aantal training trades
        manager.save_settings(5000)
        settings = manager.read_settings()

        # Het getal moet overeenkomen met wat de gebruiker heeft ingegeven
        assert settings["training_trades"] == 5000
        assert settings["max_real_days"] == 30
        assert "prefer_real_data_only" in settings
        assert "require_real_simulator_data" in settings


def test_artifacts_missing_when_no_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manager = FirstBootManager(root)
        assert manager.artifacts_missing() is True


def test_get_stage_progress():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manager = FirstBootManager(root)

        assert manager.get_stage_progress("training_running") == 0.75
        assert manager.get_stage_progress("completed") == 1.0
        assert manager.get_stage_progress("unknown") == 0.1


def test_user_configured_flag_only_set_when_explicit():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manager = FirstBootManager(root)

        manager.save_full_settings(
            training_trades=5000,
            prefer_real_data_only=True,
            max_real_days=90,
            allow_minimal_synthetic_fallback=False,
            mark_user_configured=False,
        )
        assert manager.is_user_configured() is False

        manager.save_full_settings(
            training_trades=5000,
            prefer_real_data_only=True,
            max_real_days=90,
            allow_minimal_synthetic_fallback=False,
            mark_user_configured=True,
        )
        assert manager.is_user_configured() is True

        manager.save_full_settings(
            training_trades=5000,
            prefer_real_data_only=True,
            max_real_days=90,
            allow_minimal_synthetic_fallback=False,
            mark_user_configured=False,
        )
        assert manager.is_user_configured() is False


def test_first_boot_settings_match_saved_uses_disk_and_session() -> None:
    settings = {
        "training_trades": 5000,
        "prefer_real_data_only": True,
        "max_real_days": 90,
        "allow_minimal_synthetic_fallback": False,
        "require_real_simulator_data": True,
    }
    disk_sig = build_first_boot_settings_signature_from_settings(settings)
    current = build_first_boot_settings_signature(
        training_trades=5000,
        prefer_real_data_only=True,
        max_real_days=90,
        allow_minimal_synthetic_fallback=False,
        require_real_simulator_data=True,
    )
    assert first_boot_settings_match_saved(
        current_signature=current,
        settings_on_disk=settings,
        session_saved_signature=None,
    )
    assert first_boot_settings_match_saved(
        current_signature=current,
        settings_on_disk=settings,
        session_saved_signature=list(disk_sig),
    )
    dirty = build_first_boot_settings_signature(
        training_trades=6000,
        prefer_real_data_only=True,
        max_real_days=90,
        allow_minimal_synthetic_fallback=False,
        require_real_simulator_data=True,
    )
    assert not first_boot_settings_match_saved(
        current_signature=dirty,
        settings_on_disk=settings,
        session_saved_signature=None,
    )


def test_should_show_completion_summary_when_stage_completed(tmp_path: Path) -> None:
    root = tmp_path
    manager = FirstBootManager(root)
    manager.progress_path.parent.mkdir(parents=True, exist_ok=True)
    manager.progress_path.write_text(
        '{"stage": "completed", "message": "done", "trades": 600000}',
        encoding="utf-8",
    )
    assert manager.should_show_completion_summary() is True
    assert manager.is_completed() is False


def test_is_ppo_training_phase_detects_phase_field(tmp_path: Path) -> None:
    root = tmp_path
    manager = FirstBootManager(root)
    manager.progress_path.parent.mkdir(parents=True, exist_ok=True)
    manager.progress_path.write_text(
        '{"stage": "training_running", "phase": "ppo_training", "message": "PPO policy-training"}',
        encoding="utf-8",
    )
    assert manager.is_ppo_training_phase() is True


def test_is_ppo_interrupted_when_runtime_down_and_policy_missing(tmp_path: Path) -> None:
    root = tmp_path
    manager = FirstBootManager(root)
    manager.progress_path.parent.mkdir(parents=True, exist_ok=True)
    manager.progress_path.write_text(
        '{"stage":"training_running","phase":"ppo_training","message":"PPO policy-training"}',
        encoding="utf-8",
    )
    assert manager.is_ppo_interrupted(process_alive=False) is True
    manager.policy_path.parent.mkdir(parents=True, exist_ok=True)
    manager.policy_path.write_text("policy", encoding="utf-8")
    assert manager.is_ppo_interrupted(process_alive=False) is False
