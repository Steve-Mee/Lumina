"""Multi-seed live-vs-OOS robustness campaign."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_research.monitoring.acceptance import (
    CAMPAIGN_MIN_SEEDS,
    CAMPAIGN_MIN_SIGNALS,
    DETECTION_RATE_MIN,
    FAR_HEALTHY_MAX,
    FAR_HIGH_VOL_MAX,
    TTD_MAX_TRADING_DAYS,
)
from lumina_research.monitoring.campaign import (
    DEFAULT_CAMPAIGN_INSTRUMENTS,
    DEFAULT_CAMPAIGN_SEEDS,
    DEFAULT_KINDS,
    run_phase4_multiseed_detection,
)
from lumina_research.monitoring.report import write_multiseed_detection_reports
from lumina_research.monitoring.types import ContinuityRefused

REPO_REPORTS = Path("experiments/reports")
_DECAYING = frozenset({"abrupt_decay", "gradual_decay", "regime_shift"})


@pytest.mark.unit
def test_campaign_tiny_covers_all_kinds(tmp_path: Path) -> None:
    report = run_phase4_multiseed_detection(
        audit_dir=tmp_path / "audit",
        experiment_log_dir=tmp_path / "exp",
        n_per_kind=1,
        n_days=24,
        decay_start=4,
        seeds=(7, 13),
        instruments=("MES", "MNQ"),
        kinds=DEFAULT_KINDS,
        report_dir=tmp_path / "reports",
    )
    assert report.n_seeds == 2
    assert report.n_signals == 10
    kinds = {item.kind for item in report.by_kind}
    assert kinds == set(DEFAULT_KINDS)
    assert (tmp_path / "reports" / "phase4_detection_multiseed.json").is_file()


@pytest.mark.unit
def test_campaign_refuses_misaligned_seeds_or_unknown_instrument(tmp_path: Path) -> None:
    with pytest.raises(ContinuityRefused, match="must align"):
        run_phase4_multiseed_detection(
            audit_dir=tmp_path / "audit",
            experiment_log_dir=tmp_path / "exp",
            n_per_kind=1,
            n_days=21,
            seeds=(7,),
            instruments=("MES", "MNQ"),
        )


@pytest.mark.nightly
def test_campaign_three_hundred_signals_ten_seeds(tmp_path: Path) -> None:
    assert len(DEFAULT_CAMPAIGN_SEEDS) >= CAMPAIGN_MIN_SEEDS
    assert len(DEFAULT_CAMPAIGN_INSTRUMENTS) == len(DEFAULT_CAMPAIGN_SEEDS)
    assert set(DEFAULT_CAMPAIGN_INSTRUMENTS) == {"ES", "NQ", "MES", "MNQ"}
    report = run_phase4_multiseed_detection(
        audit_dir=tmp_path / "audit",
        experiment_log_dir=tmp_path / "exp",
        n_per_kind=6,
        n_days=70,
        decay_start=20,
        report_dir=tmp_path / "reports",
    )
    assert report.n_signals >= CAMPAIGN_MIN_SIGNALS
    assert report.n_seeds >= CAMPAIGN_MIN_SEEDS
    assert report.n_decaying >= 180
    assert report.detection_rate >= DETECTION_RATE_MIN
    assert report.max_time_to_detect is not None
    assert report.max_time_to_detect <= TTD_MAX_TRADING_DAYS
    decaying_kinds = {item.kind for item in report.by_kind if item.kind in _DECAYING}
    assert decaying_kinds == _DECAYING
    for kind_row in report.by_kind:
        if kind_row.kind in _DECAYING:
            assert kind_row.detection_rate >= DETECTION_RATE_MIN, kind_row
            assert kind_row.max_time_to_detect is not None, kind_row
            assert kind_row.max_time_to_detect <= TTD_MAX_TRADING_DAYS, kind_row
        if kind_row.kind == "healthy":
            assert kind_row.false_alarm_rate <= FAR_HEALTHY_MAX, kind_row
        if kind_row.kind == "high_vol_healthy":
            assert kind_row.false_alarm_rate <= FAR_HIGH_VOL_MAX, kind_row
    write_dir = REPO_REPORTS
    write_dir.mkdir(parents=True, exist_ok=True)
    write_multiseed_detection_reports(report, write_dir)
    payload = json.loads((write_dir / "phase4_detection_multiseed.json").read_text(encoding="utf-8"))
    assert payload["n_signals"] >= CAMPAIGN_MIN_SIGNALS
    md = (write_dir / "phase4_detection_multiseed.md").read_text(encoding="utf-8")
    assert "detection_rate" in md
