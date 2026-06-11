"""
Contract tests for aperture_guard — Post Phase 1.3.4 Zero-Trace Hygiene.

After the complete structural removal of all four known bypass mechanisms
(B-001..B-004) and the 1.3.4 hygiene pass, the aperture guard has one
eternal purpose:

It is the permanent regression detector that makes any future attempt
to introduce a bypass or shortcut around the authoritative Admission
Chain + Final Arbitration immediately and loudly fatal in strict modes.

These tests verify exactly that contract. There are no legacy constants,
no "B-00x" ids, and no references to the pre-1.3.4 trusted-path era.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.risk.aperture_guard import (
    STRICT_MODES,
    enforce_no_bypass_in_strict_mode,
    logger as aperture_guard_logger,
)


class FakeEngine:
    """Minimal engine stub for testing the regression detector."""

    def __init__(self, trade_mode: str = "paper", event_bus=None):
        self.config = type("cfg", (), {"trade_mode": trade_mode})()
        self.event_bus = event_bus


def test_any_bypass_attempt_in_real_mode_is_fatal():
    """In REAL mode, any call (any bypass_id) must be fatal."""
    engine = FakeEngine(trade_mode="real")

    with pytest.raises(LuminaError) as exc_info:
        enforce_no_bypass_in_strict_mode(
            engine=engine,
            bypass_id="new_shortcut_somewhere",
            caller="test_future_erosion",
            reason="unit test of permanent detector",
        )

    err: LuminaError = exc_info.value
    assert err.severity == ErrorSeverity.FATAL_MODE_VIOLATION
    assert "ATTEMPT_TO_BYPASS_AUTHORITATIVE_GATE" in err.code
    assert "real" in err.message.lower()
    assert err.context["bypass_id"] == "new_shortcut_somewhere"


def test_any_bypass_attempt_in_sim_real_guard_mode_is_fatal():
    """In sim_real_guard mode, any call must be fatal (same invariant)."""
    engine = FakeEngine(trade_mode="sim_real_guard")

    with pytest.raises(LuminaError) as exc_info:
        enforce_no_bypass_in_strict_mode(
            engine=engine,
            bypass_id="another_potential_bypass",
            caller="test_sim_real_guard_path",
        )

    err: LuminaError = exc_info.value
    assert err.severity == ErrorSeverity.FATAL_MODE_VIOLATION
    assert "sim_real_guard" in err.message.lower()


def test_bypass_attempt_in_non_strict_emits_loud_warning():
    """In sim / paper / research modes the attempt must be loudly visible."""
    engine = FakeEngine(trade_mode="sim")

    with patch.object(aperture_guard_logger, "warning") as warn:
        enforce_no_bypass_in_strict_mode(
            engine=engine,
            bypass_id="tempting_shortcut_in_research_code",
            caller="test_sim_path",
            reason="exploratory shortcut",
        )

    assert warn.called
    message = " ".join(str(arg) for arg in warn.call_args[0])
    assert "APERTURE_REGRESSION_DETECTED" in message
    assert "tempting_shortcut_in_research_code" in message
    assert "authoritative Admission Chain + Final Arbitration" in message


def test_strict_modes_constant_is_correct():
    """The set of strict modes is the single source of truth for when the detector is fatal."""
    assert "real" in STRICT_MODES
    assert "sim_real_guard" in STRICT_MODES
    assert "paper" not in STRICT_MODES
    assert "sim" not in STRICT_MODES


def test_defensive_behavior_with_none_engine():
    """The detector must not crash when engine is None (treated as non-strict 'unknown' mode)."""
    with patch.object(aperture_guard_logger, "warning") as warn:
        enforce_no_bypass_in_strict_mode(
            engine=None,
            bypass_id="defensive_none_engine_test",
            caller="test_none_engine",
        )

    # None engine resolves to 'unknown' (non-strict) → loud warning, no raise.
    assert warn.called
    message = " ".join(str(arg) for arg in warn.call_args[0])
    assert "APERTURE_REGRESSION_DETECTED" in message
    assert "defensive_none_engine_test" in message