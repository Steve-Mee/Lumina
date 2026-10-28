"""End-to-end Phase 3: mutations go through the Phase 2 event flow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.schemas_research import RESEARCH_PROMOTION_TOPIC
from lumina_research.evolution.loop import run_multiseed_evolution, run_phase3_evolution
from lumina_research.evolution.report import write_evolution_reports
from lumina_research.evolution.types import default_parent
from tests.research.phase3_harness import make_runtime

REPO_REPORTS = Path("experiments/reports")


@pytest.mark.unit
def test_evolution_loop_kills_noise_and_counts_trials(tmp_path: Path) -> None:
    report = run_phase3_evolution(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        n_noise=2,
        seed=20261028,
        report_dir=tmp_path / "reports",
    )
    assert report.n_mutations == 4
    assert report.n_admitted == 4
    assert report.n_hypotheses == 4
    assert report.n_trials_end > report.n_trials_start
    assert report.n_trials_start >= 4
    assert report.floors_intact is True
    assert report.risk_core_intact is True
    assert report.n_noise_promoted == 0
    assert report.n_promoted >= 1
    planted = [item for item in report.candidates if item.planted]
    assert planted
    assert any(item.promoted for item in planted)
    for item in report.candidates:
        assert item.oos_values is not None
        assert isinstance(item.reject_reasons, tuple)
    md = (tmp_path / "reports" / "phase3_evolution.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "reports" / "phase3_evolution.json").read_text(encoding="utf-8"))
    assert "kill rate" in md.lower()
    assert payload["candidates"]
    write_evolution_reports(report, REPO_REPORTS)
    assert (REPO_REPORTS / "phase3_evolution.md").is_file()


@pytest.mark.unit
def test_tiny_equity_risk_core_blocks_promotion(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path, equity=1.0)
    parent = default_parent()
    mutation = runtime.birth.open_window(parent, seed=13, index=0)
    report = runtime.process((mutation,), seed=13)
    assert report.n_admitted == 1
    assert report.n_hypotheses == 1
    if report.candidates and report.candidates[0].passed_gate:
        assert report.n_promoted == 0
        assert not runtime.bus.history(RESEARCH_PROMOTION_TOPIC)


@pytest.mark.unit
def test_process_without_report_dir(tmp_path: Path) -> None:
    report = run_phase3_evolution(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        n_noise=1,
        seed=11,
    )
    assert report.n_mutations == 3
    assert (tmp_path / "reports").exists() is False


@pytest.mark.unit
def test_multiseed_align_check(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="align"):
        run_multiseed_evolution(
            audit_dir=tmp_path / "a",
            experiment_log_dir=tmp_path / "e",
            seeds=(1, 2),
            instruments=("MES",),
        )


@pytest.mark.unit
def test_multiseed_without_report_dir(tmp_path: Path) -> None:
    report = run_multiseed_evolution(
        audit_dir=tmp_path / "a",
        experiment_log_dir=tmp_path / "e",
        seeds=(11,),
        instruments=("MES",),
        n_noise=0,
        n_overfit=0,
    )
    assert report.n_mutations == 2
    assert report.n_hypotheses == 2
