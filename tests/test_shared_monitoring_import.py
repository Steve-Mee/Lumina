"""Regression: shared monitoring loader must use package import (no broken importlib path)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.test_monitoring_dashboard_smoke import _build_st_mock


@pytest.mark.unit
def test_render_shared_monitoring_dashboard_package_import(tmp_path: Path) -> None:
    # gegeven — launcher path: no frontend/ on sys.path, no manual sys.modules registration
    for key in list(sys.modules):
        if key.endswith("monitoring_dashboard"):
            del sys.modules[key]

    st_mock = _build_st_mock()
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 401
    mock_resp.json.return_value = {}

    state = tmp_path / "state"
    state.mkdir(parents=True)

    # wanneer
    with patch.dict(sys.modules, {"streamlit": st_mock}):
        with patch("requests.get", return_value=mock_resp):
            from lumina_os.frontend.dashboard_views import render_shared_monitoring_dashboard

            render_shared_monitoring_dashboard(
                "http://localhost:8000",
                workspace_root=tmp_path,
            )

    # dan
    calls = " ".join(str(c) for c in st_mock.markdown.call_args_list)
    assert "System Overview" in calls or "First Boot Training Status" in calls
