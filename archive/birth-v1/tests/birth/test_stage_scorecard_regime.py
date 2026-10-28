"""Stage scorecard regime distribution tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.stage_scorecard import (
    compute_regime_distribution,
    enrich_progress_scorecard,
    format_regime_distribution_summary,
)


@pytest.mark.unit
def test_compute_regime_distribution() -> None:
    ticks = [
        {"regime": "TREND_UP"},
        {"regime": "TREND_UP"},
        {"regime": "NEUTRAL"},
        {"regime": "TREND_DOWN"},
    ]
    dist = compute_regime_distribution(ticks)
    assert dist["TREND_UP"] == pytest.approx(0.5)
    assert dist["NEUTRAL"] == pytest.approx(0.25)
    assert dist["TREND_DOWN"] == pytest.approx(0.25)


@pytest.mark.unit
def test_enrich_progress_scorecard_adds_regime_summary() -> None:
    payload = enrich_progress_scorecard(
        {
            "curriculum_stage": "stage1_trend",
            "stage_trades": 10,
            "stage_wins": 4,
            "regime_distribution": {"TREND_UP": 0.7, "NEUTRAL": 0.2, "TREND_DOWN": 0.1},
        }
    )
    assert "regime_dominant" in payload
    assert payload["regime_dominant"] == "TREND_UP"
    assert "Trend Up" in str(payload.get("regime_distribution_summary", ""))


@pytest.mark.unit
def test_format_regime_distribution_summary() -> None:
    summary = format_regime_distribution_summary(
        {"TREND_UP": 0.6, "NEUTRAL": 0.3, "TREND_DOWN": 0.1}
    )
    assert "Trend Up 60%" in summary
