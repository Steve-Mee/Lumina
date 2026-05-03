from __future__ import annotations

import pytest

from lumina_core.monitoring.runtime_counters import RuntimeCounters


@pytest.mark.unit
def test_runtime_counters_defaults() -> None:
    # gegeven
    counters = RuntimeCounters()

    # wanneer / dan
    assert counters.cost_tracker["today"] == 0.0
    assert counters.rate_limit_backoff_seconds == 0
    assert counters.dashboard_last_has_image is False


@pytest.mark.unit
def test_runtime_counters_mutability() -> None:
    # gegeven
    counters = RuntimeCounters()

    # wanneer
    counters.cost_tracker["today"] = 11.5
    counters.restart_count = 2
    counters.dashboard_last_chart_ts = 123.45
    counters.dashboard_last_has_image = True

    # dan
    assert counters.cost_tracker["today"] == pytest.approx(11.5, rel=0.0, abs=1e-9)
    assert counters.restart_count == 2
    assert counters.dashboard_last_chart_ts == pytest.approx(123.45, rel=0.0, abs=1e-9)
    assert counters.dashboard_last_has_image is True
