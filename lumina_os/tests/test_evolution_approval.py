"""Smoke tests for the Evolution Approval UI tab.

Uses streamlit.testing.v1.AppTest.from_function to render the
render_evolution_approval_tab() function in isolation, with HTTP calls
mocked so no running backend is required.

Key design notes
----------------
* AppTest.from_function extracts the inner function's source via
  inspect.getsourcelines() and exec's it in a fresh namespace inside the
  *same* process.  sys.path is therefore shared – we insert the frontend
  directory once at module level and it is available when each _render()
  script runs.
* __file__ inside an AppTest script resolves to the temp script path; we
  must NOT derive paths from __file__ inside _render().
* All mock setup (MagicMock, patch) must be imported inside _render() so
  the extracted script is self-contained.
"""
from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

# ── Ensure the frontend package is importable inside AppTest scripts ──────────
_FRONTEND_DIR = str(Path(__file__).resolve().parent.parent / "frontend")
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

# ── Shared fixture data ────────────────────────────────────────────────────────
_SINGLE_PROPOSAL = [
    {
        "status": "proposed",
        "timestamp": "2026-04-06T13:30:56+00:00",
        "hash": "abc123def456full",
        "meta_review": {"trades": 240, "win_rate": 0.5458, "net_pnl": 842.5, "sharpe": 0.84},
        "champion": {
            "name": "champion",
            "hyperparams": {"max_risk_percent": 1.0, "fast_path_threshold": 0.78},
        },
        "challengers": [
            {
                "name": "challenger_a",
                "prompt_tweak": "More conservative.",
                "hyperparam_suggestion": {"fast_path_threshold": 0.82, "max_risk_percent": 0.9},
                "score": 53.86,
                "confidence": 99.0,
                "risk_penalty": 0.0,
            },
            {
                "name": "challenger_b",
                "prompt_tweak": "Trend bias.",
                "hyperparam_suggestion": {"fast_path_threshold": 0.75},
                "score": 49.36,
                "confidence": 99.0,
                "risk_penalty": 4.5,
            },
        ],
        "best_candidate": {"name": "challenger_a", "score": 53.86, "confidence": 99.0},
        "proposal": {"confidence": 99.0, "backtest_green": True, "safety_ok": False},
    }
]


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_evolution_approval_tab_renders_with_proposals() -> None:
    """Tab renders without error when open proposals are present."""

    def _render() -> None:
        from unittest.mock import MagicMock, patch
        from evolution_approval import render_evolution_approval_tab
        _mock = MagicMock()
        _mock.ok = True
        _mock.json.return_value = [
            {
                "status": "proposed", "timestamp": "2026-04-06T13:30:56+00:00",
                "hash": "abc123def456full",
                "meta_review": {"trades": 240, "win_rate": 0.5458, "net_pnl": 842.5, "sharpe": 0.84},
                "champion": {"name": "champion", "hyperparams": {"max_risk_percent": 1.0, "fast_path_threshold": 0.78}},
                "challengers": [
                    {"name": "challenger_a", "prompt_tweak": "Conservative.", "hyperparam_suggestion": {"fast_path_threshold": 0.82, "max_risk_percent": 0.9}, "score": 53.86, "confidence": 99.0, "risk_penalty": 0.0},
                    {"name": "challenger_b", "prompt_tweak": "Trend.", "hyperparam_suggestion": {"fast_path_threshold": 0.75}, "score": 49.36, "confidence": 99.0, "risk_penalty": 4.5},
                ],
                "best_candidate": {"name": "challenger_a", "score": 53.86, "confidence": 99.0},
                "proposal": {"confidence": 99.0, "backtest_green": True, "safety_ok": False},
            }
        ]
        with patch("requests.get", return_value=_mock):
            render_evolution_approval_tab("http://localhost:8000", api_key="test-key")

    at = AppTest.from_function(_render, default_timeout=10)
    at.run()

    assert not at.exception, f"AppTest raised: {at.exception}"
    subheaders = [e.value for e in at.subheader]
    assert any("Evolution" in s for s in subheaders), (
        f"Expected 'Evolution' subheader, got: {subheaders}"
    )


def test_evolution_approval_tab_shows_challenger_metrics() -> None:
    """Challenger scores and PnL appear in the rendered metric widgets."""

    def _render() -> None:
        from unittest.mock import MagicMock, patch
        from evolution_approval import render_evolution_approval_tab
        _mock = MagicMock()
        _mock.ok = True
        _mock.json.return_value = [
            {
                "status": "proposed", "timestamp": "2026-04-06T13:30:56+00:00",
                "hash": "abc123",
                "meta_review": {"trades": 240, "win_rate": 0.5458, "net_pnl": 842.5, "sharpe": 0.84},
                "champion": {"name": "champion", "hyperparams": {}},
                "challengers": [
                    {"name": "challenger_a", "prompt_tweak": "A", "hyperparam_suggestion": {"fast_path_threshold": 0.82}, "score": 53.86, "confidence": 99.0, "risk_penalty": 0.0},
                ],
                "best_candidate": {"name": "challenger_a", "score": 53.86, "confidence": 99.0},
                "proposal": {"confidence": 99.0, "backtest_green": True, "safety_ok": False},
            }
        ]
        with patch("requests.get", return_value=_mock):
            render_evolution_approval_tab("http://localhost:8000", api_key="test-key")

    at = AppTest.from_function(_render, default_timeout=10)
    at.run()

    assert not at.exception, f"AppTest raised: {at.exception}"
    metric_values = [str(m.value) for m in at.metric]
    assert any("53" in v or "842" in v or "54" in v or "240" in v for v in metric_values), (
        f"Expected challenger/PnL metrics, got: {metric_values[:10]}"
    )


def test_evolution_approval_tab_empty_state() -> None:
    """When no proposals exist, the 'all caught up' info message is shown."""

    def _render() -> None:
        from unittest.mock import MagicMock, patch
        from evolution_approval import render_evolution_approval_tab
        _mock = MagicMock()
        _mock.ok = True
        _mock.json.return_value = []
        with patch("requests.get", return_value=_mock):
            render_evolution_approval_tab("http://localhost:8000", api_key="test-key")

    at = AppTest.from_function(_render, default_timeout=10)
    at.run()

    assert not at.exception, f"AppTest raised: {at.exception}"
    info_messages = [e.value for e in at.info]
    assert any("caught up" in m for m in info_messages), (
        f"Expected 'caught up' info message, got: {info_messages}"
    )


def test_evolution_approval_tab_approve_button_present() -> None:
    """An Approve button is rendered for each challenger."""

    def _render() -> None:
        from unittest.mock import MagicMock, patch
        from evolution_approval import render_evolution_approval_tab
        _mock = MagicMock()
        _mock.ok = True
        _mock.json.return_value = [
            {
                "status": "proposed", "timestamp": "2026-04-06T13:30:56+00:00",
                "hash": "abc123",
                "meta_review": {"trades": 240, "win_rate": 0.5458, "net_pnl": 842.5, "sharpe": 0.84},
                "champion": {"name": "champion", "hyperparams": {}},
                "challengers": [
                    {"name": "challenger_a", "prompt_tweak": "A", "hyperparam_suggestion": {}, "score": 53.86, "confidence": 99.0, "risk_penalty": 0.0},
                    {"name": "challenger_b", "prompt_tweak": "B", "hyperparam_suggestion": {}, "score": 49.36, "confidence": 99.0, "risk_penalty": 4.5},
                ],
                "best_candidate": {"name": "challenger_a", "score": 53.86, "confidence": 99.0},
                "proposal": {"confidence": 99.0, "backtest_green": True, "safety_ok": False},
            }
        ]
        with patch("requests.get", return_value=_mock):
            render_evolution_approval_tab("http://localhost:8000", api_key="test-key")

    at = AppTest.from_function(_render, default_timeout=10)
    at.run()

    assert not at.exception, f"AppTest raised: {at.exception}"
    button_labels = [b.label for b in at.button]
    approve_buttons = [lbl for lbl in button_labels if "Approve" in lbl]
    assert len(approve_buttons) >= 2, (
        f"Expected at least 2 approve buttons, got: {approve_buttons}"
    )


def test_evolution_approval_tab_no_api_key_shows_input() -> None:
    """When api_key is empty, an 'API Key' text_input field is rendered."""

    def _render() -> None:
        from unittest.mock import MagicMock, patch
        from evolution_approval import render_evolution_approval_tab
        _mock = MagicMock()
        _mock.ok = True
        _mock.json.return_value = []
        with patch("requests.get", return_value=_mock):
            render_evolution_approval_tab("http://localhost:8000", api_key="")

    at = AppTest.from_function(_render, default_timeout=10)
    at.run()

    assert not at.exception, f"AppTest raised: {at.exception}"
    input_labels = [inp.label for inp in at.text_input]
    assert any("API" in lbl for lbl in input_labels), (
        f"Expected API key input field, got: {input_labels}"
    )
