"""Mutation testing of ungated_place_block + research_bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.order_gatekeeper.s0_mutant_kills import run as run_kills
from tests.order_gatekeeper.s0_mutants import (
    S0_MUTATION_EQUIVALENT_MAX_FRAC,
    S0_MUTATION_KILL_RATE_MIN,
    S0_MUTATION_MIN_MUTANTS,
    _run_one,
    equivalent_reason,
    insert_open_mutant,
    iter_mutants,
    run_mutation_campaign,
    write_mutation_reports,
)

REPO_REPORTS = Path("experiments/reports")


@pytest.mark.unit
def test_kill_battery_passes_on_unmutated_code() -> None:
    run_kills()


@pytest.mark.unit
def test_mutant_iterator_finds_sites() -> None:
    mutants = iter_mutants(S0_MUTATION_MIN_MUTANTS)
    assert len(mutants) >= S0_MUTATION_MIN_MUTANTS
    files = {item.path.split("/")[-1] for item in mutants}
    assert "ungated_place_block.py" in files
    assert "shadow_runtime.py" in files or "costs.py" in files or "market_health.py" in files


@pytest.mark.unit
def test_overlay_kills_open_place_mutant() -> None:
    killed = _run_one(insert_open_mutant(), 8.0)
    assert killed.killed is True, killed.detail


@pytest.mark.nightly
@pytest.mark.slow
def test_s0_mutation_campaign_kills_most_mutants(tmp_path: Path) -> None:
    report = run_mutation_campaign(limit=S0_MUTATION_MIN_MUTANTS, timeout=20.0, workers=4)
    write_mutation_reports(report, tmp_path / "reports")
    write_mutation_reports(report, REPO_REPORTS)
    assert report.n_mutants >= S0_MUTATION_MIN_MUTANTS
    assert report.n_excluded / report.n_mutants <= S0_MUTATION_EQUIVALENT_MAX_FRAC
    assert report.kill_rate >= S0_MUTATION_KILL_RATE_MIN
    payload = json.loads((REPO_REPORTS / "s0_mutation.json").read_text(encoding="utf-8"))
    assert payload["n_mutants"] >= S0_MUTATION_MIN_MUTANTS
    assert payload["kill_rate"] >= S0_MUTATION_KILL_RATE_MIN
    md = (REPO_REPORTS / "s0_mutation.md").read_text(encoding="utf-8")
    assert "kill rate" in md.lower()
    for item in report.excluded:
        assert equivalent_reason(item), f"excluded without justification {item.description}"
