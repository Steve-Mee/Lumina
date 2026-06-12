"""Unit checks for headless dashboard helpers (post-Streamlit)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from lumina_os.monitoring.dashboard_helpers import (
    DashboardPaths,
    compute_readiness_score,
    embedded_react_ui_status,
    format_eta_minutes,
    get_training_velocity_tpm,
    load_json_dict,
    react_dashboard_url,
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
        assert (root / "lumina_os" / "monitoring" / "dashboard_helpers.py").is_file()


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
    (ws / "state").mkdir(parents=True, exist_ok=True)
    (ws / "state" / "first_boot_user_configured.flag").write_text("ok", encoding="utf-8")
    p = DashboardPaths(ws)
    assert training_target_trades(p) == 250_000


@pytest.mark.unit
def test_training_target_trades_default(tmp_path: Path) -> None:
    ws = tmp_path
    (ws / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    p = DashboardPaths(ws)
    assert training_target_trades(p) == 0


@pytest.mark.unit
def test_embedded_react_ui_status_missing_dist(tmp_path: Path) -> None:
    p = DashboardPaths(tmp_path)
    status = embedded_react_ui_status("http://localhost:8000", p)
    assert status["ready"] is False
    assert status["reason"] == "missing_dist"
    assert str(status["react_url"]).startswith("http://")


@pytest.mark.unit
def test_embedded_react_ui_status_wrong_base_path(tmp_path: Path) -> None:
    ws = tmp_path
    (ws / "frontend" / "dist").mkdir(parents=True)
    (ws / "frontend" / "dist" / "index.html").write_text(
        '<html><script src="/assets/index.js"></script></html>',
        encoding="utf-8",
    )
    p = DashboardPaths(ws)
    status = embedded_react_ui_status("http://localhost:8000", p)
    assert status["ready"] is False
    assert status["reason"] == "wrong_base_path"


@pytest.mark.unit
def test_embedded_react_ui_status_ready_embedded_build(tmp_path: Path) -> None:
    ws = tmp_path
    (ws / "frontend" / "dist").mkdir(parents=True)
    (ws / "frontend" / "dist" / "index.html").write_text(
        '<html><script src="/ui/assets/index.js"></script></html>',
        encoding="utf-8",
    )
    p = DashboardPaths(ws)
    status = embedded_react_ui_status("http://localhost:8000", p)
    assert status["ready"] is True
    assert status["reason"] == "ok"
    assert str(status["react_url"]).startswith("http://localhost:8000/ui/?v=")


@pytest.mark.unit
def test_react_dashboard_url_embedded_includes_build_stamp(tmp_path: Path) -> None:
    ws = tmp_path
    (ws / "frontend" / "dist").mkdir(parents=True, exist_ok=True)
    (ws / "frontend" / "dist" / "index.html").write_text(
        '<html><script src="/ui/assets/index.js"></script></html>',
        encoding="utf-8",
    )
    p = DashboardPaths(ws)
    url = react_dashboard_url("http://localhost:8000", p)
    assert url.startswith("http://localhost:8000/ui/?v=")


@pytest.mark.unit
def test_load_json_dict_missing(tmp_path: Path) -> None:
    p = tmp_path / "nope.json"
    assert load_json_dict(p) == {}


@pytest.mark.unit
def test_get_training_velocity_tpm_none_without_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_BACKEND_URL", "http://127.0.0.1:59999")
    monkeypatch.setattr(
        "lumina_os.monitoring.dashboard_helpers.resolve_dashboard_api_key",
        lambda explicit="": "",
    )
    v, est = get_training_velocity_tpm("http://127.0.0.1:59999", trades=0)
    assert v is None
    assert est is True


def test_get_training_velocity_tpm_uses_api_key_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_os.monitoring.dashboard_helpers.resolve_dashboard_api_key",
        lambda explicit="": "test-metrics-key",
    )

    class _Resp:
        ok = True

        @staticmethod
        def json() -> dict[str, object]:
            return {"lumina_training_velocity": {"value": 4200}}

    captured: dict[str, object] = {}

    def _fake_get(url: str, **kwargs: object) -> _Resp:
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        return _Resp()

    monkeypatch.setattr("lumina_os.monitoring.dashboard_helpers.requests.get", _fake_get)
    v, est = get_training_velocity_tpm("http://127.0.0.1:8000", trades=100)
    assert v == 4200
    assert est is False
    assert captured["headers"] == {"X-API-Key": "test-metrics-key"}


@pytest.mark.integration
def test_tauri_has_monitoring_deep_panel() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "tauri-app" / "src" / "components" / "intelligence" / "MonitoringDeepPanel.tsx").read_text(
        encoding="utf-8"
    )
    assert "fetchMonitoringDiagnostics" in text or "monitoringClient" in text
