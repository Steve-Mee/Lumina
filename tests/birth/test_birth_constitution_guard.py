from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lumina_core.birth.birth_constitution_guard import (
    BIRTH_MAX_RISK_STOP_PCT,
    BirthConstitutionGuard,
    clip_birth_risk_params,
)


@pytest.mark.unit
def test_clip_birth_risk_params_hard_clips_into_1pct_band() -> None:
    stop, target, clipped = clip_birth_risk_params(0.015, 0.03)
    assert clipped is True
    assert stop == pytest.approx(BIRTH_MAX_RISK_STOP_PCT)
    # RR preserved: 0.03/0.015 = 2 → target 0.02
    assert target == pytest.approx(0.02)
    stop2, target2, clipped2 = clip_birth_risk_params(0.005, 0.01)
    assert clipped2 is False
    assert stop2 == pytest.approx(0.005)
    assert target2 == pytest.approx(0.01)


@pytest.mark.unit
def test_prepare_entry_clips_and_allows_oversized_stop() -> None:
    """P1: oversize stop is clipped into band and executes (no soft risk_cap)."""
    guard = BirthConstitutionGuard()
    ok, reason, stop, target = guard.prepare_entry(
        tick={},
        side=1,
        stop_pct=0.015,
        target_pct=0.03,
        equity=50_000.0,
    )
    assert ok is True
    assert reason == ""
    assert stop == pytest.approx(BIRTH_MAX_RISK_STOP_PCT)
    assert target == pytest.approx(0.02)
    assert guard.soft_blocks == 0


@pytest.mark.unit
def test_soft_block_histogram_tracks_reasons() -> None:
    guard = BirthConstitutionGuard()
    guard.check_entry(tick={}, side=1, stop_pct=0.0, equity=50_000.0)
    guard.check_entry(tick={}, side=1, stop_pct=0.02, equity=50_000.0, auto_clip=False)
    guard.check_entry(tick={"news_window_active": 1.0}, side=1, stop_pct=0.005, equity=50_000.0)
    hist = guard.soft_block_histogram()
    assert hist.get("invalid_stop_pct", 0) == 1
    assert hist.get("risk_exceeds_1pct", 0) == 1
    assert hist.get("news_window_entry_blocked", 0) == 1


def test_soft_publish_throttled_every_500() -> None:
    bus = MagicMock()
    guard = BirthConstitutionGuard(event_bus=bus, mode="birth")
    for _ in range(500):
        guard.check_entry(tick={}, side=1, stop_pct=0.0, equity=50_000.0)
    # First 3 + 500th → 4 publishes for 500 soft blocks
    assert guard.soft_blocks == 500
    assert bus.publish_validated.call_count == 4


@pytest.mark.unit
def test_birth_constitution_guard_blocks_news_window() -> None:
    guard = BirthConstitutionGuard()
    ok, reason = guard.check_entry(
        tick={"news_window_active": 1.0},
        side=1,
        stop_pct=0.005,
        equity=50_000.0,
    )
    assert ok is False
    assert reason == "news_window"
    # Soft block: constitution held; does not count as hard graduation violation.
    assert guard.soft_blocks == 1
    assert guard.violations == 0


@pytest.mark.unit
def test_birth_constitution_guard_blocks_risk_cap() -> None:
    """Without auto_clip, oversized stop still soft-blocks (legacy path)."""
    guard = BirthConstitutionGuard()
    ok, reason = guard.check_entry(
        tick={},
        side=1,
        stop_pct=0.02,
        equity=50_000.0,
        auto_clip=False,
    )
    assert ok is False
    assert reason == "risk_cap"
    assert guard.soft_blocks == 1
    assert guard.violations == 0


@pytest.mark.unit
def test_check_entry_auto_clip_allows_oversized_stop() -> None:
    """Default auto_clip: 1.5% stop becomes legal 1% — plant breathes."""
    guard = BirthConstitutionGuard()
    ok, reason = guard.check_entry(
        tick={},
        side=1,
        stop_pct=0.015,
        equity=50_000.0,
    )
    assert ok is True
    assert reason == ""
    assert guard.soft_blocks == 0
    assert guard.clips_applied >= 1


@pytest.mark.unit
def test_check_entry_negative_equity_does_not_permanent_soft_block() -> None:
    """Negative equity must not invert risk check into eternal risk_exceeds_1pct."""
    guard = BirthConstitutionGuard()
    ok, reason = guard.check_entry(
        tick={},
        side=1,
        stop_pct=0.0075,
        equity=-1_000.0,
        auto_clip=False,
    )
    assert ok is True
    assert reason == ""
    assert guard.soft_blocks == 0


@pytest.mark.unit
def test_birth_constitution_guard_publishes_event_on_violation() -> None:
    bus = MagicMock()
    guard = BirthConstitutionGuard(event_bus=bus, mode="birth")
    guard.check_entry(tick={}, side=1, stop_pct=0.0, equity=50_000.0)
    bus.publish_validated.assert_called_once()
    call_kwargs = bus.publish_validated.call_args.kwargs
    assert call_kwargs["topic"] == "safety.constitution.violation"
    assert call_kwargs["producer"] == "birth.constitution_guard"
    assert call_kwargs["payload"]["principle_name"] == "birth_constitution_guard"
    assert call_kwargs["payload"]["severity"] == "warning"
    assert call_kwargs["payload"]["mode"] == "birth"


@pytest.mark.unit
def test_birth_constitution_guard_allows_valid_entry() -> None:
    guard = BirthConstitutionGuard()
    ok, reason = guard.check_entry(
        tick={},
        side=1,
        stop_pct=0.005,
        equity=50_000.0,
    )
    assert ok is True
    assert reason == ""
    assert guard.violations == 0


@pytest.mark.unit
def test_birth_constitution_guard_reset_clears_state() -> None:
    guard = BirthConstitutionGuard()
    guard.check_entry(tick={"news_window_active": 1.0}, side=1, stop_pct=0.005, equity=50_000.0)
    guard.reset()
    assert guard.violations == 0
    assert guard.soft_blocks == 0
    assert guard.violation_reasons == []
    assert guard.soft_block_reasons == []


@pytest.mark.unit
def test_birth_constitution_guard_blocks_invalid_stop() -> None:
    guard = BirthConstitutionGuard()
    ok, reason = guard.check_entry(tick={}, side=1, stop_pct=0.0, equity=50_000.0)
    assert ok is False
    assert reason == "invalid_stop"


@pytest.mark.unit
def test_birth_constitution_guard_hold_side_skips_checks() -> None:
    guard = BirthConstitutionGuard()
    ok, reason = guard.check_entry(
        tick={"news_window_active": 1.0}, side=0, stop_pct=0.0, equity=50_000.0
    )
    assert ok is True
    assert guard.violations == 0
