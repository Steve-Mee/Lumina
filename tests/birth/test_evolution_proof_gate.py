"""Evolution Proof gate (ADR-0026)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.evolution_proof_gate import (
    EvolutionProofConfig,
    evaluate_evolution_proof,
    evolution_proof_passed,
    record_and_evaluate_at_certificate,
)


@pytest.mark.unit
def test_evaluate_passes_on_polish_oos_threshold() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.35,
        polish_oos_winrate=0.46,
        holdout_trades=600,
    )
    assert result.passed is True
    assert any("polish_oos_winrate" in r for r in result.reasons)


@pytest.mark.unit
def test_evaluate_passes_on_winrate_lift() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.38,
        polish_oos_winrate=0.44,
        holdout_trades=600,
        cfg=EvolutionProofConfig(min_winrate_lift=0.05, polish_oos_winrate_min=0.45),
    )
    assert result.passed is True
    assert result.winrate_lift == pytest.approx(0.06)


@pytest.mark.unit
def test_evaluate_fails_insufficient_trades_and_lift() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.40,
        polish_oos_winrate=0.41,
        holdout_trades=100,
    )
    assert result.passed is False


@pytest.mark.unit
def test_evolution_proof_passed_grandfathers_missing_record(tmp_path: Path) -> None:
    assert evolution_proof_passed(tmp_path) is True


@pytest.mark.unit
def test_record_and_evaluate_persists_state(tmp_path: Path) -> None:
    result = record_and_evaluate_at_certificate(
        tmp_path,
        eval_result={"oos_winrate": 0.50, "holdout_trades": 800},
        birth_exit_winrate=0.42,
    )
    assert result.passed is True
    assert evolution_proof_passed(tmp_path) is True
