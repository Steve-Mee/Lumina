"""Certified-schema synthetic NQ fixture for headless Birth cloud runs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.synthetic_cloud_fixture import (
    SOURCE_LABEL,
    CloudFixtureSpec,
    FixtureMarketDataService,
    generate_cloud_fixture_ticks,
    persist_cloud_fixture,
)
from lumina_core.birth.tick_cache_persist import (
    certified_tick_cache_present,
    load_cache_manifest,
    load_ticks_cache,
)
from lumina_core.birth.preflight import assess_split_preflight, regime_labels
from lumina_core.birth.birth_certificate import BirthCertificateThresholds


def _compact_spec() -> CloudFixtureSpec:
    return CloudFixtureSpec(
        calendar_days=FOUNDATION_HISTORY_START_DAYS,
        rth_bar_seconds=60,
        eth_bar_seconds=180,
        seed=7,
    )


@pytest.mark.unit
def test_fixture_ticks_are_sane_nq_microstructure() -> None:
    ticks = generate_cloud_fixture_ticks(_compact_spec())
    assert len(ticks) >= 1_000
    assert actual_calendar_days_from_ticks(ticks) >= 86
    prev = ""
    sources = set()
    sessions = set()
    for row in ticks:
        ts = str(row["timestamp"])
        assert ts > prev
        prev = ts
        assert float(row["last"]) > 0
        assert float(row["ask"]) > float(row["bid"])
        assert row["source"] == SOURCE_LABEL
        sources.add(row["source"])
        sessions.add(row.get("session"))
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert sources == {SOURCE_LABEL}
    assert "RTH" in sessions and "ETH" in sessions


@pytest.mark.slow
def test_persist_writes_certified_cache_with_three_holdout_regimes(tmp_path: Path) -> None:
    """Full enrich + certified cache. Slow: sliding ADX over 90d tape (>15s CI)."""
    result = persist_cloud_fixture(tmp_path, spec=_compact_spec())
    assert certified_tick_cache_present(tmp_path)
    cached = load_ticks_cache(tmp_path)
    assert cached
    assert all(str(t.get("source")) == SOURCE_LABEL for t in cached)
    manifest = load_cache_manifest(tmp_path)
    assert manifest is not None
    assert int(manifest["requested_days"]) >= 90
    assert int(manifest["actual_calendar_days"]) >= 86
    assert manifest.get("source") == SOURCE_LABEL
    assert "NQ" in str(manifest.get("instruments") or manifest.get("instrument") or "")
    holdout_regimes = set(regime_labels(result.split.holdout))
    assert len(holdout_regimes) >= 3
    report = assess_split_preflight(
        result.split, thresholds=BirthCertificateThresholds()
    )
    assert report.ok, report.failure_reasons


@pytest.mark.unit
def test_fixture_market_data_never_calls_fabric() -> None:
    ticks = generate_cloud_fixture_ticks(
        CloudFixtureSpec(calendar_days=90, rth_bar_seconds=300, eth_bar_seconds=900, seed=3)
    )
    svc = FixtureMarketDataService(ticks, instrument="NQ SEP26")
    assert svc._app().INSTRUMENT == "NQ SEP26"
    loaded = svc.load_historical_ohlc_extended(days_back=90, instrument="NQ SEP26")
    assert len(loaded) == len(ticks)
    assert loaded[0]["source"] == SOURCE_LABEL
