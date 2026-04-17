# CANONICAL IMPLEMENTATION – v50 Living Organism
"""Smoke tests for the Lumina OS Streamlit dashboard regime rendering.

Strategy: mock the entire `streamlit` module plus external HTTP deps so
`_render_observability_tab` can be imported and called in a plain pytest
run without a running Streamlit server.

Coverage:
  - Normal (TRENDING / NORMAL) regime renders section labels without exception
  - HIGH_RISK regime triggers st.warning with the issue label
  - Regime flip history expander is created when history rows exist
  - No API key → early return path does not crash
  - With API key → main metric sections are rendered
  - Health endpoint error → degrades gracefully (no exception)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# ── Paths ─────────────────────────────────────────────────────────────────────

_FRONTEND_PATH = Path(__file__).resolve().parents[1] / "lumina_os" / "frontend"
_MOD_KEY = "__dashboard_smoke_test__"


# ── Response stub ─────────────────────────────────────────────────────────────


def _mock_resp(data: Any, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.ok = status_code < 400
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = "# prometheus stub\n"
    return resp


# ── Shared payloads ───────────────────────────────────────────────────────────

_HEALTH_NORMAL = {
    "status": "healthy",
    "uptime_s": 120.0,
    "kill_switch_active": False,
    "websocket_connected": True,
    "current_regime": "TRENDING",
    "regime_risk_state": "NORMAL",
    "regime_confidence": 0.78,
    "fast_path_weight": 0.65,
    "high_risk_override_count": 0,
    "issues": [],
    "ts": 1_712_400_000.0,
}

_HEALTH_HIGH_RISK = {
    **_HEALTH_NORMAL,
    "status": "degraded",
    "current_regime": "NEWS_DRIVEN",
    "regime_risk_state": "HIGH_RISK",
    "regime_confidence": 0.91,
    "fast_path_weight": 0.82,
    "high_risk_override_count": 3,
    "issues": ["high_risk_regime"],
}

_SNAP_JSON: dict[str, Any] = {
    "lumina_pnl_daily": {"value": 250.0},
    "lumina_pnl_unrealized": {"value": 0.0},
    "lumina_pnl_total": {"value": 1500.0},
    "lumina_risk_daily_pnl": {"value": 250.0},
    "lumina_risk_consecutive_losses": {"value": 1.0},
    "lumina_evolution_proposals_total": {"value": 4.0},
    "lumina_evolution_acceptances_total": {"value": 2.0},
    "lumina_evolution_acceptance_rate": {"value": 0.5},
    "lumina_evolution_last_confidence": {"value": 0.72},
    'lumina_regime_confidence{regime="TRENDING"}': {"value": 0.78},
    'lumina_regime_fast_path_weight{regime="TRENDING"}': {"value": 0.65},
    'lumina_regime_high_risk_overrides_total{regime="TRENDING"}': {"value": 0.0},
}

_HISTORY_ROWS = [
    {
        "ts": 1_712_400_000.0,
        "name": "lumina_regime_current",
        "labels": {"regime": "TRENDING", "risk_state": "NORMAL"},
        "type": "gauge",
        "value": 1.0,
    },
    {
        "ts": 1_712_396_400.0,
        "name": "lumina_regime_current",
        "labels": {"regime": "RANGING", "risk_state": "NORMAL"},
        "type": "gauge",
        "value": 1.0,
    },
]


# ── Dashboard loader ──────────────────────────────────────────────────────────


def _build_st_mock() -> MagicMock:
    """Return a MagicMock that handles variable-arity columns/tabs calls."""
    st = MagicMock()

    def _columns(n, **_kw):
        # st.columns() accepts either an int or a list of relative widths
        count = len(n) if isinstance(n, (list, tuple)) else int(n)
        return [MagicMock() for _ in range(count)]

    def _tabs(labels):
        return [MagicMock() for _ in range(len(labels))]

    st.columns.side_effect = _columns
    st.tabs.side_effect = _tabs
    st.text_input.return_value = ""  # default: no API key
    st.checkbox.return_value = False  # auto-refresh off
    return st


def _load_render_fn(st_mock: MagicMock) -> Any:
    """Load dashboard._render_observability_tab with all Streamlit/HTTP deps mocked.

    dashboard.py runs _render_observability_tab once at module level (inside
    ``with tab3:``).  We execute that call with no API key and a benign health
    response so it returns early, then hand back the function for the
    test-specific call.
    """
    sys.modules.pop(_MOD_KEY, None)

    # Force no API key during module-level execution so the function returns
    # early, avoiding the need to stage all JSON/history mock responses twice.
    _saved_rv = st_mock.text_input.return_value
    st_mock.text_input.return_value = ""

    extra_mocks: dict[str, Any] = {
        "streamlit": st_mock,
        "global_wisdom_view": MagicMock(),
        "leaderboard_view": MagicMock(),
        "evolution_approval": MagicMock(),
    }

    spec = importlib.util.spec_from_file_location(_MOD_KEY, _FRONTEND_PATH / "dashboard.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]

    with patch.dict(sys.modules, extra_mocks):
        with patch("requests.get", return_value=_mock_resp(_HEALTH_NORMAL)):
            spec.loader.exec_module(mod)  # type: ignore[union-attr]

    # Restore the caller's API-key setting for the actual test call.
    st_mock.text_input.return_value = _saved_rv
    sys.modules.pop(_MOD_KEY, None)
    return mod._render_observability_tab


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_render_normal_regime_no_exception() -> None:
    """Tab renders without raising for a healthy TRENDING regime."""
    st_mock = _build_st_mock()
    render = _load_render_fn(st_mock)

    st_mock.markdown.reset_mock()
    responses = iter(
        [
            _mock_resp(_HEALTH_NORMAL),
        ]
    )
    with patch("requests.get", side_effect=lambda *a, **kw: next(responses)):
        render("http://localhost:8000")  # must not raise

    markdown_calls = " ".join(str(c) for c in st_mock.markdown.call_args_list)
    assert "Adaptive Regime" in markdown_calls


def test_render_high_risk_regime_shows_warning() -> None:
    """When regime_risk_state == HIGH_RISK, st.warning must be called."""
    st_mock = _build_st_mock()
    render = _load_render_fn(st_mock)

    st_mock.warning.reset_mock()  # clear any calls from module-level exec
    with patch("requests.get", return_value=_mock_resp(_HEALTH_HIGH_RISK)):
        render("http://localhost:8000")

    st_mock.warning.assert_called()
    warning_text = " ".join(str(c) for c in st_mock.warning.call_args_list)
    assert "high_risk_regime" in warning_text


def test_render_no_api_key_returns_early_no_exception() -> None:
    """Without an API key, the tab shows an info message and exits cleanly."""
    st_mock = _build_st_mock()
    st_mock.text_input.return_value = ""
    render = _load_render_fn(st_mock)

    st_mock.info.reset_mock()
    with patch("requests.get", return_value=_mock_resp(_HEALTH_NORMAL)):
        render("http://localhost:8000")

    st_mock.info.assert_called()  # "Enter your API key" info box


def test_render_with_api_key_shows_metrics_sections() -> None:
    """With an API key supplied, PnL and Self-Evolution sections render."""
    st_mock = _build_st_mock()
    st_mock.text_input.return_value = "secret-key"
    render = _load_render_fn(st_mock)

    prom_resp = MagicMock()
    prom_resp.ok = True
    prom_resp.text = ""
    responses = iter(
        [
            _mock_resp(_HEALTH_NORMAL),
            _mock_resp(_SNAP_JSON),
            _mock_resp([]),  # regime history
            prom_resp,  # raw Prometheus expander
        ]
    )

    st_mock.markdown.reset_mock()
    with patch("requests.get", side_effect=lambda *a, **kw: next(responses)):
        render("http://localhost:8000")

    markdown_calls = " ".join(str(c) for c in st_mock.markdown.call_args_list)
    assert "PnL" in markdown_calls
    assert "Self-Evolution" in markdown_calls
    assert "Regime Metrics" in markdown_calls


def test_render_regime_history_expander_shown_when_rows_exist() -> None:
    """When /regime/history returns rows, an expander for flips is created."""
    st_mock = _build_st_mock()
    st_mock.text_input.return_value = "secret-key"
    render = _load_render_fn(st_mock)

    prom_resp = MagicMock()
    prom_resp.ok = True
    prom_resp.text = ""
    responses = iter(
        [
            _mock_resp(_HEALTH_NORMAL),
            _mock_resp(_SNAP_JSON),
            _mock_resp(_HISTORY_ROWS),  # 2 active regime-flip rows
            prom_resp,
        ]
    )

    st_mock.expander.reset_mock()
    with patch("requests.get", side_effect=lambda *a, **kw: next(responses)):
        render("http://localhost:8000")

    assert st_mock.expander.call_count >= 1
    expander_titles = " ".join(str(c) for c in st_mock.expander.call_args_list)
    assert "Regime Flip History" in expander_titles


def test_render_health_error_degrades_gracefully() -> None:
    """If the health endpoint is unreachable, the tab renders without  raising."""
    st_mock = _build_st_mock()
    render = _load_render_fn(st_mock)

    with patch("requests.get", side_effect=ConnectionError("refused")):
        render("http://localhost:8000")  # must not propagate the exception
