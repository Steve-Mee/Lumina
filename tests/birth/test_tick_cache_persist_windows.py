"""Tick-cache persist: Windows replace, depth regression, split-brain heal."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lumina_core.birth.purged_split import PurgedSplit
from lumina_core.birth.tick_cache_guard import (
    TickCacheDepthRegressionError,
    heal_tick_cache_coherence,
)
from lumina_core.birth.tick_cache_persist import (
    certified_tick_cache_present,
    load_cache_manifest,
    load_split_cache,
    load_ticks_cache,
    save_birth_data_cache,
    split_cache_path,
    ticks_cache_path,
)


def _tick(ts: str, last: float, bar: int) -> dict[str, object]:
    return {"timestamp": ts, "last": last, "bar_index": bar, "source": "real"}


def _write_certified_stub(
    workspace: Path,
    *,
    n: int = 1000,
    requested: int = 90,
    actual: int = 89,
    instruments: list[str] | None = None,
) -> None:
    state = workspace / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_birth_ticks_cache.jsonl").write_text(
        "\n".join("{}" for _ in range(n)) + "\n",
        encoding="utf-8",
    )
    (state / "lumina_birth_split_cache.json").write_text("{}", encoding="utf-8")
    (state / "lumina_birth_cache_manifest.json").write_text(
        json.dumps(
            {
                "train_hash": "abc",
                "requested_days": requested,
                "actual_calendar_days": actual,
                "tick_count": n,
                "instruments": instruments or ["MES SEP26"],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.unit
def test_certified_false_when_jsonl_row_count_mismatches_manifest(tmp_path: Path) -> None:
    _write_certified_stub(tmp_path, n=1000)
    ticks_cache_path(tmp_path).write_text("{}\n{}\n", encoding="utf-8")
    assert certified_tick_cache_present(tmp_path) is False


@pytest.mark.unit
def test_certified_false_when_legacy_tmp_sibling_exists(tmp_path: Path) -> None:
    _write_certified_stub(tmp_path, n=1000)
    (tmp_path / "state" / "lumina_birth_split_cache.json.tmp").write_text("partial", encoding="utf-8")
    assert certified_tick_cache_present(tmp_path) is False


@pytest.mark.unit
def test_save_refuses_shallower_certified_overwrite(tmp_path: Path) -> None:
    _write_certified_stub(tmp_path, n=1000, requested=365, actual=366)
    ticks = [_tick("2026-06-12T00:00:00", 1.0, 0), _tick("2026-06-13T00:00:00", 2.0, 1)]
    split = PurgedSplit(train=[ticks[0]], holdout=[ticks[1]], holdout_days=1, train_days=1)
    with pytest.raises(TickCacheDepthRegressionError, match="depth regression"):
        save_birth_data_cache(
            tmp_path,
            ticks=ticks,
            split=split,
            holdout_pct=0.2,
            raw_ticks_hash="raw",
            train_hash="train",
            requested_days=90,
            actual_calendar_days=77,
            instruments=["MES SEP26"],
        )
    assert jsonl_still_stub(tmp_path, 1000)


def jsonl_still_stub(workspace: Path, n: int) -> bool:
    return ticks_cache_path(workspace).read_text(encoding="utf-8").count("\n") == n


@pytest.mark.unit
def test_save_allows_same_depth_rewrite(tmp_path: Path) -> None:
    ticks = [_tick(f"2026-01-01T00:00:{i:02d}", 5000.0 + i, i) for i in range(1000)]
    split = PurgedSplit(train=ticks[:800], holdout=ticks[800:], holdout_days=1, train_days=1)
    save_birth_data_cache(
        tmp_path,
        ticks=ticks,
        split=split,
        holdout_pct=0.2,
        raw_ticks_hash="raw",
        train_hash="train",
        requested_days=90,
        actual_calendar_days=89,
        instruments=["MES SEP26"],
    )
    assert certified_tick_cache_present(tmp_path)
    save_birth_data_cache(
        tmp_path,
        ticks=ticks,
        split=split,
        holdout_pct=0.2,
        raw_ticks_hash="raw",
        train_hash="train",
        requested_days=90,
        actual_calendar_days=89,
        instruments=["MES SEP26"],
    )
    loaded = load_split_cache(tmp_path, holdout_pct=0.2)
    assert loaded is not None
    assert len(loaded.train) == 800


@pytest.mark.unit
def test_split_replace_failure_does_not_commit_ticks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    ticks_cache_path(tmp_path).write_text("OLD_TICK\n", encoding="utf-8")
    real_replace = os.replace

    def _fail_split(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if Path(dst).name == "lumina_birth_split_cache.json":
            err = PermissionError(13, "Access is denied")
            setattr(err, "winerror", 5)
            raise err
        real_replace(src, dst)

    monkeypatch.setattr("lumina_core.io.atomic_fs.os.replace", _fail_split)
    monkeypatch.setattr("lumina_core.io.atomic_fs.time.sleep", lambda _s: None)
    ticks = [_tick("2026-01-01T00:00:00", 1.0, 0), _tick("2026-01-02T00:00:00", 2.0, 1)]
    split = PurgedSplit(train=[ticks[0]], holdout=[ticks[1]], holdout_days=1, train_days=1)
    with pytest.raises(PermissionError):
        save_birth_data_cache(
            tmp_path,
            ticks=ticks,
            split=split,
            holdout_pct=0.2,
            raw_ticks_hash="raw",
            train_hash="train",
            requested_days=2,
            actual_calendar_days=2,
        )
    assert ticks_cache_path(tmp_path).read_text(encoding="utf-8") == "OLD_TICK\n"
    assert not (tmp_path / "state" / "lumina_birth_cache_manifest.json").exists()


@pytest.mark.unit
def test_heal_rebuilds_jsonl_from_v1_split_and_discards_shallower_tmp(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    deep = [_tick(f"2025-09-10T{i:06d}", float(i), i) for i in range(1000)]
    split_payload = {
        "holdout_pct": 0.2,
        "train": deep[:800],
        "holdout": deep[800:],
        "holdout_days": 1,
        "train_days": 2,
    }
    split_cache_path(tmp_path).write_text(json.dumps(split_payload), encoding="utf-8")
    (state / "lumina_birth_split_cache.json.tmp").write_text(
        json.dumps(
            {
                "holdout_pct": 0.2,
                "train": [deep[-1]],
                "holdout": [],
                "holdout_days": 0,
                "train_days": 1,
            }
        ),
        encoding="utf-8",
    )
    ticks_cache_path(tmp_path).write_text(json.dumps(deep[-1]) + "\n", encoding="utf-8")
    (state / "lumina_birth_cache_manifest.json").write_text(
        json.dumps(
            {
                "train_hash": "abc",
                "raw_ticks_hash": "raw",
                "requested_days": 365,
                "actual_calendar_days": 366,
                "tick_count": 1000,
                "holdout_pct": 0.2,
                "train_tick_count": 800,
                "holdout_tick_count": 200,
                "instruments": ["MES SEP26"],
                "source": "real",
                "real_data_pct": 100.0,
            }
        ),
        encoding="utf-8",
    )
    assert heal_tick_cache_coherence(tmp_path) == "healed"
    assert not (state / "lumina_birth_split_cache.json.tmp").exists()
    recovered = load_ticks_cache(tmp_path)
    assert len(recovered) == 1000
    assert recovered[0]["last"] == 0.0
    assert recovered[-1]["last"] == 999.0
    manifest = load_cache_manifest(tmp_path)
    assert manifest is not None
    assert int(manifest["tick_count"]) == 1000
    assert manifest["tick_count_healed_from_split"] is True
    assert certified_tick_cache_present(tmp_path) is True


@pytest.mark.unit
def test_save_skips_ticks_rewrite_when_hash_and_count_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticks = [_tick("2026-01-01T00:00:00", 1.0, 0), _tick("2026-01-02T00:00:00", 2.0, 1)]
    split = PurgedSplit(train=[ticks[0]], holdout=[ticks[1]], holdout_days=1, train_days=1)
    save_birth_data_cache(
        tmp_path,
        ticks=ticks,
        split=split,
        holdout_pct=0.2,
        raw_ticks_hash="raw",
        train_hash="train",
        requested_days=2,
        actual_calendar_days=2,
    )

    def _boom(*_a: object, **_k: object) -> str:
        raise AssertionError("matching jsonl must not be rewritten")

    monkeypatch.setattr("lumina_core.birth.tick_cache_persist.ticks_jsonl", _boom)
    save_birth_data_cache(
        tmp_path,
        ticks=ticks,
        split=split,
        holdout_pct=0.2,
        raw_ticks_hash="raw",
        train_hash="train",
        requested_days=2,
        actual_calendar_days=2,
    )
    assert load_ticks_cache(tmp_path)[0]["last"] == 1.0


@pytest.mark.unit
def test_certified_cache_loaded_without_reuse_flag(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from lumina_core.birth.data_pipeline_resume import BirthDataPipelineResumeMixin
    from lumina_core.birth.data_pipeline_types import train_hash
    from lumina_core.birth.tick_cache_persist import compute_ticks_fingerprint

    ticks = [_tick(f"2026-01-01T{i:06d}", float(i), i) for i in range(1000)]
    split = PurgedSplit(train=ticks[:800], holdout=ticks[800:], holdout_days=1, train_days=1)
    save_birth_data_cache(
        tmp_path,
        ticks=ticks,
        split=split,
        holdout_pct=0.2,
        raw_ticks_hash=compute_ticks_fingerprint(ticks),
        train_hash=train_hash(split.train),
        requested_days=90,
        actual_calendar_days=89,
        instruments=["MES SEP26"],
    )
    assert certified_tick_cache_present(tmp_path) is True

    class _Host:
        workspace_root = tmp_path
        _reuse_data_manifest = False
        _data_manifest: dict = {}
        market_data_service = None
        runtime = None
        cumulative_trades = 0
        ppo_steps = 0
        birth_start_time = 1.0

    class _Pipe(BirthDataPipelineResumeMixin):
        def __init__(self) -> None:
            self._host = _Host()

    pipe = _Pipe()
    result = pipe._resolve_resume_cache(
        cfg=SimpleNamespace(holdout_pct=0.2, trade_budget_cap=25000),
        resume=False,
        training_mode="certified",
    )
    assert result["resume_skip_load"] is True
    assert len(result["ticks"]) == 1000
    assert result["split"] is not None
    assert pipe._host._reuse_data_manifest is True
    assert result["resume_cache_decision"] is not None
