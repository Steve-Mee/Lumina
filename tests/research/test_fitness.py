"""Fitness refuses IS PnL and missing gate results."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_research.fitness import FitnessRefused, compute_fitness
from lumina_research.validation.gate import passes_validation_gate
from tests.research.test_gate import _good, _registry


@pytest.mark.unit
def test_fitness_uses_gate_report_not_is_pnl(tmp_path: Path) -> None:
    path = tmp_path / "f.jsonl"
    _passed, report = passes_validation_gate(_good(path), registry=_registry(path))
    score = compute_fitness(report, turnover=0.1)
    assert score.gate_passed is True
    assert score.value > 0.0
    with pytest.raises(FitnessRefused, match="in-sample"):
        compute_fitness(report, turnover=0.1, in_sample_pnl=12.0)
    with pytest.raises(FitnessRefused, match="in-sample"):
        compute_fitness(report, turnover=0.1, is_pnl=1.0)


@pytest.mark.unit
def test_fitness_refuses_incomplete_report(tmp_path: Path) -> None:
    from lumina_research.validation.types import OOSDistribution

    path = tmp_path / "g.jsonl"
    passed, report = passes_validation_gate(
        _good(path, oos_distribution=OOSDistribution.missing()),
        registry=_registry(path),
    )
    assert passed is False
    with pytest.raises(FitnessRefused, match="missing"):
        compute_fitness(report, turnover=0.0)


@pytest.mark.unit
def test_turnover_and_dsr_penalties_are_monotonic(tmp_path: Path) -> None:
    path = tmp_path / "m.jsonl"
    _passed, report = passes_validation_gate(_good(path), registry=_registry(path))
    low_turn = compute_fitness(report, turnover=0.1)
    high_turn = compute_fitness(report, turnover=1.5)
    assert high_turn.turnover_penalty > low_turn.turnover_penalty
    assert high_turn.value < low_turn.value

    from dataclasses import replace

    high_dsr = replace(
        report.dsr,
        probability=0.99,
    )
    low_dsr = replace(
        report.dsr,
        probability=0.50,
    )
    high_report = replace(report, dsr=high_dsr, passed=False)
    low_report = replace(report, dsr=low_dsr, passed=False)
    high_score = compute_fitness(high_report, turnover=0.1)
    low_score = compute_fitness(low_report, turnover=0.1)
    assert low_score.dsr_penalty > high_score.dsr_penalty
    assert low_score.value < high_score.value
