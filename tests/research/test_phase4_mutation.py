"""Mutation testing of lumina_research/monitoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.research.phase4_mutant_kills import run as run_kills
from tests.research.phase4_mutants import (
    _run_one,
    iter_mutants,
    justify_survivor,
    run_mutation_campaign,
    write_mutation_reports,
)

REPO_REPORTS = Path("experiments/reports")


@pytest.mark.unit
def test_kill_battery_passes_on_unmutated_code() -> None:
    run_kills()


@pytest.mark.unit
def test_mutant_iterator_finds_sites() -> None:
    mutants = iter_mutants(40)
    assert len(mutants) >= 40
    files = {item.path.split("/")[-1] for item in mutants}
    assert len(files) >= 4
    assert "registry.py" in files or "statistics.py" in files


@pytest.mark.unit
def test_overlay_kills_raise_to_pass_on_insert() -> None:
    """Guard against cwd shadowing the mutant overlay on sys.path."""
    needle = "direct registry insertion is forbidden"
    chosen = next(
        (
            item
            for item in iter_mutants(250)
            if item.path.endswith("registry.py") and needle not in item.source
        ),
        None,
    )
    assert chosen is not None
    killed = _run_one(chosen, 20.0)
    assert killed.killed is True, killed.detail


@pytest.mark.nightly
@pytest.mark.slow
def test_monitoring_mutation_campaign_kills_most_mutants(tmp_path: Path) -> None:
    report = run_mutation_campaign(limit=320, timeout=20.0, workers=4)
    write_mutation_reports(report, tmp_path / "reports")
    write_mutation_reports(report, REPO_REPORTS)
    assert report.n_mutants >= 300
    assert report.kill_rate >= 0.20
    payload = json.loads((REPO_REPORTS / "phase4_mutation.json").read_text(encoding="utf-8"))
    assert payload["n_mutants"] >= 300
    md = (REPO_REPORTS / "phase4_mutation.md").read_text(encoding="utf-8")
    assert "kill rate" in md.lower()
    for survivor in report.survivors:
        reason = justify_survivor(survivor)
        assert reason, f"unjustified survivor {survivor.description}: {survivor.detail}"
