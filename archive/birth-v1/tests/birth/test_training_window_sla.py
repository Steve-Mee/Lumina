"""C3: training-window SLA before Stage 2 burn."""

from __future__ import annotations

import pytest

from lumina_core.birth.training_window_sla import (
    stage2_requires_data_expand,
    training_window_ratio,
    training_window_sla_ok,
    training_window_sla_report,
)


@pytest.mark.unit
def test_sla_passes_at_full_window() -> None:
    assert training_window_sla_ok(days_loaded=56, requested_days=56) is True
    assert training_window_ratio(days_loaded=56, requested_days=56) == 1.0


@pytest.mark.unit
def test_sla_passes_at_95_percent() -> None:
    # 54/56 ≈ 0.964 ≥ 0.95
    assert training_window_sla_ok(days_loaded=54, requested_days=56, min_ratio=0.95) is True


@pytest.mark.unit
def test_sla_fails_audit_39_of_56() -> None:
    """Regression: 2026-08-08 Birth loaded 39/56 with preflight_ok — must fail SLA."""
    assert training_window_sla_ok(days_loaded=39, requested_days=56, min_ratio=0.95) is False
    report = training_window_sla_report(days_loaded=39, requested_days=56)
    assert report["ok"] is False
    assert report["stage2_entry_blocked"] is True
    assert report["shortfall_days"] == 17
    assert stage2_requires_data_expand(days_loaded=39, requested_days=56) is True


@pytest.mark.unit
def test_sla_fails_57_of_90_front_month_tape() -> None:
    assert training_window_sla_ok(days_loaded=57, requested_days=90, min_ratio=0.95) is False


@pytest.mark.unit
def test_sla_90_actual_vs_365_ceiling_is_not_the_rung() -> None:
    """Ceiling is not requested_days. 90 vs 90 passes; comparing 90 to 365 would false-fail."""
    assert training_window_sla_ok(days_loaded=90, requested_days=90, min_ratio=0.95) is True
    assert training_window_sla_ok(days_loaded=90, requested_days=365, min_ratio=0.95) is False


@pytest.mark.unit
def test_degraded_mode_allows_short_window_but_marked() -> None:
    assert (
        training_window_sla_ok(
            days_loaded=39,
            requested_days=56,
            degraded_data_mode=True,
        )
        is True
    )
    report = training_window_sla_report(
        days_loaded=39,
        requested_days=56,
        degraded_data_mode=True,
    )
    assert report["ok"] is True
    assert report["degraded_data_mode"] is True
    assert report["stage2_entry_blocked"] is False


@pytest.mark.unit
def test_zero_request_is_vacuously_ok() -> None:
    assert training_window_sla_ok(days_loaded=0, requested_days=0) is True
