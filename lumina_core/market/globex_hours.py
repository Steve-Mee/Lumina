"""CME equity Globex hours for ES, NQ, YM, RTY and MES.

Sunday 18:00 ET through Friday 17:00 ET. Monday–Thursday 17:00–18:00 ET is the halt.
17:00 ET is closed. 18:00 ET is open. A naive timestamp is invalid, not open.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BRUSSELS = ZoneInfo("Europe/Brussels")
OPEN_MIN = 18 * 60
CLOSE_MIN = 17 * 60

_WEEKDAY_NL = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")


def parse_instant(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(ET)


def globex_status(moment: datetime) -> str:
    """`open`, `halt`, or `weekend`. Naive datetimes raise."""
    local = _et(moment)
    weekday = local.weekday()
    minutes = local.hour * 60 + local.minute
    if weekday == 5:
        return "weekend"
    if weekday == 6:
        return "weekend" if minutes < OPEN_MIN else "open"
    if weekday == 4:
        return "weekend" if minutes >= CLOSE_MIN else "open"
    if CLOSE_MIN <= minutes < OPEN_MIN:
        return "halt"
    return "open"


def next_open(moment: datetime) -> datetime:
    """Next 18:00 ET at which the book is open. If `moment` is already open, the following one."""
    local = _et(moment)
    if globex_status(local) != "open":
        return _upcoming_open(local)
    cursor = local + timedelta(minutes=1)
    for _ in range(8 * 24 * 60):
        if globex_status(cursor) == "open" and (cursor.hour, cursor.minute) == (18, 0):
            return cursor.replace(second=0, microsecond=0)
        cursor += timedelta(minutes=1)
    return _upcoming_open(local)


def history_request_end(moment: datetime) -> datetime:
    """Last instant NT may be asked for bars. A closed book ends at the last real close.

    The close is 17:00 ET. Saturday and Sunday walk back to Friday 17:00 ET.
    The daily halt ends at 17:00 ET the same day. An open book uses `moment`.
    """
    local = _et(moment)
    status = globex_status(local)
    if status == "open":
        return moment.astimezone(timezone.utc)
    if status == "halt":
        close = local.replace(hour=17, minute=0, second=0, microsecond=0)
        return close.astimezone(timezone.utc)
    cursor = local
    while cursor.weekday() != 4:
        cursor = cursor - timedelta(days=1)
    close = cursor.replace(hour=17, minute=0, second=0, microsecond=0)
    return close.astimezone(timezone.utc)


def globex_session_date(moment: datetime) -> date:
    """Trade date. 18:00 ET and later belong to the next session. Brussels is not consulted."""
    local = _et(moment)
    if local.hour >= 18:
        return (local + timedelta(days=1)).date()
    return local.date()


def closed_sentence(moment: datetime) -> str | None:
    """Dutch line while the book is shut. ET decides. Brussels is only the translation."""
    if globex_status(moment) == "open":
        return None
    opening = next_open(moment)
    brussels = opening.astimezone(BRUSSELS)
    et_day = _WEEKDAY_NL[opening.weekday()]
    bru_day = _WEEKDAY_NL[brussels.weekday()]
    return (
        f"Beurs dicht tot {et_day} {opening.strftime('%H:%M')} ET "
        f"({bru_day} {brussels.strftime('%H:%M')} Brussel). Geen stall. Geen order."
    )


def _upcoming_open(local: datetime) -> datetime:
    weekday = local.weekday()
    minutes = local.hour * 60 + local.minute
    if weekday <= 3 and CLOSE_MIN <= minutes < OPEN_MIN:
        return _at(local, 0, 18)
    if weekday == 4 and minutes >= CLOSE_MIN:
        return _at(local, 2, 18)
    if weekday == 5:
        return _at(local, 1, 18)
    if weekday == 6 and minutes < OPEN_MIN:
        return _at(local, 0, 18)
    return _at(local, 0, 18)


def _at(local: datetime, day_delta: int, hour: int) -> datetime:
    shifted = local + timedelta(days=day_delta)
    return shifted.replace(hour=hour, minute=0, second=0, microsecond=0)


def _et(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("naive_timestamp")
    return moment.astimezone(ET)
