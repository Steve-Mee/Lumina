"""Multi-seed evolution: noise dies, floors and Risk Core do not drift."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_research.evolution.integrity import capture_integrity
from lumina_research.evolution.loop import (
    DEFAULT_MULTISEED_INSTRUMENTS,
    DEFAULT_MULTISEED_SEEDS,
    run_multiseed_evolution,
)
from lumina_research.evolution.report import write_multiseed_evolution_reports
from lumina_research.validation.thresholds import (
    FLOOR_DSR_PROBABILITY_MIN,
    FLOOR_MIN_OOS_WINDOWS,
    FLOOR_PBO_HARD_REJECT,
    FLOOR_PBO_WARNING,
    FLOOR_WFE_MIN,
)

REPO_REPORTS = Path("experiments/reports")


@pytest.mark.unit
def test_multiseed_evolution_noise_dies_without_floor_drift(tmp_path: Path) -> None:
    before = capture_integrity()
    report = run_multiseed_evolution(
        audit_dir=tmp_path / "audit",
        experiment_log_dir=tmp_path / "exp",
        report_dir=tmp_path / "reports",
        n_noise=2,
    )
    after = capture_integrity()
    assert len(report.seeds) >= 10
    assert len(DEFAULT_MULTISEED_SEEDS) >= 10
    assert len(DEFAULT_MULTISEED_INSTRUMENTS) == len(DEFAULT_MULTISEED_SEEDS)
    assert set(DEFAULT_MULTISEED_INSTRUMENTS) == {"ES", "NQ", "MES", "MNQ"}
    assert report.n_hypotheses >= 40
    assert report.floors_intact is True
    assert report.risk_core_intact is True
    assert report.n_noise_promoted == 0
    assert report.n_noise_mutations >= 20
    for row in report.seeds:
        assert row.report.n_noise_promoted == 0
        assert row.report.floors_intact is True
        assert row.report.risk_core_intact is True
        assert row.report.n_trials_end > row.report.n_trials_start
        for item in row.report.candidates:
            assert item.oos_values is not None
    assert before.floors == after.floors
    assert before.live_risk_hash == after.live_risk_hash
    assert before.research_risk_hash == after.research_risk_hash
    assert before.thresholds_toml_hash == after.thresholds_toml_hash
    assert FLOOR_DSR_PROBABILITY_MIN == 0.95
    assert FLOOR_WFE_MIN == 0.5
    assert FLOOR_PBO_HARD_REJECT == 0.50
    assert FLOOR_PBO_WARNING == 0.25
    assert FLOOR_MIN_OOS_WINDOWS == 6
    md = (tmp_path / "reports" / "phase3_evolution_multiseed.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "reports" / "phase3_evolution_multiseed.json").read_text(encoding="utf-8"))
    assert "kill rate" in md.lower()
    assert payload["n_hypotheses"] == report.n_hypotheses
    write_multiseed_evolution_reports(report, REPO_REPORTS)
    assert (REPO_REPORTS / "phase3_evolution_multiseed.md").is_file()
