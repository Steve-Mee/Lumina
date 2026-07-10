"""Birth cache manifest persistence tests."""

from __future__ import annotations

import json

import pytest

from lumina_core.birth.purged_split import PurgedSplit
from lumina_core.birth.tick_cache_persist import (
    CACHE_SCHEMA_VERSION,
    load_cache_manifest,
    save_birth_data_cache,
    ticks_cache_path,
)


@pytest.mark.unit
def test_save_birth_data_cache_writes_manifest(tmp_path) -> None:
    ticks = [
        {"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0, "regime": "NEUTRAL"},
        {"timestamp": "2026-01-02T00:00:00Z", "last": 5001.0, "regime": "TREND_UP"},
    ]
    split = PurgedSplit(train=[ticks[0]], holdout=[ticks[1]], holdout_days=1, train_days=1)
    paths = save_birth_data_cache(
        tmp_path,
        ticks=ticks,
        split=split,
        holdout_pct=0.2,
        raw_ticks_hash="raw123",
        train_hash="train123",
    )
    assert paths["cache_manifest_path"]
    manifest = load_cache_manifest(tmp_path)
    assert manifest is not None
    assert manifest["cache_schema_version"] == CACHE_SCHEMA_VERSION
    assert manifest["raw_ticks_hash"] == "raw123"
    assert manifest["train_hash"] == "train123"
    assert ticks_cache_path(tmp_path).is_file()
    payload = json.loads(ticks_cache_path(tmp_path).read_text(encoding="utf-8").splitlines()[0])
    assert payload["last"] == 5000.0
