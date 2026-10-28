"""Evolution Proof gate (ADR-0026)."""

from __future__ import annotations

import json
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
def test_evaluate_winrate_lift_is_diagnostic_not_a_pass() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.38,
        polish_oos_winrate=0.44,
        holdout_trades=600,
        cfg=EvolutionProofConfig(min_winrate_lift=0.05, polish_oos_winrate_min=0.45),
    )
    assert result.passed is False
    assert result.winrate_lift == pytest.approx(0.06)
    assert "parent_replay_missing" in result.reasons


@pytest.mark.unit
def test_evaluate_fails_when_paired_ci_is_under_the_floor() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.35,
        polish_oos_winrate=0.36,
        holdout_trades=600,
        parent_replay_present=True,
        paired_ci_low=0.014,
        paired_delta=0.02,
        child_median_win_r=0.4,
        parent_median_win_r=0.45,
    )
    assert result.passed is False
    assert any("paired regret CI" in r and "<" in r for r in result.reasons)


@pytest.mark.unit
def test_evaluate_passes_on_paired_ci() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.35,
        polish_oos_winrate=0.36,
        holdout_trades=600,
        parent_replay_present=True,
        paired_ci_low=0.06,
        paired_delta=0.1,
        child_median_win_r=0.4,
        parent_median_win_r=0.45,
    )
    assert result.passed is True
    assert any("paired regret CI" in r for r in result.reasons)


@pytest.mark.unit
def test_scalp_blocks_even_when_oos_clears() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.35,
        polish_oos_winrate=0.50,
        holdout_trades=600,
        parent_replay_present=True,
        paired_ci_low=0.2,
        child_median_win_r=0.05,
        parent_median_win_r=0.4,
    )
    assert result.passed is False
    assert any("median_win_r_collapsed" in r for r in result.reasons)


def _day_book(day: str, trade_r: float, plant: bool = False) -> dict[str, object]:
    return {"day": day, "trade_r": trade_r, "plant": plant, "pnl": trade_r}


@pytest.mark.unit
def test_paired_book_ignores_plant_and_fails_closed_without_days() -> None:
    from lumina_core.birth.evolution_proof_gate import paired_book_from_rows

    child = [_day_book("2026-01-01", trade_r=1.0, plant=True)]
    child.append({"trade_r": 0.2, "plant": False})
    parent = [_day_book("2026-01-01", trade_r=-0.2)]
    book = paired_book_from_rows(child, parent)
    assert book["parent_replay_present"] is False


@pytest.mark.unit
def test_require_policy_session_days_refuses_an_undated_policy_close() -> None:
    from lumina_core.birth.evolution_proof_gate import require_policy_session_days

    require_policy_session_days([_day_book("2026-04-01", 0.2)])
    require_policy_session_days([{"plant_entry": True, "pnl": 1.0, "trade_r": 0.1}])
    with pytest.raises(RuntimeError, match="no session day"):
        require_policy_session_days([{"pnl": 1.0, "trade_r": 0.2, "plant_entry": False}])


def test_attach_session_days_uses_the_holdout_timestamp_and_does_not_invent_one() -> None:
    from lumina_core.birth.evolution_proof_gate import attach_session_days, paired_book_from_rows

    tape = [{"timestamp": f"2026-04-{index + 1:02d}T14:30:00"} for index in range(8)]
    child = [{"entry_bar_index": index, "trade_r": 0.3, "plant": False} for index in range(8)]
    parent = [{"entry_bar_index": index, "trade_r": -0.2, "plant": False} for index in range(8)]
    stamped_child = attach_session_days(child, tape)
    stamped_parent = attach_session_days(parent, tape)
    assert stamped_child[0]["ts_iso"].startswith("2026-04-01")
    book = paired_book_from_rows(stamped_child, stamped_parent)
    assert book["parent_replay_present"] is True
    assert float(book["paired_ci_low"]) >= 0.05
    undated = attach_session_days([{"entry_bar_index": 3, "trade_r": 0.1}], [{"last": 1.0}])
    assert "ts_iso" not in undated[0]
    assert paired_book_from_rows(undated, undated)["parent_replay_present"] is False


@pytest.mark.unit
def test_paired_book_day_block_clears_when_child_is_better() -> None:
    from lumina_core.birth.evolution_proof_gate import paired_book_from_rows

    child: list[dict[str, object]] = []
    parent: list[dict[str, object]] = []
    for index in range(8):
        day = f"2026-01-{index + 1:02d}"
        child.append(_day_book(day, 0.3))
        child.append(_day_book(day, 0.1, plant=True))
        parent.append(_day_book(day, -0.2))
    book = paired_book_from_rows(child, parent)
    assert book["parent_replay_present"] is True
    assert book["paired_delta"] == pytest.approx(0.5)
    assert float(book["paired_ci_low"]) >= 0.05
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.35,
        polish_oos_winrate=0.36,
        holdout_trades=600,
        child_closes=child,
        parent_closes=parent,
    )
    assert result.passed is True
    assert result.child_median_win_r == pytest.approx(0.3)


@pytest.mark.unit
def test_evaluate_fails_insufficient_trades_and_lift() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.40,
        polish_oos_winrate=0.41,
        holdout_trades=100,
    )
    assert result.passed is False


@pytest.mark.unit
def test_evaluate_fails_n_133_despite_five_pp_lift() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.333,
        polish_oos_winrate=0.436,
        holdout_trades=133,
    )
    assert result.passed is False
    assert any("133" in r and "500" in r for r in result.reasons)


@pytest.mark.unit
def test_evolution_proof_passed_fail_closed_on_missing_record(tmp_path: Path) -> None:
    assert evolution_proof_passed(tmp_path) is False


@pytest.mark.unit
def test_evolution_proof_passed_legacy_grandfather_opt_in(tmp_path: Path) -> None:
    assert evolution_proof_passed(tmp_path, allow_legacy_grandfather=True) is False


@pytest.mark.unit
def test_record_and_evaluate_persists_state(tmp_path: Path) -> None:
    result = record_and_evaluate_at_certificate(
        tmp_path,
        eval_result={"oos_winrate": 0.50, "holdout_trades": 800},
        birth_exit_winrate=0.42,
    )
    assert result.passed is True
    assert evolution_proof_passed(tmp_path) is True
    rec = json.loads((tmp_path / "state" / "lumina_evolution_proof.json").read_text(encoding="utf-8"))
    assert rec["oos_winrate"] == rec["polish_oos_winrate"] == 0.50
