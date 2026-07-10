"""Tiered resume cache classification tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.remediation import ResumeCacheTier, classify_cache_resume_tier
from lumina_core.rl.trend_features import ENRICH_VERSION


def _split(train_count: int = 100) -> SimpleNamespace:
    train = [{"timestamp": f"2026-01-01T{i:02d}:00:00Z", "last": 5000.0 + i} for i in range(train_count)]
    holdout = [{"timestamp": "2026-02-01T00:00:00Z", "last": 5100.0}]
    return SimpleNamespace(train=train, holdout=holdout)


@pytest.mark.unit
def test_classify_t0_full_cache_hit() -> None:
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0}]
    decision = classify_cache_resume_tier(
        checkpoint_manifest={"train_hash": "abc123", "holdout_pct": 0.2},
        cache_manifest={
            "train_hash": "abc123",
            "holdout_pct": 0.2,
            "enrich_version": ENRICH_VERSION,
        },
        cached_ticks=ticks,
        cached_split=_split(),
        cached_train_hash="abc123",
        holdout_pct=0.2,
        enrich_version=ENRICH_VERSION,
    )
    assert decision.tier == ResumeCacheTier.T0
    assert decision.skip_load is True
    assert decision.skip_enrich is True


@pytest.mark.unit
def test_classify_t1_manifest_repair() -> None:
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0}]
    decision = classify_cache_resume_tier(
        checkpoint_manifest={"train_hash": "stale_hash"},
        cache_manifest={
            "train_hash": "abc123",
            "holdout_pct": 0.2,
            "enrich_version": ENRICH_VERSION,
        },
        cached_ticks=ticks,
        cached_split=_split(),
        cached_train_hash="abc123",
        holdout_pct=0.2,
        enrich_version=ENRICH_VERSION,
    )
    assert decision.tier == ResumeCacheTier.T1
    assert decision.repair_manifest is True


@pytest.mark.unit
def test_classify_t2_enrich_only() -> None:
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0}]
    decision = classify_cache_resume_tier(
        checkpoint_manifest={"train_hash": "abc123", "holdout_pct": 0.2},
        cache_manifest={
            "train_hash": "abc123",
            "holdout_pct": 0.2,
            "enrich_version": "trend_features_v0",
        },
        cached_ticks=ticks,
        cached_split=_split(),
        cached_train_hash="abc123",
        holdout_pct=0.2,
        enrich_version=ENRICH_VERSION,
    )
    assert decision.tier == ResumeCacheTier.T2
    assert decision.skip_load is True
    assert decision.skip_enrich is False


@pytest.mark.unit
def test_classify_t4_holdout_pct_changed() -> None:
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0}]
    decision = classify_cache_resume_tier(
        checkpoint_manifest={"train_hash": "abc123", "holdout_pct": 0.2},
        cache_manifest={"train_hash": "abc123", "holdout_pct": 0.2, "enrich_version": ENRICH_VERSION},
        cached_ticks=ticks,
        cached_split=_split(),
        cached_train_hash="abc123",
        holdout_pct=0.25,
        enrich_version=ENRICH_VERSION,
    )
    assert decision.tier == ResumeCacheTier.T4
    assert decision.skip_load is False
