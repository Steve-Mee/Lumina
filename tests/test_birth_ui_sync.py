"""Birth Phase UI sync: pulse helpers, status bar trades label, fragment wiring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_core.first_boot_progress import (
    format_progress_heartbeat_age,
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
    from lumina_os.frontend.dashboard_views import status_bar_trades_label

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
def test_first_boot_command_center_status_bar_inside_fragment() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "lumina_launcher"
        / "ui"
        / "tabs"
        / "training_dashboard.py"
    ).read_text(encoding="utf-8")
    fb_section = source.split("def render_first_boot_command_center", 1)[1].split(
        "def render_training_dashboard_tab", 1
    )[0]
    assert "_render_luxury_status_bar_live" in fb_section
    assert "def _command_center_body" in fb_section
    assert fb_section.index("_render_luxury_status_bar_live") < fb_section.index("_render_command_center_tabs")


@pytest.mark.unit
def test_first_boot_tab_supports_skip_autorefresh() -> None:
    source = (Path(__file__).resolve().parents[1] / "lumina_launcher" / "ui" / "tabs" / "first_boot.py").read_text(
        encoding="utf-8"
    )
    assert "skip_autorefresh: bool = False" in source
    assert "Verversing via **Auto-refresh command center**" in source


@pytest.mark.unit
def test_first_boot_training_trades_tooltip_is_value_dependent() -> None:
    source = (Path(__file__).resolve().parents[1] / "lumina_launcher" / "ui" / "tabs" / "first_boot.py").read_text(
        encoding="utf-8"
    )
    assert "def _training_trades_help_text" in source
    assert "help_text=_training_trades_help_text(" in source
    assert "first_boot_training_trades_value" in source
    assert "estimate_first_boot_real_days(current_trades)" in source
    assert "FIRST_BOOT_EST_TRADES_PER_REAL_DAY" in source
    assert "200.000 -> ~" in source
    assert "500.000 -> ~" in source
    assert "1.000.000 -> ~" in source
    assert "historical cycling" in source


@pytest.mark.unit
def test_setup_wizard_training_copy_mentions_realistic_window_and_examples() -> None:
    source = (Path(__file__).resolve().parents[1] / "lumina_launcher" / "ui" / "setup_wizard.py").read_text(
        encoding="utf-8"
    )
    assert "ceil(trades/" in source
    assert "200.000 -> ~445 dagen" in source
    assert "500.000 -> ~1.112 dagen" in source
    assert "1.000.000 -> ~2.223 dagen" in source
    assert "cycling door historische dagen" in source


@pytest.mark.unit
def test_react_birth_phase_panel_shows_live_real_days_estimate_copy() -> None:
    source = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "components" / "BirthPhasePanel.tsx").read_text(
        encoding="utf-8"
    )
    assert "const EST_TRADES_PER_REAL_DAY = 450;" in source
    assert "Math.ceil" in source
    assert "Geschatte echte historische dagen" in source
    assert "Referentie: 200.000 - ~445 dagen" in source
    assert "historical cycling" in source


@pytest.mark.unit
def test_streamlit_sidebar_training_trades_help_has_live_examples() -> None:
    source = (Path(__file__).resolve().parents[1] / "lumina_launcher" / "streamlit_main.py").read_text(
        encoding="utf-8"
    )
    assert "def _sidebar_training_trades_help_text" in source
    assert "estimate_first_boot_real_days" in source
    assert "sidebar_first_boot_training_trades" in source
    assert "200.000 -> ~445 dagen" in source
    assert "500.000 -> ~1.112 dagen" in source
    assert "1.000.000 -> ~2.223 dagen" in source
