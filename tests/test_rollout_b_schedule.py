from __future__ import annotations

from scripts.validation.build_sim_real_guard_rollout_b_schedule import build_schedule


def test_build_schedule_creates_15_windows_over_5_weekdays() -> None:
    windows = build_schedule(start_date="2026-04-13", trading_days=5)

    assert len(windows) == 15
    assert windows[0].trading_date == "2026-04-13"
    assert windows[-1].trading_date == "2026-04-17"


def test_build_schedule_skips_weekend_start() -> None:
    windows = build_schedule(start_date="2026-04-18", trading_days=2)

    assert len(windows) == 6
    assert windows[0].trading_date == "2026-04-20"
    assert windows[3].trading_date == "2026-04-21"


def test_build_schedule_uses_expected_window_durations() -> None:
    windows = build_schedule(start_date="2026-04-13", trading_days=1)

    assert [item.duration for item in windows] == ["30m", "30m", "35m"]
