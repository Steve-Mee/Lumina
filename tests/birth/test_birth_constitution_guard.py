from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard


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
    assert guard.violations == 1


@pytest.mark.unit
def test_birth_constitution_guard_blocks_risk_cap() -> None:
    guard = BirthConstitutionGuard()
    ok, reason = guard.check_entry(
        tick={},
        side=1,
        stop_pct=0.02,
        equity=50_000.0,
    )
    assert ok is False
    assert reason == "risk_cap"
    assert guard.violations == 1


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
    assert guard.violation_reasons == []


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
