"""Verify the NT8 roll calendar, including Friday 2026-06-12."""

from __future__ import annotations

from datetime import date, datetime, timezone

from lumina_research.cycles.rolls import NT8_ROLL_DATES

# Friday 2026-06-12 is the Globex session date of the June roll in the P2 NT8
# zip manifests. June 2026 MES/MNQ expiry is the third Friday 2026-06-19.
# A Thursday 17:00 ET roll puts the first new-front bar in the Friday session
# that opens 18:00 ET Thursday (Globex session date Friday). Other listed
# dates land on Mondays because those rolls sit on Friday-before or Monday
# session labels in the same NT8 export. Source of truth remains the zip.
FRIDAY_ROLL = date(2026, 6, 12)
JUNE_2026_EXPIRY = date(2026, 6, 19)


def verify_nt8_rolls() -> dict[str, object]:
    weekdays = {item.isoformat(): item.strftime("%A") for item in NT8_ROLL_DATES}
    friday = FRIDAY_ROLL in NT8_ROLL_DATES and FRIDAY_ROLL.weekday() == 4
    mondays = tuple(item for item in NT8_ROLL_DATES if item.weekday() == 0)
    return {
        "friday_2026_06_12_present": FRIDAY_ROLL in NT8_ROLL_DATES,
        "friday_2026_06_12_is_friday": friday,
        "june_2026_third_friday_expiry": JUNE_2026_EXPIRY.isoformat(),
        "n_monday_rolls": len(mondays),
        "n_rolls": len(NT8_ROLL_DATES),
        "weekdays": weekdays,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": (
            "2026-06-12 Friday is the NT8 Globex session date of the June roll, "
            "not a calendar error. Indicators use back-adjusted prices; PnL uses "
            "the unadjusted series."
        ),
    }


def require_friday_roll() -> None:
    body = verify_nt8_rolls()
    if not body["friday_2026_06_12_present"] or not body["friday_2026_06_12_is_friday"]:
        raise RuntimeError("NT8 roll calendar missing Friday 2026-06-12")
