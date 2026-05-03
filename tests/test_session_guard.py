from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from lumina_core.risk.session_guard import SessionGuard


class _CalendarOk:
    def schedule(self, *, start_date, end_date):
        del start_date, end_date
        return pd.DataFrame(
            {
                "market_open": [pd.Timestamp("2026-04-21T13:30:00+00:00")],
                "market_close": [pd.Timestamp("2026-04-21T20:00:00+00:00")],
            }
        )


def test_session_guard_is_market_open_uses_schedule_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = SessionGuard()
    guard._calendar = _CalendarOk()

    calls = {"count": 0}
    original_schedule = guard._calendar.schedule

    def _counting_schedule(*, start_date, end_date):
        calls["count"] += 1
        return original_schedule(start_date=start_date, end_date=end_date)

    guard._calendar.schedule = _counting_schedule  # type: ignore[assignment]

    ts = datetime(2026, 4, 21, 15, 0, tzinfo=timezone.utc)
    first = guard.is_market_open(ts)
    second = guard.is_market_open(ts)

    assert first is True
    assert second is True
    assert calls["count"] == 1


def test_session_guard_fail_closed_on_schedule_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = SessionGuard(schedule_timeout_seconds=0.1)

    class _FutureTimeout:
        def result(self, timeout=None):
            del timeout
            raise TimeoutError("simulated timeout")

        def cancel(self):
            return True

    class _ExecutorTimeout:
        def submit(self, fn):
            del fn
            return _FutureTimeout()

    guard._schedule_executor = _ExecutorTimeout()  # type: ignore[assignment]

    ts = datetime(2026, 4, 21, 15, 0, tzinfo=timezone.utc)
    assert guard.is_market_open(ts) is False


def test_session_guard_fail_closed_on_schedule_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = SessionGuard(schedule_timeout_seconds=0.1)

    class _FutureInterrupt:
        def result(self, timeout=None):
            del timeout
            raise KeyboardInterrupt()

        def cancel(self):
            return True

    class _ExecutorInterrupt:
        def submit(self, fn):
            del fn
            return _FutureInterrupt()

    guard._schedule_executor = _ExecutorInterrupt()  # type: ignore[assignment]

    ts = datetime(2026, 4, 21, 15, 0, tzinfo=timezone.utc)
    assert guard.is_market_open(ts) is False
