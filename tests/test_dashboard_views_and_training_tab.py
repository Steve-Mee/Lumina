"""Unit and integration checks for ``dashboard_views`` and the launcher Training tab."""

from __future__ import annotations

import textwrap
from pathlib import Path
import pytest

from lumina_os.frontend.dashboard_views import (
    DashboardPaths,
    compute_readiness_score,
    format_eta_minutes,
    get_training_velocity_tpm,
    load_json_dict,
    resolve_workspace_root_from_this_module,
    training_target_trades,
)


@pytest.mark.unit
class TestDashboardPaths:
    def test_paths_resolve_under_workspace(self, tmp_path: Path) -> None:
        ws = tmp_path / "repo"
        (ws / "state").mkdir(parents=True)
        p = DashboardPaths(ws)
        assert p.state_dir == ws / "state"
        assert p.last_run_summary == ws / "state" / "last_run_summary.json"
        assert p.config_yaml == ws / "config.yaml"
        assert p.evolution_log == ws / "state" / "evolution_log.jsonl"

    def test_resolve_workspace_root_points_at_repo(self) -> None:
        root = resolve_workspace_root_from_this_module()
        assert (root / "lumina_os" / "frontend" / "dashboard_views.py").is_file()


@pytest.mark.unit
class TestReadinessAndEta:
    def test_compute_readiness_score_full_green(self) -> None:
        report = {"READY_FOR_REAL": True, "consecutive_green_days": 5}
        score, note = compute_readiness_score(
            first_boot_done=True,
            report=report,
            bot_alive=True,
        )
        assert score == 100
        assert "READY_FOR_REAL=True" in note

    def test_compute_readiness_score_idle(self) -> None:
        report = {"READY_FOR_REAL": False, "consecutive_green_days": 0}
        score, _ = compute_readiness_score(
            first_boot_done=False,
            report=report,
            bot_alive=False,
        )
        assert score == 0

    def test_format_eta_minutes(self) -> None:
        assert "min" in format_eta_minutes(100, 10)
        assert format_eta_minutes(100, None) == "—"


@pytest.mark.unit
def test_training_target_trades_from_config(tmp_path: Path) -> None:
    ws = tmp_path
    cfg = textwrap.dedent(
        """
        first_boot:
          training_trades: 250000
        """
    )
    (ws / "config.yaml").write_text(cfg, encoding="utf-8")
    p = DashboardPaths(ws)
    assert training_target_trades(p) == 250_000


@pytest.mark.unit
def test_training_target_trades_default(tmp_path: Path) -> None:
    ws = tmp_path
    (ws / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    p = DashboardPaths(ws)
    assert training_target_trades(p) == 500_000


@pytest.mark.unit
def test_load_json_dict_missing(tmp_path: Path) -> None:
    p = tmp_path / "nope.json"
    assert load_json_dict(p) == {}


@pytest.mark.unit
def test_get_training_velocity_tpm_none_without_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_BACKEND_URL", "http://127.0.0.1:59999")
    v, est = get_training_velocity_tpm("http://127.0.0.1:59999", trades=0)
    assert v is None
    assert est is True


@pytest.mark.integration
def test_streamlit_main_wires_training_dashboard_tab() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "lumina_launcher" / "streamlit_main.py").read_text(encoding="utf-8")
    assert "render_training_dashboard_tab" in text
    assert "LUMINA OS Dashboard" in text


@pytest.mark.integration
def test_import_training_dashboard_module() -> None:
    from lumina_launcher.ui.tabs.training_dashboard import render_training_dashboard_tab

    assert callable(render_training_dashboard_tab)


@pytest.mark.integration
def test_legacy_dashboard_entry_does_not_import_on_smoke_path() -> None:
    """``dashboard.py`` calls ``main()`` at import time — do not import it in CI."""
    root = Path(__file__).resolve().parents[1]
    text = (root / "lumina_os" / "frontend" / "dashboard.py").read_text(encoding="utf-8")
    assert "render_full_streamlit_dashboard" in text
    assert "dashboard_views" in text
