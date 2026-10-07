"""Globex boundaries. 17:00 ET is closed. 18:00 ET is open. DST does not move the rule."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumina_core.market.globex_hours import (
    BRUSSELS,
    ET,
    closed_sentence,
    globex_session_date,
    globex_status,
    history_request_end,
    next_open,
)
from lumina_core.maturity.apprenticeship.days import row_session_date


def _et(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    from zoneinfo import ZoneInfo

    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


@pytest.mark.unit
def test_friday_close_and_sunday_open() -> None:
    assert globex_status(_et(2026, 10, 2, 16, 59)) == "open"
    assert globex_status(_et(2026, 10, 2, 17, 0)) == "weekend"
    assert globex_status(_et(2026, 10, 4, 17, 59)) == "weekend"
    assert globex_status(_et(2026, 10, 4, 18, 0)) == "open"


@pytest.mark.unit
def test_weekday_halt_is_one_hour() -> None:
    assert globex_status(_et(2026, 10, 5, 16, 59)) == "open"
    assert globex_status(_et(2026, 10, 5, 17, 0)) == "halt"
    assert globex_status(_et(2026, 10, 5, 17, 59)) == "halt"
    assert globex_status(_et(2026, 10, 5, 18, 0)) == "open"
    assert next_open(_et(2026, 10, 5, 17, 30)).hour == 18


@pytest.mark.unit
def test_dst_sundays_keep_the_eighteen_hundred_open() -> None:
    spring = _et(2026, 3, 8, 18, 0)
    autumn = _et(2026, 11, 1, 18, 0)
    assert globex_status(spring) == "open"
    assert globex_status(autumn) == "open"
    assert globex_status(_et(2026, 3, 8, 17, 59)) == "weekend"


@pytest.mark.unit
def test_naive_timestamp_is_not_open() -> None:
    with pytest.raises(ValueError):
        globex_status(datetime(2026, 10, 5, 15, 0))


@pytest.mark.unit
def test_closed_sentence_names_new_york_and_brussels() -> None:
    halt = closed_sentence(_et(2026, 10, 5, 17, 30))
    weekend = closed_sentence(_et(2026, 10, 3, 12, 0))
    assert halt is not None and "18:00 ET" in halt and "Brussel" in halt and "Geen stall" in halt
    assert weekend is not None and "zondag" in weekend and "Brussel" in weekend
    assert closed_sentence(_et(2026, 10, 5, 15, 0)) is None


@pytest.mark.unit
def test_brussels_is_not_the_exchange_clock() -> None:
    """Winter and summer are six hours. The two mismatch weeks are five. Never a fixed offset."""
    winter_open = datetime(2026, 1, 11, 18, 0, tzinfo=ET)
    summer_open = datetime(2026, 7, 12, 18, 0, tzinfo=ET)
    march_gap = datetime(2026, 3, 15, 18, 0, tzinfo=ET)
    october_gap = datetime(2026, 10, 28, 17, 30, tzinfo=ET)
    assert winter_open.astimezone(BRUSSELS).hour == 0
    assert summer_open.astimezone(BRUSSELS).hour == 0
    march = march_gap.astimezone(BRUSSELS)
    assert (march.hour, march.day) == (23, 15)
    october = october_gap.astimezone(BRUSSELS)
    assert (october.hour, october.minute) == (22, 30)
    assert globex_status(datetime(2026, 1, 11, 18, 0, tzinfo=BRUSSELS)) == "weekend"
    assert globex_status(winter_open) == "open"
    assert globex_status(march_gap) == "open"
    assert globex_status(october_gap) == "halt"
    assert globex_session_date(march_gap).isoformat() == "2026-03-16"
    march_line = str(closed_sentence(datetime(2026, 3, 15, 17, 30, tzinfo=ET)))
    october_line = str(closed_sentence(october_gap))
    assert "18:00 ET" in march_line and "23:00 Brussel" in march_line
    assert "18:00 ET" in october_line and "23:00 Brussel" in october_line
    assert "22:30" not in october_line


@pytest.mark.unit
def test_closed_weekend_history_ends_at_friday_close_not_now() -> None:
    saturday = _et(2026, 10, 3, 12, 0)
    end = history_request_end(saturday).astimezone(ET)
    assert end.weekday() == 4
    assert (end.hour, end.minute) == (17, 0)
    halt = history_request_end(_et(2026, 10, 5, 17, 30)).astimezone(ET)
    assert (halt.hour, halt.minute) == (17, 0)
    assert halt.day == 5


@pytest.mark.unit
def test_session_date_follows_the_eighteen_hundred_et_reopen() -> None:
    friday = datetime(2026, 10, 2, 20, 59, tzinfo=timezone.utc)  # 16:59 ET
    sunday = datetime(2026, 10, 4, 22, 1, tzinfo=timezone.utc)  # 18:01 ET
    assert row_session_date({"ts": friday.isoformat()}) == friday.astimezone(timezone.utc).date()
    monday = row_session_date({"ts": sunday.isoformat()})
    assert monday is not None and monday.isoformat() == "2026-10-05"
