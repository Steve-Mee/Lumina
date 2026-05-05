"""Smoke/unit tests for first-boot UI estimates (launcher-aligned, no Streamlit)."""

from __future__ import annotations

import pytest

from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_MAX_REAL_DAYS,
    FIRST_BOOT_DEFAULT_TRADES,
    FIRST_BOOT_EST_TRADES_PER_REAL_DAY,
    FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS,
    FIRST_BOOT_TRADE_MAX,
    FIRST_BOOT_TRADE_MIN,
    FIRST_BOOT_TRADE_STEP,
    estimate_first_boot_real_days,
    exceeds_max_real_days_window,
    is_high_load_estimate,
    normalize_first_boot_training_trades,
)


@pytest.mark.unit
def test_estimate_first_boot_real_days_matches_prompt_examples() -> None:
    # Rough formula from LUMINA_CURSOR_FIRST_BOOT_REAL_DATA_PROMPT.md
    assert estimate_first_boot_real_days(100_000) == 40
    assert estimate_first_boot_real_days(300_000) == 120
    assert estimate_first_boot_real_days(500_000) == 200
    assert estimate_first_boot_real_days(1_000_000) == 400
    assert estimate_first_boot_real_days(2_000_000) == 800
    assert FIRST_BOOT_EST_TRADES_PER_REAL_DAY == 2500


@pytest.mark.unit
def test_exceeds_max_real_days_window_default_config() -> None:
    """Default max_real_days in config is 90; 1M trades → 400 estimated days → warn."""
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
def test_normalize_first_boot_training_trades_uses_shared_bounds_and_step() -> None:
    assert FIRST_BOOT_DEFAULT_TRADES == 500_000
    assert FIRST_BOOT_TRADE_MIN == 100_000
    assert FIRST_BOOT_TRADE_MAX == 2_000_000
    assert FIRST_BOOT_TRADE_STEP == 100_000
    assert normalize_first_boot_training_trades(None) == 500_000
    assert normalize_first_boot_training_trades(49_999) == 100_000
    assert normalize_first_boot_training_trades(155_000) == 200_000
    assert normalize_first_boot_training_trades(2_500_000) == 2_000_000
