"""Additional birth constitution guard and aperture guard coverage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.risk.aperture_guard import enforce_no_bypass_in_strict_mode, logger as aperture_logger


@pytest.mark.unit
def test_birth_constitution_guard_post_init_fallback_on_bible_error() -> None:
    with patch("lumina_core.birth.birth_constitution_guard.BibleEngine", side_effect=RuntimeError("boom")):
        guard = BirthConstitutionGuard()
    assert guard._news_cfg == {} or isinstance(guard._news_cfg, dict)


@pytest.mark.unit
def test_birth_constitution_guard_publish_failure_is_non_fatal() -> None:
    bus = MagicMock()
    bus.publish_validated.side_effect = RuntimeError("bus down")
    guard = BirthConstitutionGuard(event_bus=bus, mode="birth")
    ok, reason = guard.check_entry(tick={}, side=1, stop_pct=0.0, equity=10_000.0)
    assert ok is False
    assert reason == "invalid_stop"


@pytest.mark.unit
def test_aperture_guard_emit_failure_is_non_fatal() -> None:
    from lumina_core.agent_orchestration.event_bus import EventBus
    from lumina_core.engine.errors import LuminaError

    bus = EventBus()
    bus.publish_validated = MagicMock(side_effect=RuntimeError("fail"))  # type: ignore[method-assign]
    engine = type("E", (), {"config": type("C", (), {"trade_mode": "real"})(), "event_bus": bus})()
    with pytest.raises(LuminaError):
        enforce_no_bypass_in_strict_mode(
            engine=engine,
            bypass_id="emit_fail_test",
            caller="test",
        )


@pytest.mark.unit
def test_aperture_guard_non_strict_with_reason_string() -> None:
    engine = type("E", (), {"config": type("C", (), {"trade_mode": "paper"})()})()
    with patch.object(aperture_logger, "warning") as warn:
        enforce_no_bypass_in_strict_mode(
            engine=engine,
            bypass_id="paper_shortcut",
            caller="test_coverage",
            reason="exploratory",
        )
    assert warn.called
