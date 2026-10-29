"""18:17 null-gate: 7/8 FPR, fail-at 4, v2 builder, research lock, holdout assert."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from random import Random

import pytest

from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.holdout import P2_HOLDOUT_START_NS, HoldoutLocked, assert_no_holdout_timestamps
from lumina_research.cycles.null_lock import NULL_LEAK_REASON, NullLeaks, assert_research_allowed
from lumina_research.cycles.null_model import (
    NULL_BUILDER_V1,
    NULL_BUILDER_V2,
    _balance_signed_magnitude,
    _linear_residuals,
    _week_block_shuffle_in_window,
    classify_null_a2,
    fail_closed_hit_count,
)
from lumina_research.cycles.null_only import run_null_only, synthetic_drift_tape
from lumina_research.proof.cli import build_parser, main as proof_main
from tests.research.null_only_stub import write_passing_null_only_json

UTC = timezone.utc


@pytest.mark.unit
def test_four_of_thirty_two_is_fail_not_monitor() -> None:
    assert fail_closed_hit_count(32) == 4
    hit = classify_null_a2(4, 32)
    assert hit.status == "unreliable"
    assert hit.reliable is False
    assert hit.borderline is False
    assert classify_null_a2(3, 32).reliable is True


@pytest.mark.unit
def test_linear_residuals_remove_slope() -> None:
    resid = _linear_residuals([1.0, 2.0, 3.0, 4.0])
    assert all(abs(item) < 1e-12 for item in resid)


@pytest.mark.unit
def test_magnitude_balance_reduces_signed_mass() -> None:
    signs = [1.0, 1.0, -1.0, -1.0]
    moves = [10.0, 1.0, 1.0, 1.0]
    out = _balance_signed_magnitude(signs, moves)
    before = abs(sum(sign * mag for sign, mag in zip(signs, moves, strict=True)))
    after = abs(sum(sign * mag for sign, mag in zip(out, moves, strict=True)))
    assert after <= before
    n_pos = sum(1 for item in out if item > 0.0)
    n_neg = sum(1 for item in out if item < 0.0)
    assert abs(n_pos - n_neg) <= 1


@pytest.mark.unit
def test_week_block_shuffle_in_window_keeps_week_runs() -> None:
    days = (date(2025, 3, 3), date(2025, 3, 4), date(2025, 3, 10), date(2025, 3, 11))
    signs = [1.0, 1.0, -1.0, -1.0]
    shuffled = _week_block_shuffle_in_window(days, signs, Random(20261129))
    assert sorted(shuffled) == sorted(signs)
    pairs = {(shuffled[0], shuffled[1]), (shuffled[2], shuffled[3])}
    assert pairs <= {(1.0, 1.0), (-1.0, -1.0)}


@pytest.mark.unit
def test_holdout_pin_timestamp_is_refused() -> None:
    pin_bar = ResearchBar(
        ts_ns=P2_HOLDOUT_START_NS,
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        volume=1.0,
    )
    with pytest.raises(HoldoutLocked, match="2026-01-28"):
        assert_no_holdout_timestamps((pin_bar,))
    ok = ResearchBar(
        ts_ns=P2_HOLDOUT_START_NS - 1,
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        volume=1.0,
    )
    assert_no_holdout_timestamps((ok,))


@pytest.mark.unit
def test_research_lock_requires_passing_null_only_json(tmp_path: Path) -> None:
    with pytest.raises(NullLeaks, match="strict 7/8"):
        assert_research_allowed(tmp_path)
    leaking = tmp_path / "phase5_p2_null_only_validation.json"
    leaking.write_text(
        json.dumps(
            {
                "strict_gate_pass": True,
                "n_seeds": 32,
                "builder_after": NULL_BUILDER_V2,
                "es_after": {"n_edge": 4},
                "synthetic_after": {"n_edge": 0},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(NullLeaks):
        assert_research_allowed(tmp_path)
    write_passing_null_only_json(tmp_path)
    assert_research_allowed(tmp_path)


@pytest.mark.unit
def test_synthetic_null_only_does_not_unlock_without_es(tmp_path: Path) -> None:
    cycle = run_null_only(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        synthetic=synthetic_drift_tape(),
    )
    assert cycle.synthetic_before.builder == NULL_BUILDER_V1
    assert cycle.synthetic_after.builder == NULL_BUILDER_V2
    assert cycle.synthetic_before.n_seeds == 32
    assert cycle.es_after is None
    assert cycle.strict_gate_pass is False
    assert cycle.holdout_asserted is False
    payload = json.loads(cycle.json_path.read_text(encoding="utf-8"))
    assert payload["templates_run"] is False
    assert payload["research_run"] is False
    assert payload["holdout_opened"] is False
    with pytest.raises(NullLeaks):
        assert_research_allowed(tmp_path / "reports")


@pytest.mark.unit
def test_cli_null_only_and_locked_research(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "null-only", "--es-csv", "local.csv"])
    assert args.cycle == "null-only"
    assert args.es_csv == Path("local.csv")

    class _Fail:
        strict_gate_pass = False

    monkeypatch.setattr("lumina_research.proof.cli.run_null_only", lambda **_kwargs: _Fail())
    assert proof_main(["research", "--cycle", "null-only", "--work-dir", str(tmp_path)]) == 2

    class _Pass:
        strict_gate_pass = True

    monkeypatch.setattr("lumina_research.proof.cli.run_null_only", lambda **_kwargs: _Pass())
    assert proof_main(["research", "--cycle", "null-only", "--work-dir", str(tmp_path)]) == 0

    reports = tmp_path / "locked"
    reports.mkdir()
    code = proof_main(
        [
            "research",
            "--work-dir",
            str(tmp_path / "w"),
            "--report-dir",
            str(reports),
            "--data-dir",
            str(tmp_path / "empty"),
        ]
    )
    assert code == 2
    stderr_note = NULL_LEAK_REASON
    assert "strict 7/8" in stderr_note


@pytest.mark.unit
def test_committed_null_only_json_unlocks_research() -> None:
    reports = Path("experiments/reports")
    payload = json.loads((reports / "phase5_p2_null_only_validation.json").read_text(encoding="utf-8"))
    assert payload["strict_gate_pass"] is True
    assert payload["es_after"]["exact_edge"] == "0/32"
    assert payload["synthetic_after"]["exact_edge"] == "0/32"
    assert payload["holdout_opened"] is False
    assert payload["templates_run"] is False
    assert_research_allowed(reports)


@pytest.mark.unit
def test_synthetic_tape_stays_before_holdout_pin() -> None:
    tape = synthetic_drift_tape()
    last = max(int(bar.ts_ns) for bar in tape.bars)
    assert last < P2_HOLDOUT_START_NS
    first = datetime.fromtimestamp(tape.bars[0].ts_ns / 1_000_000_000, tz=UTC)
    assert first.year == 2025
