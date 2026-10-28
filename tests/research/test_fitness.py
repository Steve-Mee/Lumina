"""Fitness refuses IS PnL and missing gate results."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_research.fitness import FitnessRefused, compute_fitness
from lumina_research.validation.gate import passes_validation_gate
from tests.research.test_gate import _good


@pytest.mark.unit
def test_fitness_uses_gate_report_not_is_pnl(tmp_path: Path) -> None:
    _passed, report = passes_validation_gate(_good(tmp_path / "f.jsonl"))
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

    passed, report = passes_validation_gate(_good(tmp_path / "g.jsonl", oos_distribution=OOSDistribution.missing()))
    assert passed is False
    with pytest.raises(FitnessRefused, match="missing"):
        compute_fitness(report, turnover=0.0)
