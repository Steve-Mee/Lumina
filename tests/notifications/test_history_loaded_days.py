"""History-loaded Telegram copy must use actual calendar days, not the ceiling."""

from __future__ import annotations

from lumina_core.notifications.milestone_events_birth import history_loaded_event


def test_history_loaded_event_prefers_actual_calendar_days() -> None:
    event = history_loaded_event(
        tick_count=352800,
        real_data_pct=100.0,
        max_real_days=365,
        actual_calendar_days=91,
    )
    assert "91 dagen" in event.summary
    assert "365 dagen" not in event.summary
    assert event.context.get("actual_calendar_days") == 91
    assert event.context.get("max_real_days") == 365


def test_history_loaded_event_falls_back_to_max_when_actual_missing() -> None:
    event = history_loaded_event(
        tick_count=1000,
        real_data_pct=100.0,
        max_real_days=90,
    )
    assert "90 dagen" in event.summary
