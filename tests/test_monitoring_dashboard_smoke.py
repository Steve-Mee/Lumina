from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def _build_st_mock() -> MagicMock:
    st = MagicMock()

    def _columns(n, **_kw):
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return [MagicMock() for _ in range(count)]

    st.columns.side_effect = _columns
    st.text_input.return_value = ""
    st.slider.return_value = 20
    st.checkbox.return_value = False
    st.sidebar.selectbox.return_value = "All"
    return st


def test_monitoring_dashboard_tab_renders_without_exception() -> None:
    # gegeven
    frontend_file = Path(__file__).resolve().parents[1] / "lumina_os" / "frontend" / "monitoring_dashboard.py"
    spec = importlib.util.spec_from_file_location("__monitoring_dashboard_test__", frontend_file)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    st_mock = _build_st_mock()

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 401
    mock_resp.json.return_value = {}

    # wanneer
    with patch.dict(sys.modules, {"streamlit": st_mock}):
        with patch("requests.get", return_value=mock_resp):
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            module.render_monitoring_dashboard_tab("http://localhost:8000", title="Monitoring Dashboard")

    # dan
    calls = " ".join(str(c) for c in st_mock.markdown.call_args_list)
    assert "System Overview" in calls
    assert "Training History" in calls


def test_monitoring_dashboard_section_choice_gates_content() -> None:
    frontend_file = Path(__file__).resolve().parents[1] / "lumina_os" / "frontend" / "monitoring_dashboard.py"
    spec = importlib.util.spec_from_file_location("__monitoring_dashboard_test_section__", frontend_file)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    st_mock = _build_st_mock()
    st_mock.sidebar.selectbox.return_value = "B. First Boot Training Status"

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 401
    mock_resp.json.return_value = {}

    with patch.dict(sys.modules, {"streamlit": st_mock}):
        with patch("requests.get", return_value=mock_resp):
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            module.render_monitoring_dashboard_tab("http://localhost:8000", title="Monitoring Dashboard")

    calls = " ".join(str(c) for c in st_mock.markdown.call_args_list)
    assert "First Boot Training Status" in calls
    assert "A. System Overview" not in calls
