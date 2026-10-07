"""Exam truth for every Awakening plant. Floors stay. Finished runs are not regraded."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from lumina_core.birth.certificate_evaluator import sharpe_from_pnl
from lumina_core.birth.evolution_proof_gate import paired_book_from_rows
from lumina_core.birth.foundation_metrics import s5_holdout_sharpe
from lumina_core.maturity.awakening.clock import classify_stable
from lumina_core.maturity.awakening.keep_best import parent_replay_card
from lumina_core.maturity.awakening.law import snapshot_from_workspace
from lumina_core.maturity.awakening.weight_sha import pack_policy_weight_zip, policy_weight_sha256
from lumina_core.maturity.phase_runners.awakening_shot import (
    INCUMBENT_LEDGER_NAME,
    INCUMBENT_PARENT_LEDGER_NAME,
    LEDGER_NAME,
    artifacts_dir,
)
from lumina_core.maturity.phase_runners.awakening_shot_io import (
    _policy_skill_from_ledger,
    default_eval,
)


def _pnl() -> list[float]:
    """Negative trade book whose information ratio stays above -2 and whose √252 form does not."""
    return [-1.0, -1.0, -1.0, -1.0, 1.0] * 4


def _line(day: str, trade_r: float, pnl: float) -> str:
    return json.dumps(
        {"day": day, "trade_r": trade_r, "pnl": pnl, "plant": False, "ts_iso": f"{day}T15:00:00Z"}
    )


def _write_ledger(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


@pytest.mark.unit
def test_policy_sharpe_is_the_trade_ratio_not_a_session_year(tmp_path: Path) -> None:
    pnl = _pnl()
    ratio = s5_holdout_sharpe(pnl)
    annual = sharpe_from_pnl(pnl)
    assert ratio is not None
    assert ratio > -2.0
    assert annual == pytest.approx(float(ratio) * math.sqrt(252.0))
    assert annual <= -3.0
    assert classify_stable(n_b=500, sharpe=float(ratio), dd_pct=9.0) == "STABLE"
    assert classify_stable(n_b=500, sharpe=annual, dd_pct=9.0) == "GRIND_REGRESS"

    ledger = tmp_path / "policy.jsonl"
    _write_ledger(ledger, [_line("2026-03-01", -0.2, value) for value in pnl])
    skill = _policy_skill_from_ledger(ledger)
    assert skill["sharpe"] == pytest.approx(float(ratio))
    assert skill["sharpe"] != pytest.approx(annual)


@pytest.mark.unit
def test_grind_table_uses_the_same_trade_ratio() -> None:
    from lumina_core.birth.awakening_grind import grind_table_from_rows

    pnl = _pnl()
    rows = [{"pnl": value, "trade_r": -0.2, "plant": False} for value in pnl]
    metrics = grind_table_from_rows(rows, holdout_exhausted=True, frozen_loaded=True)
    ratio = s5_holdout_sharpe(pnl)
    assert ratio is not None
    assert metrics.oos_sharpe == pytest.approx(float(ratio))
    assert metrics.oos_sharpe != pytest.approx(sharpe_from_pnl(pnl))


@pytest.mark.unit
def test_default_eval_passes_the_sample_window_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    metrics = SimpleNamespace(
        n=10,
        policy_trades=0,
        wr=0.4,
        oos_sharpe=-0.2,
        oos_dd_pct=9.0,
        occupancy=0.90,
        occupancy_at_nb=0.31,
        mean_r=-0.2,
        edge=0.01,
        holdout_exhausted=True,
        stopped=False,
    )
    monkeypatch.setattr(
        "lumina_core.birth.awakening_grind_run.run_evaluate_only",
        lambda **_kwargs: metrics,
    )
    monkeypatch.setattr(
        "lumina_core.birth.awakening_grind_run.resolve_awakening_occupancy_seed",
        lambda *_args, **_kwargs: (None, "missing"),
    )
    child = tmp_path / "child.zip"
    child.write_bytes(pack_policy_weight_zip(b"child-weights"))
    out = default_eval(
        holdout=[],
        child_path=child,
        workspace=tmp_path,
        reports=tmp_path,
        ledger_path=tmp_path / "missing.jsonl",
    )
    assert out["occupancy"] == pytest.approx(0.90)
    assert out["occupancy_at_nb"] == pytest.approx(0.31)


@pytest.mark.unit
def test_missing_sample_window_is_not_filled_from_the_full_tape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    metrics = SimpleNamespace(
        n=10,
        policy_trades=0,
        wr=0.4,
        oos_sharpe=-0.2,
        oos_dd_pct=9.0,
        occupancy=0.90,
        occupancy_at_nb=None,
        mean_r=-0.2,
        edge=0.01,
        holdout_exhausted=True,
        stopped=False,
    )
    monkeypatch.setattr(
        "lumina_core.birth.awakening_grind_run.run_evaluate_only",
        lambda **_kwargs: metrics,
    )
    monkeypatch.setattr(
        "lumina_core.birth.awakening_grind_run.resolve_awakening_occupancy_seed",
        lambda *_args, **_kwargs: (None, "missing"),
    )
    child = tmp_path / "child.zip"
    child.write_bytes(pack_policy_weight_zip(b"child-weights"))
    out = default_eval(
        holdout=[],
        child_path=child,
        workspace=tmp_path,
        reports=tmp_path,
        ledger_path=tmp_path / "missing.jsonl",
    )
    assert out["occupancy_at_nb"] is None


@pytest.mark.unit
def test_weight_resave_is_still_the_frozen_parent() -> None:
    same = pack_policy_weight_zip(b"weights", serialization_id=b"first-save")
    resaved = pack_policy_weight_zip(b"weights", serialization_id=b"second-save")
    changed = pack_policy_weight_zip(b"weights-changed", serialization_id=b"first-save")
    assert same != resaved
    left = Path(__file__).with_name("_w1.zip")
    right = Path(__file__).with_name("_w2.zip")
    other = Path(__file__).with_name("_w3.zip")
    try:
        left.write_bytes(same)
        right.write_bytes(resaved)
        other.write_bytes(changed)
        assert policy_weight_sha256(left) == policy_weight_sha256(right)
        assert policy_weight_sha256(left) != policy_weight_sha256(other)
    finally:
        for path in (left, right, other):
            path.unlink(missing_ok=True)


@pytest.mark.unit
def test_live_ledger_cannot_replace_the_kept_book(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.progress import save_awakening_progress

    art = artifacts_dir(tmp_path)
    kept_child = [_line(f"2026-04-{index + 1:02d}", 0.40, 40.0) for index in range(4)]
    kept_parent = [_line(f"2026-04-{index + 1:02d}", -0.10, -10.0) for index in range(4)]
    live_child = [_line(f"2026-05-{index + 1:02d}", -1.00, -100.0) for index in range(4)]
    live_parent = [_line(f"2026-05-{index + 1:02d}", 0.20, 20.0) for index in range(4)]
    _write_ledger(art / INCUMBENT_LEDGER_NAME, kept_child)
    _write_ledger(art / INCUMBENT_PARENT_LEDGER_NAME, kept_parent)
    _write_ledger(art / LEDGER_NAME, live_child)
    _write_ledger(art / "awakening_parent_holdout.jsonl", live_parent)
    save_awakening_progress(
        tmp_path,
        {
            "n_b": 500,
            "wr": 0.40,
            "birth_oos_wr": 0.30,
            "paired_ci_low": 0.01,
            "paired_delta": 0.02,
            "parent_replay_present": True,
            "child_weight_sha": "aa" * 32,
            "init_weight_sha": "bb" * 32,
        },
    )
    kept = paired_book_from_rows(
        [json.loads(line) for line in kept_child],
        [json.loads(line) for line in kept_parent],
    )
    live = paired_book_from_rows(
        [json.loads(line) for line in live_child],
        [json.loads(line) for line in live_parent],
    )
    assert float(kept["paired_delta"]) > 0.0
    assert float(live["paired_delta"]) < 0.0
    snap = snapshot_from_workspace(tmp_path)
    assert snap.paired_delta == pytest.approx(float(kept["paired_delta"]))
    assert snap.paired_ci_low == pytest.approx(float(kept["paired_ci_low"]))
    assert snap.paired_ci_low != pytest.approx(0.01)


@pytest.mark.unit
def test_missing_frozen_ledgers_do_not_read_the_live_book(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.progress import save_awakening_progress

    art = artifacts_dir(tmp_path)
    live_child = [_line(f"2026-05-{index + 1:02d}", -1.00, -100.0) for index in range(4)]
    live_parent = [_line(f"2026-05-{index + 1:02d}", 0.20, 20.0) for index in range(4)]
    _write_ledger(art / LEDGER_NAME, live_child)
    _write_ledger(art / "awakening_parent_holdout.jsonl", live_parent)
    save_awakening_progress(
        tmp_path,
        {
            "n_b": 500,
            "paired_ci_low": 0.024,
            "paired_delta": 0.148,
            "parent_replay_present": True,
            "child_median_win_r": 0.56,
            "parent_median_win_r": 0.88,
        },
    )
    live = paired_book_from_rows(
        [json.loads(line) for line in live_child],
        [json.loads(line) for line in live_parent],
    )
    assert float(live["paired_delta"]) < 0.0
    snap = snapshot_from_workspace(tmp_path)
    assert snap.paired_ci_low == pytest.approx(0.024)
    assert snap.paired_delta == pytest.approx(0.148)


@pytest.mark.unit
def test_parent_holdout_card_reads_the_replay_not_the_child(tmp_path: Path) -> None:
    from tests.maturity.test_awakening_live_shot import _write_birth_plant

    _write_birth_plant(tmp_path)
    art = artifacts_dir(tmp_path)
    frozen = art / "birth_exit_pi_star.zip"
    parent_rows = [
        _line("2026-06-01", -0.20, -20.0),
        _line("2026-06-01", -0.20, -20.0),
        _line("2026-06-02", 0.10, 10.0),
        _line("2026-06-02", -0.20, -20.0),
    ]
    _write_ledger(art / "awakening_parent_holdout.jsonl", parent_rows)
    _write_ledger(art / LEDGER_NAME, [_line("2026-06-01", 0.90, 90.0)])
    from lumina_core.maturity.awakening.keep_best import freeze_incumbent_ledgers

    assert freeze_incumbent_ledgers(tmp_path) is True
    card = parent_replay_card(tmp_path)
    assert card["parent_holdout_n_b"] == 4
    assert card["parent_holdout_wr"] == pytest.approx(0.25)
    assert card["parent_holdout_mean_r"] == pytest.approx(-0.125)
    assert card["parent_holdout_sha"] == policy_weight_sha256(frozen)
    assert card["parent_holdout_wr"] != pytest.approx(1.0)
