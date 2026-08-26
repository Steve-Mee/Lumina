"""Tiered resume cache classification tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.remediation import ResumeCacheTier, classify_cache_resume_tier
from lumina_core.rl.trend_features import ENRICH_VERSION

_REQ = {
    "requested_days": 90,
    "actual_calendar_days": 90,
    "instruments": ["MES SEP26"],
}


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
            **_REQ,
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
            **_REQ,
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
            **_REQ,
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
        cache_manifest={
            "train_hash": "abc123",
            "holdout_pct": 0.2,
            "enrich_version": ENRICH_VERSION,
            **_REQ,
        },
        cached_ticks=ticks,
        cached_split=_split(),
        cached_train_hash="abc123",
        holdout_pct=0.25,
        enrich_version=ENRICH_VERSION,
    )
    assert decision.tier == ResumeCacheTier.T4
    assert decision.skip_load is False


@pytest.mark.unit
def test_classify_t4_missing_or_thin_requested_days() -> None:
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0}]
    missing = classify_cache_resume_tier(
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
    assert missing.tier == ResumeCacheTier.T4
    assert missing.reason == "requested_days_mismatch"
    thin = classify_cache_resume_tier(
        checkpoint_manifest={"train_hash": "abc123", "holdout_pct": 0.2},
        cache_manifest={
            "train_hash": "abc123",
            "holdout_pct": 0.2,
            "enrich_version": ENRICH_VERSION,
            "requested_days": 56,
        },
        cached_ticks=ticks,
        cached_split=_split(),
        cached_train_hash="abc123",
        holdout_pct=0.2,
        enrich_version=ENRICH_VERSION,
    )
    assert thin.tier == ResumeCacheTier.T4
    assert thin.reason == "requested_days_mismatch"


@pytest.mark.unit
def test_classify_t4_thin_actual_calendar_days() -> None:
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0}]
    decision = classify_cache_resume_tier(
        checkpoint_manifest={"train_hash": "abc123", "holdout_pct": 0.2},
        cache_manifest={
            "train_hash": "abc123",
            "holdout_pct": 0.2,
            "enrich_version": ENRICH_VERSION,
            "requested_days": 90,
            "actual_calendar_days": 57,
            "instruments": ["MES SEP26"],
        },
        cached_ticks=ticks,
        cached_split=_split(),
        cached_train_hash="abc123",
        holdout_pct=0.2,
        enrich_version=ENRICH_VERSION,
        current_instrument="MES SEP26",
    )
    assert decision.tier == ResumeCacheTier.T4
    assert decision.reason == "history_depth_thin"


@pytest.mark.unit
def test_classify_t4_instrument_chain_mismatch() -> None:
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0}]
    kwargs = dict(
        checkpoint_manifest={"train_hash": "abc123", "holdout_pct": 0.2},
        cached_ticks=ticks,
        cached_split=_split(),
        cached_train_hash="abc123",
        holdout_pct=0.2,
        enrich_version=ENRICH_VERSION,
    )
    missing_chain = classify_cache_resume_tier(
        cache_manifest={
            "train_hash": "abc123",
            "holdout_pct": 0.2,
            "enrich_version": ENRICH_VERSION,
            "requested_days": 90,
            "actual_calendar_days": 90,
        },
        current_instrument="MES SEP26",
        **kwargs,
    )
    assert missing_chain.tier == ResumeCacheTier.T4
    assert missing_chain.reason == "instrument_chain_mismatch"
    rolled = classify_cache_resume_tier(
        cache_manifest={
            "train_hash": "abc123",
            "holdout_pct": 0.2,
            "enrich_version": ENRICH_VERSION,
            "requested_days": 90,
            "actual_calendar_days": 90,
            "instruments": ["MES JUN26", "MES MAR26"],
        },
        current_instrument="MES SEP26",
        **kwargs,
    )
    assert rolled.tier == ResumeCacheTier.T4
    assert rolled.reason == "instrument_chain_mismatch"


@pytest.mark.unit
def test_classify_t0_when_front_month_in_stitched_chain() -> None:
    ticks = [{"timestamp": "2026-01-01T00:00:00Z", "last": 5000.0}]
    decision = classify_cache_resume_tier(
        checkpoint_manifest={"train_hash": "abc123", "holdout_pct": 0.2},
        cache_manifest={
            "train_hash": "abc123",
            "holdout_pct": 0.2,
            "enrich_version": ENRICH_VERSION,
            "requested_days": 90,
            "actual_calendar_days": 90,
            "instruments": ["MES SEP26", "MES JUN26"],
        },
        cached_ticks=ticks,
        cached_split=_split(),
        cached_train_hash="abc123",
        holdout_pct=0.2,
        enrich_version=ENRICH_VERSION,
        current_instrument="MES SEP26",
    )
    assert decision.tier == ResumeCacheTier.T0
    assert decision.skip_load is True
