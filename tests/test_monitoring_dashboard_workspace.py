"""Monitoring dashboard reads state from an explicit workspace root."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_monitoring_module():
    frontend_file = Path(__file__).resolve().parents[1] / "lumina_os" / "frontend" / "monitoring_dashboard.py"
    spec = importlib.util.spec_from_file_location("__monitoring_workspace_test__", frontend_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    return module, spec


@pytest.mark.unit
def test_monitoring_paths_resolve_under_workspace(tmp_path: Path) -> None:
    module, spec = _load_monitoring_module()
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    state = tmp_path / "state"
    state.mkdir()
    progress = state / "lumina_birth_progress.json"
    progress.write_text(
        json.dumps({"stage": "ppo_training", "progress_pct": 42, "timestamp": "2026-05-17T12:00:00+00:00"}),
        encoding="utf-8",
    )

    paths = module._MonitoringPaths.resolve(tmp_path)
    assert paths.first_boot_progress == progress
    assert paths.workspace_root.resolve() == tmp_path.resolve()


@pytest.mark.unit
def test_render_monitoring_dashboard_uses_workspace_progress(tmp_path: Path) -> None:
    module, spec = _load_monitoring_module()
    st_mock = MagicMock()

    def _columns(n, **_kw):
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return [MagicMock() for _ in range(count)]

    st_mock.columns.side_effect = _columns
    st_mock.text_input.return_value = ""
    st_mock.tabs.return_value = [MagicMock() for _ in range(9)]

    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_progress.json").write_text(
        json.dumps({"stage": "ppo_training", "progress_pct": 55, "message": "workspace ok"}),
        encoding="utf-8",
    )

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.json.return_value = {}

    with patch.dict(sys.modules, {"streamlit": st_mock}):
        with patch("requests.get", return_value=mock_resp):
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            module.render_monitoring_dashboard_tab(
                "http://localhost:8000",
                workspace_root=tmp_path,
                title="Monitoring Dashboard",
            )

    captions = " ".join(str(c) for c in st_mock.caption.call_args_list)
    assert str(tmp_path) in captions or "workspace ok" in captions
