"""Birth Phase UI sync: pulse helpers and Tauri parity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_core.first_boot_progress import (
    progress_is_recently_active,
    resolve_birth_training_pulse,
    resolve_ppo_training_progress,
)


@pytest.mark.unit
def test_resolve_birth_training_pulse_active_when_birth_running() -> None:
    pulse = resolve_birth_training_pulse({}, birth_running=True)
    assert pulse == "active"


@pytest.mark.unit
def test_resolve_birth_training_pulse_stale_when_old_timestamp() -> None:
    old_ts = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
    progress = {"stage": "training_running", "timestamp": old_ts, "trades_done": 100}
    pulse = resolve_birth_training_pulse(progress)
    assert pulse == "stale"


@pytest.mark.unit
def test_progress_is_recently_active_uses_longer_window_for_ppo(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "birth_runner.json").write_text("{}", encoding="utf-8")
    ts = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()
    progress = {"stage": "ppo_training", "timestamp": ts}
    assert (
        progress_is_recently_active(
            progress,
            stage="ppo_training",
            workspace_root=tmp_path,
        )
        is True
    )


@pytest.mark.unit
def test_status_bar_trades_label_shows_target() -> None:
    from lumina_os.monitoring.dashboard_helpers import status_bar_trades_label

    progress = {"trades_done": 21187, "target_trades": 25000}
    label = status_bar_trades_label(progress, target_trades=25000)
    assert label == "21,187 / 25,000"


@pytest.mark.unit
def test_ppo_training_progress_does_not_double_count_batch() -> None:
    progress = {
        "ppo_steps": 20_000,
        "ppo_timesteps_total": 25_000,
        "ppo_batch_steps": 5_000,
        "ppo_batch_total": 10_000,
    }
    steps, total, pct = resolve_ppo_training_progress(progress)
    assert steps == 20_000
    assert total == 25_000
    assert pct is not None and pct <= 100.0


@pytest.mark.unit
def test_tauri_help_texts_registry_has_training_trades() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "tauri-app" / "src" / "lib" / "helpTexts.ts").read_text(encoding="utf-8")
    assert "training_trades" in source
    assert "450" in source or "historical" in source


@pytest.mark.unit
def test_tauri_birth_settings_panel_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "tauri-app" / "src" / "components" / "birth" / "BirthSettingsPanel.tsx"
    assert path.is_file()
    source = path.read_text(encoding="utf-8")
    assert "saveBirthSettings" in source or "BirthHoloSlider" in source
