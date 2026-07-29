from __future__ import annotations

import pytest

from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.certificate_evaluator import build_certificate_failure_reasons
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass, stage_pass_trades, stage_progress_pct
from lumina_core.birth.preflight import assess_split_preflight, regime_labels
from lumina_core.birth.purged_split import PurgedSplit


def _ticks(regimes: list[str]) -> list[dict]:
    out: list[dict] = []
    for idx, regime in enumerate(regimes):
        out.append({"regime": regime, "last": 5000.0 + idx, "timestamp": f"2026-01-{idx + 1:02d}T00:00:00Z"})
    return out


@pytest.mark.unit
def test_stage_pass_trades_uses_stage_config() -> None:
    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    assert stage_pass_trades(CurriculumStage.STAGE1_TREND, cfg) == 200


@pytest.mark.unit
def test_stage2_uses_range_flat_ratio() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000, stage2_edgescore_enabled=False)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=300,
        wins=150,
        hold_signals=900,
        total_signals=1000,
        range_hold_signals=210,
        range_total_signals=500,
        range_flat_bars=250,
        range_round_trips=30,
        constitution_violations=0,
        target_trades=3000,
        cfg=cfg,
    )
    assert result.passed is True
    assert "range_flat" in result.message


@pytest.mark.unit
def test_stage_progress_pct_with_cfg() -> None:
    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    pct = stage_progress_pct(100, cfg, stage=CurriculumStage.STAGE1_TREND)
    assert pct == 50.0


@pytest.mark.unit
def test_preflight_rejects_single_regime_holdout() -> None:
    split = PurgedSplit(
        train=_ticks(["TREND_UP"] * 400),
        holdout=_ticks(["NEUTRAL"] * 100),
        holdout_days=5,
        train_days=20,
    )
    report = assess_split_preflight(split, thresholds=BirthCertificateThresholds(min_regimes=3))
    assert report.ok is False
    assert any("holdout_regimes" in reason for reason in report.failure_reasons)


@pytest.mark.unit
def test_preflight_passes_three_regime_holdout() -> None:
    split = PurgedSplit(
        train=_ticks(["TREND_UP", "TREND_DOWN", "NEUTRAL"] * 200),
        holdout=_ticks(["TREND_UP", "TREND_DOWN", "NEUTRAL"] * 200),
        holdout_days=5,
        train_days=20,
    )
    report = assess_split_preflight(
        split,
        thresholds=BirthCertificateThresholds(min_regimes=3, min_holdout_trades=5),
    )
    assert report.ok is True
    assert len(regime_labels(split.holdout)) >= 3


@pytest.mark.unit
def test_certificate_failure_reasons_populated() -> None:
    thresholds = BirthCertificateThresholds()
    reasons = build_certificate_failure_reasons(
        real_data_pct=50.0,
        winrate=0.40,
        sharpe=0.0,
        drawdown=12.0,
        regimes=["NEUTRAL"],
        holdout_trades=10,
        constitution_violations=1,
        thresholds=thresholds,
    )
    assert any(item.startswith("regimes_covered:") for item in reasons)
    assert any(item.startswith("oos_sharpe:") for item in reasons)
    assert any(item.startswith("holdout_trades:") for item in reasons)
