"""Enrichment cache tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.enrichment_cache import (
    load_enrichment_cache,
    save_enrichment_cache,
    try_apply_enrichment_cache,
)
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.trend_features import ENRICH_VERSION


def _sample_ticks(n: int = 200) -> list[dict]:
    return [
        {
            "last": 5000.0 + i * 0.05,
            "close": 5000.0 + i * 0.05,
            "high": 5000.0 + i * 0.05 + 0.5,
            "low": 5000.0 + i * 0.05 - 0.5,
            "volume": 100,
            "source": "real",
            "bid": 5000.0 + i * 0.05 - 0.125,
            "ask": 5000.0 + i * 0.05 + 0.125,
        }
        for i in range(n)
    ]


@pytest.mark.unit
def test_enrichment_cache_roundtrip(tmp_path) -> None:
    ticks = enrich_ticks_for_sim(_sample_ticks(200), workspace_root=tmp_path)
    raw_hash = "abc123"
    path = save_enrichment_cache(tmp_path, ticks=ticks, raw_ticks_hash=raw_hash)
    assert path
    cached = load_enrichment_cache(
        tmp_path,
        raw_ticks_hash=raw_hash,
        tick_count=len(ticks),
        enrich_version=ENRICH_VERSION,
    )
    assert cached is not None
    assert float(cached["trend_regime_strength"][100]) == pytest.approx(
        float(ticks[100]["trend_regime_strength"]),
        abs=1e-6,
    )


@pytest.mark.unit
def test_try_apply_enrichment_cache_skips_compute(tmp_path, monkeypatch) -> None:
    ticks = enrich_ticks_for_sim(_sample_ticks(120), workspace_root=tmp_path)
    raw_hash = "def456"
    save_enrichment_cache(tmp_path, ticks=ticks, raw_ticks_hash=raw_hash)

    calls = {"n": 0}

    def _fail_batch(*_args, **_kwargs):
        calls["n"] += 1
        raise AssertionError("batch compute should not run on cache hit")

    monkeypatch.setattr(
        "lumina_core.birth.tick_enricher.compute_trend_features_sliding_batch",
        _fail_batch,
    )
    fresh = _sample_ticks(120)
    assert try_apply_enrichment_cache(
        tmp_path,
        fresh,
        raw_ticks_hash=raw_hash,
        enrich_version=ENRICH_VERSION,
    )
    assert calls["n"] == 0
    assert "trend_regime_strength" in fresh[100]
