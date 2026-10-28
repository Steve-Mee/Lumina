"""Multi-seed live-vs-OOS robustness campaign."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_research.monitoring.campaign import (
    DEFAULT_CAMPAIGN_INSTRUMENTS,
    DEFAULT_CAMPAIGN_SEEDS,
    DEFAULT_KINDS,
    run_phase4_multiseed_detection,
)
from lumina_research.monitoring.report import write_multiseed_detection_reports

REPO_REPORTS = Path("experiments/reports")


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


@pytest.mark.slow
@pytest.mark.timeout(120)
def test_campaign_three_hundred_signals_ten_seeds(tmp_path: Path) -> None:
    assert len(DEFAULT_CAMPAIGN_SEEDS) >= 10
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
    assert report.n_signals >= 300
    assert report.n_seeds >= 10
    assert report.n_decaying >= 180
    assert report.detection_rate >= 0.80
    assert report.false_alarm_rate <= 0.20
    assert report.median_time_to_detect is not None
    decaying_kinds = {item.kind for item in report.by_kind if item.kind in {"abrupt_decay", "gradual_decay", "regime_shift"}}
    assert decaying_kinds == {"abrupt_decay", "gradual_decay", "regime_shift"}
    write_dir = REPO_REPORTS
    write_dir.mkdir(parents=True, exist_ok=True)
    write_multiseed_detection_reports(report, write_dir)
    payload = json.loads((write_dir / "phase4_detection_multiseed.json").read_text(encoding="utf-8"))
    assert payload["n_signals"] >= 300
    md = (write_dir / "phase4_detection_multiseed.md").read_text(encoding="utf-8")
    assert "detection_rate" in md
