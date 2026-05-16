from __future__ import annotations

from pathlib import Path

import pytest

from lumina_launcher.core.blank_reset import run_post_setup_blank_reset


def _touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_post_setup_blank_reset_preserves_setup_and_wipes_training(tmp_path: Path) -> None:
    _touch(tmp_path / "state" / "lumina_setup_complete.json", "{}")
    _touch(tmp_path / "state" / "lumina_setup_status.json", "{}")
    _touch(tmp_path / "state" / "hardware_snapshot.json", "{}")
    _touch(tmp_path / "state" / "first_boot_completed.flag", "done")
    _touch(tmp_path / "state" / "first_boot_progress.json", "{}")
    _touch(tmp_path / "state" / "first_boot_checkpoint.json", "{}")
    _touch(tmp_path / "state" / "launcher_bot_process.json", "{}")
    _touch(tmp_path / "logs" / "app.log", "log")
    _touch(tmp_path / "journal" / "simulator" / "first_boot_training_1.json", "{}")
    _touch(tmp_path / "lumina_os" / "logs" / "ui.log", "log")
    _touch(tmp_path / "lumina_os" / "state" / "metrics.db", "db")
    _touch(tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip", "zip")
    _touch(tmp_path / "config.yaml", "mode: sim")
    _touch(tmp_path / ".env", "TRADE_MODE=sim")

    stop_calls = {"count": 0}

    def _stop_runtime() -> tuple[bool, str]:
        stop_calls["count"] += 1
        return True, "stopped"

    result = run_post_setup_blank_reset(tmp_path, stop_runtime=_stop_runtime)

    assert result.success is True
    assert stop_calls["count"] == 1
    assert result.backup_path is not None and result.backup_path.exists()
    assert (tmp_path / "state" / "lumina_setup_complete.json").exists()
    assert (tmp_path / "state" / "hardware_snapshot.json").exists()
    assert not (tmp_path / "state" / "first_boot_completed.flag").exists()
    assert not (tmp_path / "state" / "first_boot_progress.json").exists()
    assert not (tmp_path / "journal" / "simulator" / "first_boot_training_1.json").exists()
    assert not (tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip").exists()
    assert (tmp_path / "config.yaml").exists()
    assert (tmp_path / ".env").exists()


@pytest.mark.unit
def test_post_setup_blank_reset_fails_if_runtime_stop_fails(tmp_path: Path) -> None:
    _touch(tmp_path / "state" / "lumina_setup_complete.json", "{}")

    def _stop_runtime() -> tuple[bool, str]:
        return False, "cannot stop"

    result = run_post_setup_blank_reset(tmp_path, stop_runtime=_stop_runtime)

    assert result.success is False
    assert "Runtime stop failed" in result.message
    assert result.backup_path is None
