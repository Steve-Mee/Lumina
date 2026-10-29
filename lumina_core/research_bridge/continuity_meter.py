"""NT-PIT continuity meter for S4 SIM-entry floors.

Research team decision (relayed by Steve 2026-10-29): FAR ≤ 10%, TTD fast ≤ 15d,
TTD slow ≤ 45d, power ≥ 85%, computed from real NT-PIT ClosedBar tape. No
caller-supplied float. Planted decay is a mean-shift on those NT returns.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

# Lazy imports below: ungated_place_block → sim_gate → this module must not load
# lumina_research.monitoring (EventBus) or nt_tape during lumina_core bootstrap.

PRODUCED_BY = "continuity_meter.measure"
FAR_MAX = 0.10
TTD_FAST_MAX_DAYS = 15.0
TTD_SLOW_MAX_DAYS = 45.0
POWER_MIN = 0.85
MIN_BAR_DAYS = 0.5
OOS_BARS = 80
N_POWER_TRIALS = 8
FAST_SHIFT_SIGMA = 3.0
SLOW_SHIFT_SIGMA = 1.0
MIN_CLOSED_BARS = 241
TAPE_KIND_NT_PIT = "nt_pit"
S3_INSTRUMENTS: frozenset[str] = frozenset({"MES", "MNQ"})


class ContinuityMeterRefused(ValueError):
    """NT-PIT continuity cannot be measured without inventing a float."""


@dataclass(frozen=True, slots=True)
class ContinuityMeterReport:
    tape_kind: str
    instrument: str
    n_bars: int
    far: float
    ttd_fast_days: float
    ttd_slow_days: float
    power: float
    bar_sha256: str
    passed: bool
    reason: str
    produced_by: str


def fixture_closed_mes_daily_bars(
    *,
    n: int = MIN_CLOSED_BARS,
    start: datetime | None = None,
    now: datetime | None = None,
    root: str = "MES",
) -> tuple[dict[str, object], ...]:
    """Deterministic pre-pin daily MES/MNQ OHLC. One bar = one weekday. Not gauss."""
    del root
    if n < MIN_CLOSED_BARS:
        raise ContinuityMeterRefused("tape_too_short")
    first = start if start is not None else datetime(2025, 1, 2, 21, 0, tzinfo=timezone.utc)
    clock = now if now is not None else datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    if first.tzinfo is None or clock.tzinfo is None:
        raise ContinuityMeterRefused("timestamp_not_utc")
    rows: list[dict[str, object]] = []
    cursor = first
    while len(rows) < n:
        if cursor > clock:
            raise ContinuityMeterRefused("lookahead_future_bar")
        if cursor.weekday() < 5:
            close = 5000.0 + (10.0 if len(rows) % 2 == 0 else -10.0)
            opened = 5000.0 + (10.0 if (len(rows) + 1) % 2 == 0 else -10.0)
            high = max(opened, close) + 0.50
            low = min(opened, close) - 0.50
            rows.append(
                {
                    "timestamp": cursor,
                    "open": opened,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": 1000 + len(rows),
                    "bar_period": "1m",
                }
            )
        cursor = cursor + timedelta(days=1)
    return tuple(rows)


def measure_continuity(
    bars: Sequence[Any],
    *,
    instrument: str = "MES",
    config: Any | None = None,
) -> ContinuityMeterReport:
    """FAR/TTD/power from NT-PIT ClosedBar only. Fail-closed if the tape cannot support days."""
    from lumina_research.monitoring.config import packaged_config
    from lumina_research.validation.nt_tape import series_from_closed_bars

    root = str(instrument or "").strip().upper().split()[0] if str(instrument or "").strip() else ""
    if root not in S3_INSTRUMENTS:
        raise ContinuityMeterRefused("sim_instrument_not_yet_released")
    closed = _require_closed_bars(bars)
    bar_days = _median_bar_days(closed)
    if bar_days < MIN_BAR_DAYS:
        raise ContinuityMeterRefused("ttd_requires_daily_tape")
    digest = bar_sha256(closed)
    gross, _positions, _markets = series_from_closed_bars(closed)
    returns = tuple(float(item) for item in gross)
    if len(returns) < OOS_BARS + int(TTD_SLOW_MAX_DAYS) + 1:
        raise ContinuityMeterRefused("tape_too_short")
    cfg = config if config is not None else packaged_config()
    oos = returns[:OOS_BARS]
    if any(not math.isfinite(item) for item in oos):
        raise ContinuityMeterRefused("non_finite_return")
    far = _false_alarm_rate(returns, oos, cfg)
    sigma = float(statistics.pstdev(oos)) if len(oos) >= 2 else 0.0
    if sigma <= 0.0 or not math.isfinite(sigma):
        raise ContinuityMeterRefused("oos_zero_variance")
    fast_shift = FAST_SHIFT_SIGMA * sigma
    slow_shift = SLOW_SHIFT_SIGMA * sigma
    starts = _trial_starts(len(returns))
    fast_hits, ttd_fast = _horizon_power(returns, oos, cfg, starts, fast_shift, bar_days, TTD_FAST_MAX_DAYS)
    slow_hits, ttd_slow = _horizon_power(returns, oos, cfg, starts, slow_shift, bar_days, TTD_SLOW_MAX_DAYS)
    n_trials = len(starts)
    if n_trials < 1:
        raise ContinuityMeterRefused("power_unmeasured")
    power = float(fast_hits + slow_hits) / float(n_trials * 2)
    reason = _floor_reason(far, ttd_fast, ttd_slow, power)
    passed = reason == "ok"
    return ContinuityMeterReport(
        tape_kind=TAPE_KIND_NT_PIT,
        instrument=root,
        n_bars=len(closed),
        far=far,
        ttd_fast_days=ttd_fast,
        ttd_slow_days=ttd_slow,
        power=power,
        bar_sha256=digest,
        passed=passed,
        reason=reason,
        produced_by=PRODUCED_BY,
    )


def measure_fixture_daily(*, instrument: str = "MES") -> ContinuityMeterReport:
    from lumina_research.validation.nt_tape import closed_bars_from_rows

    now = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    rows = fixture_closed_mes_daily_bars(now=now, root=instrument)
    bars = closed_bars_from_rows(rows, now=now, purpose="gate")
    return measure_continuity(bars, instrument=instrument)


def bar_sha256(bars: Sequence[Any]) -> str:
    hasher = hashlib.sha256()
    for bar in bars:
        hasher.update(f"{bar.ts_ns}:{bar.close:.10f}|".encode("utf-8"))
    return hasher.hexdigest()


def _require_closed_bars(bars: Sequence[Any]) -> tuple[Any, ...]:
    from lumina_research.validation.nt_tape import ClosedBar

    if bars is None or isinstance(bars, (str, bytes)):
        raise ContinuityMeterRefused("bars_missing")
    out: list[Any] = []
    previous_ns = 0
    for item in bars:
        if type(item) is not ClosedBar:
            raise ContinuityMeterRefused("bar_not_closed")
        if previous_ns != 0 and item.ts_ns <= previous_ns:
            raise ContinuityMeterRefused("timestamps_not_increasing")
        previous_ns = item.ts_ns
        out.append(item)
    if len(out) < MIN_CLOSED_BARS:
        raise ContinuityMeterRefused("tape_too_short")
    return tuple(out)


def _median_bar_days(bars: Sequence[Any]) -> float:
    deltas: list[float] = []
    for index in range(1, len(bars)):
        seconds = (bars[index].timestamp - bars[index - 1].timestamp).total_seconds()
        if seconds <= 0.0:
            raise ContinuityMeterRefused("timestamps_not_increasing")
        deltas.append(seconds / 86400.0)
    if not deltas:
        raise ContinuityMeterRefused("tape_too_short")
    return float(statistics.median(deltas))


def _false_alarm_rate(returns: Sequence[float], oos: Sequence[float], config: Any) -> float:
    from lumina_research.monitoring.statistics import assess_decay

    window = int(config.window)
    alarms = 0
    ready = 0
    for end in range(OOS_BARS + window, len(returns) + 1):
        assessment = assess_decay(tuple(returns[:end]), oos, config)
        if assessment.ready is not True:
            continue
        ready += 1
        if str(assessment.stage) != "active":
            alarms += 1
    if ready < 1:
        raise ContinuityMeterRefused("far_unmeasured")
    return float(alarms) / float(ready)


def _trial_starts(n_returns: int) -> tuple[int, ...]:
    last = n_returns - int(TTD_SLOW_MAX_DAYS) - 1
    first = OOS_BARS + 10
    if last <= first:
        raise ContinuityMeterRefused("tape_too_short")
    step = max(1, (last - first) // max(1, N_POWER_TRIALS - 1))
    starts = tuple(first + index * step for index in range(N_POWER_TRIALS) if first + index * step <= last)
    if len(starts) < 1:
        raise ContinuityMeterRefused("power_unmeasured")
    return starts


def _horizon_power(
    returns: Sequence[float],
    oos: Sequence[float],
    config: Any,
    starts: Sequence[int],
    shift: float,
    bar_days: float,
    cap_days: float,
) -> tuple[int, float]:
    hits = 0
    detections: list[float] = []
    for plant_at in starts:
        days = _ttd_days(returns, oos, config, plant_at, shift, bar_days, cap_days)
        if days is None:
            continue
        detections.append(days)
        if days <= cap_days:
            hits += 1
    if not detections:
        return 0, cap_days + 1.0
    return hits, float(statistics.median(detections))


def _ttd_days(
    returns: Sequence[float],
    oos: Sequence[float],
    config: Any,
    plant_at: int,
    shift: float,
    bar_days: float,
    cap_days: float,
) -> float | None:
    planted = list(returns)
    for index in range(plant_at, len(planted)):
        planted[index] = float(planted[index]) - float(shift)
    max_end = min(len(planted), plant_at + int(cap_days / bar_days) + 2)
    from lumina_research.monitoring.statistics import assess_decay

    window = int(config.window)
    for end in range(plant_at + 1, max_end + 1):
        days = float(end - plant_at) * bar_days
        if days > cap_days:
            return None
        if end < window:
            continue
        assessment = assess_decay(tuple(planted[:end]), oos, config)
        if assessment.ready is not True:
            continue
        if str(assessment.stage) != "active":
            return days
    return None


def _floor_reason(far: float, ttd_fast: float, ttd_slow: float, power: float) -> str:
    if not math.isfinite(far) or far < 0.0:
        return "far_unmeasured"
    if far > FAR_MAX:
        return "far_above_floor"
    if not math.isfinite(ttd_fast) or ttd_fast <= 0.0:
        return "ttd_fast_unmeasured"
    if ttd_fast > TTD_FAST_MAX_DAYS:
        return "ttd_fast_above_floor"
    if not math.isfinite(ttd_slow) or ttd_slow <= 0.0:
        return "ttd_slow_unmeasured"
    if ttd_slow > TTD_SLOW_MAX_DAYS:
        return "ttd_slow_above_floor"
    if not math.isfinite(power) or power < 0.0:
        return "power_unmeasured"
    if power < POWER_MIN:
        return "power_below_floor"
    return "ok"


def daily_closed_bars(*, instrument: str = "MES") -> tuple[Any, ...]:
    from lumina_research.validation.nt_tape import TapeRefused, closed_bars_from_rows

    now = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    try:
        return closed_bars_from_rows(fixture_closed_mes_daily_bars(now=now, root=instrument), now=now, purpose="gate")
    except TapeRefused as exc:
        raise ContinuityMeterRefused(str(exc)) from exc
