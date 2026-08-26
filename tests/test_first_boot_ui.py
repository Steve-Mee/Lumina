"""Smoke/unit tests for first-boot UI estimates (launcher-aligned, no Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.first_boot_ui import (
    BIRTH_BARS_PER_TRADING_DAY,
    FIRST_BOOT_DEFAULT_MAX_REAL_DAYS,
    FIRST_BOOT_DEFAULT_TRADES,
    FIRST_BOOT_EST_TRADES_PER_REAL_DAY,
    FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS,
    FIRST_BOOT_MIN_REAL_DAYS,
    FIRST_BOOT_TRADE_MAX,
    FIRST_BOOT_TRADE_MIN,
    FIRST_BOOT_TRADE_STEP,
    FIRST_BOOT_TRAINING_TRADES_MAX,
    FIRST_BOOT_TRAINING_TRADES_MIN,
    estimate_first_boot_duration,
    estimate_first_boot_real_days,
    exceeds_max_real_days_window,
    format_duration_range,
    is_high_load_estimate,
    normalize_first_boot_training_trades,
    resolve_default_max_real_days,
    resolve_historical_bar_limit,
)


@pytest.mark.unit
def test_estimate_first_boot_real_days_matches_engine_ssot() -> None:
    assert FIRST_BOOT_EST_TRADES_PER_REAL_DAY == 450
    assert estimate_first_boot_real_days(25_000) == 56
    assert estimate_first_boot_real_days(100_000) == 223
    assert estimate_first_boot_real_days(300_000) == 667
    assert estimate_first_boot_real_days(500_000) == 1112
    assert estimate_first_boot_real_days(1_000_000) == 2223
    assert estimate_first_boot_real_days(2_000_000) == 4445


@pytest.mark.unit
def test_resolve_default_max_real_days_is_foundation_ceiling() -> None:
    assert FIRST_BOOT_MIN_REAL_DAYS == 90
    assert FIRST_BOOT_DEFAULT_MAX_REAL_DAYS == 365
    assert resolve_default_max_real_days(25_000) == 365
    assert resolve_default_max_real_days(5_000) == 365
    assert resolve_default_max_real_days(100_000) == 365


@pytest.mark.unit
def test_resolve_historical_bar_limit_no_25k_cap() -> None:
    limit = resolve_historical_bar_limit(30)
    assert limit is not None
    assert limit == 30 * BIRTH_BARS_PER_TRADING_DAY
    assert limit != 25_000
    assert resolve_historical_bar_limit(90) == 90 * BIRTH_BARS_PER_TRADING_DAY


@pytest.mark.unit
def test_exceeds_max_real_days_window_default_config() -> None:
    """Default max_real_days ceiling is 365; large duration estimates should trigger a warning."""
    max_days = FIRST_BOOT_DEFAULT_MAX_REAL_DAYS
    assert exceeds_max_real_days_window(400, max_days) is True
    assert exceeds_max_real_days_window(80, max_days) is False


@pytest.mark.unit
def test_is_high_load_estimate_threshold_700() -> None:
    """>700 estimated days → second-tier operator warning in launcher."""
    assert FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS == 700
    assert is_high_load_estimate(701) is True
    assert is_high_load_estimate(700) is False
    assert is_high_load_estimate(800) is True


@pytest.mark.unit
def test_normalize_first_boot_training_trades_clamps_to_bounds_without_coarse_snapping() -> None:
    """User-chosen trade counts must round-trip (within min/max); no 100k-floor override."""
    assert FIRST_BOOT_DEFAULT_TRADES == 5_000
    assert FIRST_BOOT_TRAINING_TRADES_MIN == 500
    assert FIRST_BOOT_TRAINING_TRADES_MAX == 2_000_000
    assert FIRST_BOOT_TRADE_MIN == FIRST_BOOT_TRAINING_TRADES_MIN
    assert FIRST_BOOT_TRADE_MAX == FIRST_BOOT_TRAINING_TRADES_MAX
    assert FIRST_BOOT_TRADE_STEP == 500

    assert normalize_first_boot_training_trades(None) == 5_000
    assert normalize_first_boot_training_trades(499) == FIRST_BOOT_TRAINING_TRADES_MIN
    assert normalize_first_boot_training_trades(5_000) == 5_000
    assert normalize_first_boot_training_trades(155_000) == 155_000
    assert normalize_first_boot_training_trades(2_500_000) == FIRST_BOOT_TRAINING_TRADES_MAX


@pytest.mark.unit
def test_estimate_first_boot_duration_uses_journal_samples(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal" / "simulator"
    journal_dir.mkdir(parents=True)
    reports = [
        {"status": "ok_real_only", "trades": 60_000, "elapsed_sec": 2_500.0, "synthetic_pct": 0.0},
        {"status": "ok_real_only", "trades": 67_500, "elapsed_sec": 2_760.0, "synthetic_pct": 0.0},
        {"status": "ok_real_only", "trades": 50_000, "elapsed_sec": 1_950.0, "synthetic_pct": 0.0},
        {"status": "ok_minimal_synthetic_fallback", "trades": 300_000, "elapsed_sec": 7.0, "synthetic_pct": 99.0},
    ]
    for idx, payload in enumerate(reports):
        (journal_dir / f"first_boot_training_20260101_00000{idx}.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    estimate = estimate_first_boot_duration(
        training_trades=500_000,
        max_real_days=90,
        prefer_real_data_only=True,
        allow_minimal_synthetic_fallback=False,
        workspace_root=tmp_path,
    )

    assert estimate.method == "journal"
    assert estimate.confidence in {"medium", "high"}
    assert estimate.breakdown["sim_trades_per_sec"] < 40.0
    assert estimate.seconds_max > estimate.seconds_min > 0


@pytest.mark.unit
def test_estimate_first_boot_duration_hardware_fallback_without_journal(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "hardware_snapshot.json").write_text(
        json.dumps({"profile_tier": "sweet", "cpu_cores_logical": 8}),
        encoding="utf-8",
    )

    estimate = estimate_first_boot_duration(
        training_trades=100_000,
        max_real_days=120,
        prefer_real_data_only=True,
        allow_minimal_synthetic_fallback=False,
        workspace_root=tmp_path,
    )

    assert estimate.method == "hardware"
    assert estimate.confidence == "low"
    assert estimate.breakdown["sim_trades_per_sec"] > 0
    assert "hardwarefallback" in " ".join(estimate.notes).lower()


@pytest.mark.unit
def test_estimate_first_boot_duration_includes_synthetic_capacity_note(tmp_path: Path) -> None:
    estimate = estimate_first_boot_duration(
        training_trades=900_000,
        max_real_days=90,
        prefer_real_data_only=True,
        allow_minimal_synthetic_fallback=False,
        workspace_root=tmp_path,
        profile_tier="sweet",
        workers=8,
    )
    assert any("synthetic" in note.lower() for note in estimate.notes)


@pytest.mark.unit
def test_format_duration_range_renders_human_readable(tmp_path: Path) -> None:
    estimate = estimate_first_boot_duration(
        training_trades=5_000,
        max_real_days=60,
        prefer_real_data_only=True,
        allow_minimal_synthetic_fallback=False,
        workspace_root=tmp_path,
        profile_tier="sweet",
        workers=8,
    )
    rendered = format_duration_range(estimate)
    assert "typisch" in rendered
    assert "-" in rendered
