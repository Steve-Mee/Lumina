"""Read-only PIT NT closed-bar tape for the Validation Gate (S2.5 / D2).

Forming bars, look-ahead, vendor-CSV substitutes, and synthetic gauss tapes
are refused. Survivors cannot be stamped ``nt_pit`` unless this adapter built
the series.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar, cast

from lumina_core.agent_orchestration.schemas_research import HypothesisProposed
from lumina_core.engine.market_data_manager import MarketDataManager
from lumina_core.engine.nt_bar_ssot import BarRejected, is_forming_bar, validate_nt_bar
from lumina_core.engine.ohlc_clock import utc_from_any
from lumina_research.cycles.holdout import (
    HOLDOUT_PIN_UTC,
    LOCKED_PURPOSES,
    HoldoutLocked,
    assert_holdout_pin_closed,
    holdout_pin_is_closed,
)
from lumina_research.validation.cost_model import MarketSnapshot

Tape = tuple[tuple[float, ...], tuple[float, ...], tuple[MarketSnapshot, ...]]
TAPE_KIND_NT_PIT = "nt_pit"
TAPE_KIND_SYNTHETIC = "synthetic"
MIN_CLOSED_BARS = 241


class TapeRefused(ValueError):
    """NT-PIT tape cannot be built without look-ahead, forming bars, or a substitute."""


@dataclass(frozen=True, slots=True)
class ClosedBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    ts_ns: int


def _as_utc(value: object) -> datetime:
    parsed = utc_from_any(value)
    if not isinstance(parsed, datetime):
        raise TapeRefused("timestamp_missing")
    return parsed


def _as_row_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TapeRefused("bar_not_mapping")
    typed = cast(dict[object, object], value)
    return {str(key): item for key, item in typed.items()}


def _as_object_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TapeRefused("closed_book_empty")
    return list(cast(list[object], value))


def _require_float(row: Mapping[str, object], key: str) -> float:
    raw = row.get(key)
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise TapeRefused(f"bar_field_invalid:{key}")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise TapeRefused(f"bar_field_invalid:{key}") from exc
    if not math.isfinite(value):
        raise TapeRefused(f"bar_field_invalid:{key}")
    return value


def _closed_from_validated(row: Mapping[str, object], *, now: datetime, purpose: str) -> ClosedBar:
    ts = _as_utc(row["timestamp"])
    if is_forming_bar(ts, now):
        raise TapeRefused("forming_bar_refused")
    if ts > now:
        raise TapeRefused("lookahead_future_bar")
    ts_ns = int(ts.timestamp() * 1_000_000_000)
    try:
        assert_holdout_pin_closed(ts_ns=ts_ns, purpose=purpose)
    except HoldoutLocked as exc:
        raise TapeRefused("holdout_pin_closed") from exc
    return ClosedBar(
        timestamp=ts,
        open=_require_float(row, "open"),
        high=_require_float(row, "high"),
        low=_require_float(row, "low"),
        close=_require_float(row, "close"),
        volume=_require_float(row, "volume"),
        ts_ns=ts_ns,
    )


def closed_bars_from_rows(
    rows: Sequence[object] | None,
    *,
    now: datetime,
    purpose: str = "gate",
) -> tuple[ClosedBar, ...]:
    """Validate NT Last OHLC. Forming, look-ahead, and the holdout pin refuse."""
    if holdout_pin_is_closed() is not True:
        raise TapeRefused("holdout_pin_open")
    if rows is None or isinstance(rows, (str, bytes)):
        raise TapeRefused("bars_missing")
    now_utc = _as_utc(now)
    if purpose.strip().lower() not in LOCKED_PURPOSES and purpose.strip().lower() not in {
        "evaluation",
        "holdout_eval",
        "survivor",
    }:
        raise TapeRefused("unknown_tape_purpose")
    key = purpose.strip().lower()
    pin_purpose = "evaluation" if key in {"evaluation", "holdout_eval"} else "gate"
    out: list[ClosedBar] = []
    previous_ns = 0
    for raw in rows:
        typed_row = _as_row_dict(raw)
        try:
            validated = validate_nt_bar(typed_row)
        except BarRejected as exc:
            raise TapeRefused(str(exc.code)) from exc
        bar = _closed_from_validated(_as_row_dict(validated), now=now_utc, purpose=pin_purpose)
        if previous_ns != 0 and bar.ts_ns <= previous_ns:
            raise TapeRefused("timestamps_not_increasing")
        previous_ns = bar.ts_ns
        out.append(bar)
    if len(out) < MIN_CLOSED_BARS:
        raise TapeRefused("tape_too_short")
    return tuple(out)


def closed_bars_from_frame(rows: object, *, now: datetime, purpose: str = "gate") -> tuple[ClosedBar, ...]:
    """Closed book only. Forming bars in the frame are refused, never evaluated."""
    if rows is None or isinstance(rows, (str, bytes)):
        raise TapeRefused("closed_book_empty")
    if getattr(rows, "empty", False) is True:
        raise TapeRefused("closed_book_empty")
    to_dict = getattr(rows, "to_dict", None)
    if not callable(to_dict):
        raise TapeRefused("closed_book_empty")
    raw_records = to_dict("records")
    return closed_bars_from_rows(_as_object_list(raw_records), now=now, purpose=purpose)


def closed_bars_from_manager(
    manager: MarketDataManager,
    *,
    now: datetime,
    purpose: str = "gate",
) -> tuple[ClosedBar, ...]:
    frame = getattr(manager, "ohlc_1min", None)
    return closed_bars_from_frame(frame, now=now, purpose=purpose)


def series_from_closed_bars(bars: Sequence[ClosedBar]) -> Tape:
    """Close-to-close returns at t use only bars ≤ t. Never shift −1 / t+1."""
    if len(bars) < 2:
        raise TapeRefused("tape_too_short")
    gross: list[float] = []
    positions: list[float] = []
    markets: list[MarketSnapshot] = []
    for index in range(1, len(bars)):
        prev = bars[index - 1]
        cur = bars[index]
        if cur.ts_ns <= prev.ts_ns:
            raise TapeRefused("lookahead_shuffled")
        if prev.close <= 0.0:
            raise TapeRefused("non_positive_close")
        gross.append((cur.close - prev.close) / prev.close)
        positions.append(1.0)
        vol = cur.volume if cur.volume > 0.0 else 1.0
        markets.append(MarketSnapshot(volume=vol, average_volume=vol, volatility_price=max(cur.high - cur.low, 1e-6)))
    return tuple(gross), tuple(positions), tuple(markets)


def refuse_synthetic_as_nt_pit(tape_kind: object) -> None:
    kind = str(tape_kind or "").strip().lower()
    if kind == TAPE_KIND_SYNTHETIC:
        raise TapeRefused("synthetic_cannot_be_nt_pit")
    if kind != TAPE_KIND_NT_PIT:
        raise TapeRefused("survivors_not_nt_pit")


def refuse_vendor_csv_substitute(path: object) -> None:
    text = str(path or "").strip().lower()
    if not text:
        return
    banned = ("yahoo", "stooq", "polygon", "databento", "kaggle", "planted_edge", "gauss")
    if any(token in text for token in banned):
        raise TapeRefused("vendor_csv_substitute_forbidden")


class NtTapeMaterializer:
    """Callable ValidationAgent materializer. ``tape_kind`` is ``nt_pit`` only here."""

    tape_kind: ClassVar[str] = TAPE_KIND_NT_PIT
    _bars: tuple[ClosedBar, ...]

    def __init__(self, bars: Sequence[ClosedBar]) -> None:
        if type(self) is not NtTapeMaterializer:
            raise TapeRefused("nt_tape_subclass_forbidden")
        if len(bars) < MIN_CLOSED_BARS:
            raise TapeRefused("tape_too_short")
        self._bars = tuple(bars)

    def __call__(self, hypothesis: HypothesisProposed) -> Tape:
        del hypothesis
        refuse_synthetic_as_nt_pit(self.tape_kind)
        return series_from_closed_bars(self._bars)


def materializer_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    now: datetime,
    purpose: str = "gate",
    source_path: object = "",
) -> NtTapeMaterializer:
    refuse_vendor_csv_substitute(source_path)
    return NtTapeMaterializer(closed_bars_from_rows(rows, now=now, purpose=purpose))


def fixture_closed_mes_bars(
    *,
    n: int = MIN_CLOSED_BARS,
    start: datetime | None = None,
    now: datetime | None = None,
    root: str = "MES",
) -> tuple[dict[str, object], ...]:
    """Deterministic pre-pin NT-shaped MES/MNQ OHLC for tests. Not gauss."""
    del root
    if n < MIN_CLOSED_BARS:
        raise TapeRefused("tape_too_short")
    first = start if start is not None else datetime(2025, 1, 2, 14, 31, tzinfo=timezone.utc)
    clock = now if now is not None else datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    if first >= HOLDOUT_PIN_UTC:
        raise TapeRefused("holdout_pin_closed")
    rows: list[dict[str, object]] = []
    price = 5000.0
    for index in range(n):
        ts = datetime.fromtimestamp(first.timestamp() + float(index) * 60.0, tz=timezone.utc)
        if ts > clock:
            raise TapeRefused("lookahead_future_bar")
        high = price + 0.50
        low = price - 0.50
        close = price + (0.25 if index % 17 else -0.25)
        rows.append(
            {
                "timestamp": ts,
                "open": price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000 + index,
                "bar_period": "1m",
            }
        )
        price = close
    return tuple(rows)

