"""Awakening exam tape: extend thin B, never train A, never touch Birth cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumina_core.maturity.awakening.exam_tape import (
    exam_ext_path,
    exam_manifest_path,
    extend_exam_if_thin,
)
from lumina_core.maturity.awakening.progress import load_awakening_progress
from lumina_core.maturity.awakening.select import persist_cycle


def _tick(ts: str, last: float, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"timestamp": ts, "last": last, "close": last, "REAL": "no"}
    row.update(extra)
    return row


def _birth_cache(root: Path) -> tuple[Path, Path]:
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    ticks = state / "lumina_birth_ticks_cache.jsonl"
    split = state / "lumina_birth_split_cache.json"
    ticks.write_text('{"timestamp":"2026-01-01T00:00:00+00:00"}\n', encoding="utf-8")
    split.write_text('{"holdout_pct":0.2}\n', encoding="utf-8")
    return ticks, split


@pytest.mark.unit
def test_fat_b_is_the_exam_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[int] = []

    def _boom(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        called.append(1)
        raise AssertionError("fat B must not generate continuation")

    monkeypatch.setattr("lumina_core.maturity.awakening.exam_tape._generate_continuation", _boom)
    holdout = [_tick(f"2026-03-01T14:0{i}:00+00:00", 21100.0 + i) for i in range(5)]
    exam, meta = extend_exam_if_thin(
        tmp_path,
        train=[_tick("2026-01-01T00:00:00+00:00", 21000.0)],
        holdout_b=holdout,
        min_ticks=5,
    )
    assert meta["exam_extended"] is False
    assert meta["exam_kind"] == "holdout_B"
    assert exam == holdout
    assert called == []
    assert not exam_ext_path(tmp_path).is_file()


@pytest.mark.unit
def test_thin_b_extends_after_b_no_train_leak(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ticks, split = _birth_cache(tmp_path)
    before_t, before_s = ticks.read_bytes(), split.read_bytes()
    train = [_tick("2026-01-01T00:00:00+00:00", 21000.0, id="train-a")]
    holdout = [_tick("2026-03-01T14:00:00+00:00", 21100.0, id="b-a")]
    ext = [
        _tick("2026-03-01T14:05:00+00:00", 21110.0, id="ext-a"),
        _tick("2026-03-01T14:10:00+00:00", 21120.0, id="ext-b"),
    ]
    gens: list[int] = []

    def _gen(holdout_b: list[dict[str, Any]], *, min_ticks: int) -> list[dict[str, Any]]:
        gens.append(min_ticks)
        assert holdout_b[-1]["id"] == "b-a"
        return list(ext)

    monkeypatch.setattr("lumina_core.maturity.awakening.exam_tape._generate_continuation", _gen)
    exam, meta = extend_exam_if_thin(tmp_path, train=train, holdout_b=holdout, min_ticks=3)
    assert meta["exam_extended"] is True
    assert meta["exam_kind"] == "holdout_B_plus_continuation"
    assert [row["id"] for row in exam] == ["b-a", "ext-a", "ext-b"]
    assert exam[0]["timestamp"] > train[-1]["timestamp"]
    assert exam[-1]["timestamp"] > holdout[-1]["timestamp"]
    assert ticks.read_bytes() == before_t
    assert split.read_bytes() == before_s
    assert exam_manifest_path(tmp_path).is_file()
    exam2, _ = extend_exam_if_thin(tmp_path, train=train, holdout_b=holdout, min_ticks=3)
    assert [row["id"] for row in exam2] == ["b-a", "ext-a", "ext-b"]
    assert gens == [3]


@pytest.mark.unit
def test_train_leak_fail_closed(tmp_path: Path) -> None:
    train = [_tick("2026-06-01T00:00:00+00:00", 21000.0)]
    holdout = [_tick("2026-05-01T00:00:00+00:00", 21100.0)]
    with pytest.raises(RuntimeError, match="awakening_exam_train_leak"):
        extend_exam_if_thin(tmp_path, train=train, holdout_b=holdout, min_ticks=1)


@pytest.mark.unit
def test_continuation_not_after_b_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _gen(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        return [_tick("2026-01-01T00:00:00+00:00", 21100.0)]

    monkeypatch.setattr("lumina_core.maturity.awakening.exam_tape._generate_continuation", _gen)
    with pytest.raises(RuntimeError, match="awakening_exam_not_after_B"):
        extend_exam_if_thin(
            tmp_path,
            train=[_tick("2025-01-01T00:00:00+00:00", 20000.0)],
            holdout_b=[_tick("2026-03-01T14:00:00+00:00", 21100.0)],
            min_ticks=3,
        )


@pytest.mark.unit
def test_invalid_anchor_ts_fail_closed() -> None:
    from lumina_core.maturity.awakening.exam_tape import _next_et

    with pytest.raises(RuntimeError, match="awakening_exam_anchor_ts_invalid"):
        _next_et("not-a-timestamp")
    with pytest.raises(RuntimeError, match="awakening_exam_anchor_ts_missing"):
        _next_et("")


@pytest.mark.unit
def test_persist_cycle_zero_uses_same_tape_parent(tmp_path: Path) -> None:
    persist_cycle(
        tmp_path,
        {
            "policy_trades": 600,
            "policy_only": True,
            "polish_oos_winrate": 0.41,
            "birth_exit_winrate": 0.33,
            "mean_r": -0.12,
            "split": {"exam_kind": "holdout_B_plus_continuation", "exam_n": 180000},
        },
        cycle=0,
    )
    prog = load_awakening_progress(tmp_path)
    assert prog.get("parent_same_tape") is True
    assert float(prog.get("birth_oos_wr") or 0) == pytest.approx(0.41)
    assert float(prog.get("fitness_oos_wr") or 0) == pytest.approx(0.33)
    assert float(prog.get("birth_mean_r") or 0) == pytest.approx(-0.12)
    persist_cycle(
        tmp_path,
        {
            "policy_trades": 620,
            "policy_only": True,
            "polish_oos_winrate": 0.44,
            "birth_exit_winrate": 0.33,
            "mean_r": -0.10,
        },
        cycle=1,
    )
    later = load_awakening_progress(tmp_path)
    assert later.get("parent_same_tape") is True
    assert float(later.get("birth_oos_wr") or 0) == pytest.approx(0.41)
    assert float(later.get("wr") or 0) == pytest.approx(0.44)
    assert float(later.get("birth_mean_r") or 0) == pytest.approx(-0.12)
