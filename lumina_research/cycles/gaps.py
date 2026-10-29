"""Known P2 data gaps. Exclude the windows. Never fill."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

UTC = timezone.utc


@dataclass(frozen=True, slots=True)
class GapWindow:
    instrument: str
    start_ns: int
    end_ns: int
    reason: str

    def contains(self, ts_ns: int) -> bool:
        return self.start_ns <= int(ts_ns) <= self.end_ns

    def matches(self, instrument: str) -> bool:
        return self.instrument in {"*", instrument}


def _ns(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> int:
    stamp = datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    return int(stamp.timestamp() * 1_000_000_000)


# Inclusive UTC windows from GAPS.md (P2 package, 2026-10-29). Date-only ranges
# cover the full UTC calendar days named. Never interpolate inside them.
KNOWN_GAPS: tuple[GapWindow, ...] = (
    GapWindow("MNQ", _ns(2025, 6, 30), _ns(2025, 7, 2) - 1, "MNQ missing 2025-06-30..2025-07-01"),
    GapWindow("MNQ", _ns(2025, 7, 13), _ns(2025, 7, 16) - 1, "MNQ missing 2025-07-13..2025-07-15"),
    GapWindow(
        "ES",
        _ns(2025, 7, 13),
        _ns(2025, 7, 16) - 1,
        "ES TRAIN hole 2025-07-13/14/15 (instrument-specific; NQ/MES present; never fill from MES)",
    ),
    GapWindow("MNQ", _ns(2026, 1, 26), _ns(2026, 1, 28) - 1, "MNQ missing 2026-01-26..2026-01-27"),
    GapWindow("MNQ", _ns(2026, 7, 17), _ns(2026, 7, 18) - 1, "MNQ partial 2026-07-17"),
    GapWindow("MES", _ns(2026, 6, 9, 15, 0), _ns(2026, 6, 9, 15, 38), "MES short gap 2026-06-09 15:00-15:38Z"),
    GapWindow("MES", _ns(2026, 7, 24, 15, 2), _ns(2026, 7, 24, 15, 55), "MES short gap 2026-07-24 15:02-15:55Z"),
    GapWindow("*", _ns(2025, 11, 28), _ns(2025, 11, 29) - 1, "CME outage 2025-11-28"),
    # Holdout pin 2026-01-28T23:00Z is closed. These windows are recorded so a
    # later holdout eval cannot score incomplete ES days. They are not used now.
    GapWindow("ES", _ns(2026, 4, 22), _ns(2026, 4, 28) - 1, "ES HOLDOUT hole 2026-04-22..04-27; unused"),
    GapWindow("ES", _ns(2026, 5, 8), _ns(2026, 5, 9) - 1, "ES HOLDOUT hole 2026-05-08; unused"),
    GapWindow("ES", _ns(2026, 5, 11), _ns(2026, 5, 13) - 1, "ES HOLDOUT hole 2026-05-11/12; unused"),
)


def gaps_for(instrument: str) -> tuple[GapWindow, ...]:
    root = instrument.strip().upper()
    return tuple(item for item in KNOWN_GAPS if item.matches(root))


def in_known_gap(instrument: str, ts_ns: int) -> bool:
    return any(item.contains(ts_ns) for item in gaps_for(instrument))


def interval_crosses_gap(instrument: str, prev_ns: int, curr_ns: int) -> bool:
    """True when (prev, curr) overlaps a known gap. Never take a return across it."""
    if int(curr_ns) <= int(prev_ns):
        return False
    for gap in gaps_for(instrument):
        if int(prev_ns) < gap.end_ns and int(curr_ns) > gap.start_ns:
            return True
    return False
