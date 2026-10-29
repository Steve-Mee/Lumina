"""Mutation testing of P2 artefact-fix modules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.research.p2_mutant_kills import run as run_kills
from tests.research.p2_mutants import (
    _run_one,
    equivalent_reason,
    insert_refuse_mutant,
    iter_mutants,
    run_mutation_campaign,
    write_mutation_reports,
)

REPO_REPORTS = Path("experiments/reports")
MUTATION_MIN_MUTANTS = 300
MUTATION_KILL_RATE_MIN = 0.80


@pytest.mark.unit
def test_p2_kill_battery_passes_on_unmutated_code() -> None:
    run_kills()


@pytest.mark.unit
def test_p2_mutant_iterator_finds_sites() -> None:
    mutants = iter_mutants(40)
    assert len(mutants) >= 40
    files = {item.path.split("/")[-1] for item in mutants}
    assert len(files) >= 4


@pytest.mark.unit
def test_p2_overlay_kills_raise_to_pass_on_insert() -> None:
    killed = _run_one(insert_refuse_mutant(), 12.0)
    assert killed.killed is True, killed.detail


@pytest.mark.nightly
@pytest.mark.slow
def test_p2_mutation_campaign_kills_most_mutants(tmp_path: Path) -> None:
    report = run_mutation_campaign(limit=MUTATION_MIN_MUTANTS, timeout=20.0, workers=4)
    write_mutation_reports(report, tmp_path / "reports")
    write_mutation_reports(report, REPO_REPORTS)
    assert report.n_mutants >= MUTATION_MIN_MUTANTS
    assert report.kill_rate >= MUTATION_KILL_RATE_MIN
    payload = json.loads((REPO_REPORTS / "phase5_p2_mutation.json").read_text(encoding="utf-8"))
    assert payload["n_mutants"] >= MUTATION_MIN_MUTANTS
    assert payload["kill_rate"] >= MUTATION_KILL_RATE_MIN
    for item in report.excluded:
        assert equivalent_reason(item), f"excluded without justification {item.description}"
