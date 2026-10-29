"""NT8 roll dates for the P2 unadjusted continuous MES/MNQ tapes.

Returns are never taken across a roll boundary. The date is the first Globex
session of the new front month (NinjaTrader 8 roll schedule in the export
manifests).
"""

from __future__ import annotations

from datetime import date

# Identical MES/MNQ NT8 roll calendar from the 2026-10-29 P2 zip manifests.
NT8_ROLL_DATES: tuple[date, ...] = (
    date(2023, 9, 11),
    date(2023, 12, 11),
    date(2024, 3, 11),
    date(2024, 6, 17),
    date(2024, 9, 16),
    date(2024, 12, 16),
    date(2025, 3, 17),
    date(2025, 6, 16),
    date(2025, 9, 15),
    date(2025, 12, 15),
    date(2026, 3, 16),
    date(2026, 6, 12),
    date(2026, 9, 14),
    date(2026, 12, 14),
)

NT8_ROLL_SET: frozenset[date] = frozenset(NT8_ROLL_DATES)


def is_roll_session(session: date) -> bool:
    return session in NT8_ROLL_SET
