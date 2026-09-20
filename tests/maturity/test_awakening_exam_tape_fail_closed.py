"""Fail-closed exam-tape paths: thin B, cache reject, labels, never train A."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from lumina_core.birth.synthetic_cloud_fixture import SOURCE_LABEL
from lumina_core.maturity.awakening.exam_tape import (
    AWAKENING_EXAM_SEED,
    CONTINUATION_CALENDAR_DAYS,
    EXAM_SCHEMA,
    MIN_EXAM_TICKS,
    _assert_after,
    _assert_no_train_leak,
    _calendar_days_for,
    _generate_continuation,
    _next_et,
    _persist_ext,
    _read_jsonl,
    exam_ext_path,
    exam_manifest_path,
    extend_exam_if_thin,
    load_awakening_exam_split,
)


def _tick(ts: str, last: float, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"timestamp": ts, "last": last, "close": last, "REAL": "no"}
    row.update(extra)
    return row


def _write_manifest(root: Path, *, schema: str, anchor: str, n: int = 1) -> None:
    exam_manifest_path(root).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": schema,
        "REAL": "no",
        "source": "synthetic_cloud_fixture",
        "seed": AWAKENING_EXAM_SEED,
        "n": int(n),
        "fingerprint": "deadbeef",
        "anchor_ts": anchor,
        "first_ts": "2026-03-01T14:05:00+00:00",
        "last_ts": "2026-03-01T14:10:00+00:00",
        "birth_cache_untouched": True,
    }
    exam_manifest_path(root).write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_ext_rows(root: Path, rows: list[dict[str, Any]]) -> None:
    path = exam_ext_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


@pytest.mark.unit
def test_empty_holdout_b_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="awakening_exam_holdout_b_empty"):
        extend_exam_if_thin(
            tmp_path,
            train=[_tick("2026-01-01T00:00:00+00:00", 21000.0)],
            holdout_b=[],
            min_ticks=3,
        )


@pytest.mark.unit
def test_too_thin_after_continuation_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _gen(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        return [_tick("2026-03-01T14:05:00+00:00", 21110.0)]

    monkeypatch.setattr("lumina_core.maturity.awakening.exam_tape._generate_continuation", _gen)
    with pytest.raises(RuntimeError, match="awakening_exam_too_thin"):
        extend_exam_if_thin(
            tmp_path,
            train=[_tick("2026-01-01T00:00:00+00:00", 21000.0)],
            holdout_b=[_tick("2026-03-01T14:00:00+00:00", 21100.0)],
            min_ticks=10,
        )


@pytest.mark.unit
def test_empty_train_or_other_skips_leak_check() -> None:
    holdout = [_tick("2026-03-01T14:00:00+00:00", 21100.0)]
    train = [_tick("2026-01-01T00:00:00+00:00", 21000.0)]
    _assert_no_train_leak([], holdout)
    _assert_no_train_leak(train, [])


@pytest.mark.unit
def test_assert_after_empty_continuation_fail_closed() -> None:
    with pytest.raises(RuntimeError, match="awakening_exam_continuation_empty"):
        _assert_after([_tick("2026-03-01T14:00:00+00:00", 21100.0)], [])


@pytest.mark.unit
def test_next_et_naive_and_zulu() -> None:
    naive = _next_et("2026-08-28T20:59:00")
    zulu = _next_et("2026-08-28T20:59:00Z")
    aware = _next_et("2026-08-28T20:59:00+00:00")
    assert naive.tzinfo is not None
    assert naive == zulu == aware
    et = ZoneInfo("America/New_York")
    expected = datetime(2026, 8, 28, 20, 59, tzinfo=timezone.utc).astimezone(et)
    expected = expected.replace(microsecond=0)
    assert naive == expected + timedelta(minutes=1)


@pytest.mark.unit
def test_calendar_days_never_below_continuation_floor() -> None:
    assert _calendar_days_for(149_000, MIN_EXAM_TICKS) == CONTINUATION_CALENDAR_DAYS
    needed = MIN_EXAM_TICKS - 43_170
    assert _calendar_days_for(43_170, MIN_EXAM_TICKS) == max(CONTINUATION_CALENDAR_DAYS, int(needed / 1800) + 7)


@pytest.mark.unit
def test_read_jsonl_fail_closed_on_garbage_and_empty(tmp_path: Path) -> None:
    missing = tmp_path / "nope.jsonl"
    assert _read_jsonl(missing) == []
    blank = tmp_path / "blank.jsonl"
    blank.write_text("\n\n", encoding="utf-8")
    assert _read_jsonl(blank) == []
    garbage = tmp_path / "garbage.jsonl"
    garbage.write_text("{not-json\n", encoding="utf-8")
    assert _read_jsonl(garbage) == []
    mixed = tmp_path / "mixed.jsonl"
    mixed.write_text(
        "\n".join(['{"timestamp":"2026-03-01T14:05:00+00:00"}', "[1,2]", "3", ""]) + "\n",
        encoding="utf-8",
    )
    assert _read_jsonl(mixed) == [{"timestamp": "2026-03-01T14:05:00+00:00"}]
    as_dir = tmp_path / "dirjsonl"
    as_dir.mkdir()
    assert _read_jsonl(as_dir) == []


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutate",
    [
        "missing_files",
        "bad_json",
        "wrong_schema",
        "wrong_anchor",
        "empty_rows",
        "too_thin_cache",
        "not_after_b",
    ],
)
def test_invalid_cache_rebuilds_not_silently_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate: str
) -> None:
    holdout = [_tick("2026-03-01T14:00:00+00:00", 21100.0)]
    train = [_tick("2026-01-01T00:00:00+00:00", 21000.0)]
    rebuilt = [_tick("2026-03-01T14:05:00+00:00", 21110.0), _tick("2026-03-01T14:10:00+00:00", 21120.0)]
    gens: list[int] = []

    def _gen(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        gens.append(1)
        return list(rebuilt)

    monkeypatch.setattr("lumina_core.maturity.awakening.exam_tape._generate_continuation", _gen)
    if mutate != "missing_files":
        _write_manifest(tmp_path, schema=EXAM_SCHEMA, anchor="2026-03-01T14:00:00+00:00", n=2)
        _write_ext_rows(tmp_path, rebuilt)
    if mutate == "bad_json":
        exam_manifest_path(tmp_path).write_text("{nope", encoding="utf-8")
    elif mutate == "wrong_schema":
        _write_manifest(tmp_path, schema="awakening_exam_v0", anchor="2026-03-01T14:00:00+00:00")
    elif mutate == "wrong_anchor":
        _write_manifest(tmp_path, schema=EXAM_SCHEMA, anchor="2026-02-01T00:00:00+00:00")
    elif mutate == "empty_rows":
        _write_ext_rows(tmp_path, [])
    elif mutate == "too_thin_cache":
        _write_ext_rows(tmp_path, [_tick("2026-03-01T14:05:00+00:00", 21110.0)])
    elif mutate == "not_after_b":
        _write_ext_rows(
            tmp_path,
            [
                _tick("2026-03-01T13:00:00+00:00", 21090.0),
                _tick("2026-03-01T13:05:00+00:00", 21091.0),
            ],
        )

    min_ticks = 3
    exam, meta = extend_exam_if_thin(tmp_path, train=train, holdout_b=holdout, min_ticks=min_ticks)
    assert gens == [1]
    assert meta["exam_extended"] is True
    assert [row["timestamp"] for row in exam][-2:] == [
        rebuilt[0]["timestamp"],
        rebuilt[1]["timestamp"],
    ]


@pytest.mark.unit
def test_generate_continuation_labels_and_never_writes_birth_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    birth_ticks = state / "lumina_birth_ticks_cache.jsonl"
    birth_split = state / "lumina_birth_split_cache.json"
    birth_ticks.write_text('{"keep":true}\n', encoding="utf-8")
    birth_split.write_text('{"keep":true}\n', encoding="utf-8")
    before_t, before_s = birth_ticks.read_bytes(), birth_split.read_bytes()
    specs: list[Any] = []
    enrich_roots: list[Any] = []

    def _gen(spec: Any) -> list[dict[str, Any]]:
        specs.append(spec)
        return [
            {
                "timestamp": "2026-03-01T14:05:00+00:00",
                "last": 21110.0,
                "close": 21110.0,
                "high": 21111.0,
                "low": 21109.0,
            },
            {
                "timestamp": "2026-03-01T14:10:00+00:00",
                "last": 21120.0,
                "close": 21120.0,
                "high": 21121.0,
                "low": 21119.0,
            },
        ]

    def _enrich(
        ticks: list[dict[str, Any]],
        *,
        workspace_root: Path | str | None = None,
        raw_ticks_hash: str | None = None,
        **_k: Any,
    ) -> list[dict[str, Any]]:
        enrich_roots.append(workspace_root)
        assert raw_ticks_hash
        # Strip labels so exam_tape must re-stamp after enrich.
        return [{"timestamp": str(t["timestamp"]), "last": float(t["last"]), "close": float(t["close"])} for t in ticks]

    monkeypatch.setattr("lumina_core.maturity.awakening.exam_tape.generate_cloud_fixture_ticks", _gen)
    monkeypatch.setattr("lumina_core.maturity.awakening.exam_tape.enrich_ticks_for_sim", _enrich)
    holdout = [_tick("2026-03-01T14:00:00+00:00", 21100.0)]
    exam, meta = extend_exam_if_thin(
        tmp_path,
        train=[_tick("2026-01-01T00:00:00+00:00", 21000.0)],
        holdout_b=holdout,
        min_ticks=3,
    )
    assert specs
    spec = specs[0]
    assert spec.seed == AWAKENING_EXAM_SEED
    assert spec.start_price == pytest.approx(21100.0)
    assert spec.start_et == _next_et("2026-03-01T14:00:00+00:00")
    assert spec.calendar_days == _calendar_days_for(1, 3)
    assert enrich_roots == [None]
    assert meta["exam_extended"] is True
    assert meta["source"] == SOURCE_LABEL
    assert meta["REAL"] == "no"
    for row in exam[1:]:
        assert row["source"] == SOURCE_LABEL
        assert row["awakening_exam"] is True
        assert row["REAL"] == "no"
    assert birth_ticks.read_bytes() == before_t
    assert birth_split.read_bytes() == before_s
    man = json.loads(exam_manifest_path(tmp_path).read_text(encoding="utf-8"))
    assert man["schema"] == EXAM_SCHEMA
    assert man["birth_cache_untouched"] is True
    assert man["anchor_ts"] == "2026-03-01T14:00:00+00:00"
    assert man["seed"] == AWAKENING_EXAM_SEED


@pytest.mark.unit
def test_generate_continuation_default_price_when_last_nonpositive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[float] = []

    def _gen(spec: Any) -> list[dict[str, Any]]:
        seen.append(float(spec.start_price))
        return [_tick("2026-03-01T14:05:00+00:00", 21150.0)]

    def _enrich(ticks: list[dict[str, Any]], **_k: Any) -> list[dict[str, Any]]:
        return [dict(t) for t in ticks]

    monkeypatch.setattr("lumina_core.maturity.awakening.exam_tape.generate_cloud_fixture_ticks", _gen)
    monkeypatch.setattr("lumina_core.maturity.awakening.exam_tape.enrich_ticks_for_sim", _enrich)
    out = _generate_continuation([_tick("2026-03-01T14:00:00+00:00", 0.0)], min_ticks=3)
    assert seen == [21150.0]
    assert out[0]["awakening_exam"] is True
    assert out[0]["source"] == SOURCE_LABEL


@pytest.mark.unit
def test_persist_ext_empty_timestamps(tmp_path: Path) -> None:
    _persist_ext(tmp_path, [], holdout_b=[_tick("2026-03-01T14:00:00+00:00", 21100.0)])
    man = json.loads(exam_manifest_path(tmp_path).read_text(encoding="utf-8"))
    assert man["first_ts"] == ""
    assert man["last_ts"] == ""
    assert man["n"] == 0


@pytest.mark.unit
def test_load_awakening_exam_split_wraps_live_split(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    train = [_tick("2026-01-01T00:00:00+00:00", 21000.0)]
    holdout = [_tick(f"2026-03-01T14:0{i}:00+00:00", 21100.0 + i) for i in range(5)]

    def _live(_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        return train, holdout, {"holdout_pct": 0.2, "from_live": True, "train_n": 1, "holdout_n": 5}

    monkeypatch.setattr(
        "lumina_core.maturity.phase_runners.awakening_shot.load_live_split",
        _live,
    )
    got_train, exam, meta = load_awakening_exam_split(tmp_path, min_ticks=5)
    assert got_train == train
    assert exam == holdout
    assert meta["from_live"] is True
    assert meta["exam_n"] == 5
    assert meta["holdout_b_n"] == 5
    assert meta["exam_extended"] is False
    assert meta["exam_kind"] == "holdout_B"
    assert meta["REAL"] == "no"
