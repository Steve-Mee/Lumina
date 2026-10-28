"""Multi-seed kill-rate robustness. Does not retune generators or gate floors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_research.agents.loop import (
    DEFAULT_MULTISEED_INSTRUMENTS,
    DEFAULT_MULTISEED_SEEDS,
    run_multiseed_kill_rate,
)
from lumina_research.agents.report import write_multiseed_kill_rate_reports

REPO_REPORTS = Path("experiments/reports")


@pytest.mark.slow
def test_multiseed_kill_rate_robustness(tmp_path: Path) -> None:
    report = run_multiseed_kill_rate(
        audit_dir=tmp_path / "audit",
        experiment_log_dir=tmp_path / "exp",
        report_dir=tmp_path / "reports",
    )
    assert len(report.seeds) >= 10
    assert len(DEFAULT_MULTISEED_SEEDS) >= 10
    assert len(DEFAULT_MULTISEED_INSTRUMENTS) == len(DEFAULT_MULTISEED_SEEDS)
    assert report.n_hypotheses >= 300
    assert set(DEFAULT_MULTISEED_INSTRUMENTS) == {"ES", "NQ", "MES", "MNQ"}
    for row in report.seeds:
        assert row.n_hypotheses >= 30
        assert 0.0 <= row.kill_rate <= 1.0
        for item in row.candidates:
            assert item.oos_values is not None
            assert item.n_oos_windows >= 6 or item.passed_gate is False
            assert isinstance(item.reject_reasons, tuple)
    md = (tmp_path / "reports" / "phase2_kill_rate_multiseed.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "reports" / "phase2_kill_rate_multiseed.json").read_text(encoding="utf-8"))
    assert "kill rate" in md.lower()
    assert "false-kill" in md.lower()
    assert "false-survivor" in md.lower()
    assert "OOS" in md or "oos" in md.lower()
    assert payload["n_hypotheses"] == report.n_hypotheses
    assert payload["seeds"]
    for seed_row in payload["seeds"]:
        for candidate in seed_row["candidates"]:
            assert "oos_distribution" in candidate
            assert "values" in candidate["oos_distribution"]
    write_dir = REPO_REPORTS
    write_multiseed_kill_rate_reports(report, write_dir)
    assert (write_dir / "phase2_kill_rate_multiseed.md").is_file()
    assert (write_dir / "phase2_kill_rate_multiseed.json").is_file()
    # Honest threshold: do not retune data if this fails.
    assert report.kill_rate > 0.90, (
        f"overall kill_rate={report.kill_rate:.4f} "
        f"false_kill={report.false_kill_rate:.4f} "
        f"false_survivor={report.false_survivor_rate:.4f} "
        + ", ".join(f"seed={row.seed}:{row.kill_rate:.4f}" for row in report.seeds)
    )
