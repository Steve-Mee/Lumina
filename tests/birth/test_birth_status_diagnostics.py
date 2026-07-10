"""Tests for birth status certificate diagnostics merge."""

from __future__ import annotations

import pytest

from lumina_launcher.services.birth_status_diagnostics import merge_certificate_diagnostics


@pytest.mark.unit
def test_merge_prefers_progress_oos_when_rich() -> None:
    progress = {
        "failure_reasons": ["oos_winrate:0.31/0.48"],
        "oos_metrics": {"oos_winrate": 0.31, "oos_sharpe": -5.62},
    }
    checkpoint = {"oos_metrics": {"oos_winrate": 0.99}}
    diag = merge_certificate_diagnostics(progress, checkpoint)
    assert diag["oos_metrics"]["oos_winrate"] == 0.31


@pytest.mark.unit
def test_merge_falls_back_to_checkpoint_oos() -> None:
    progress = {
        "failure_reasons": ["oos_winrate:0.31/0.48"],
    }
    checkpoint = {
        "oos_metrics": {
            "oos_winrate": 0.31,
            "oos_sharpe": -5.62,
            "oos_max_drawdown_pct": 25.46,
        }
    }
    diag = merge_certificate_diagnostics(progress, checkpoint)
    assert diag["oos_metrics"]["oos_winrate"] == 0.31
    assert diag["oos_metrics"]["oos_sharpe"] == -5.62


@pytest.mark.unit
def test_merge_failure_reasons_from_oos_metrics() -> None:
    progress = {
        "oos_metrics": {
            "failure_reasons": ["oos_sharpe:-5.62/0.35"],
            "oos_winrate": 0.31,
        }
    }
    diag = merge_certificate_diagnostics(progress, {})
    assert "oos_sharpe:-5.62/0.35" in diag["failure_reasons"]
