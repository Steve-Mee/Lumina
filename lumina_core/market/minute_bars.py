"""Append-only closed 1-minute bars. One fixed-width file per root.

ADR-0056 §9. The lab searches this file, not a list of tick dicts.
A scheduled close does not append and does not delete. A second write of
the same timestamp must match. A mismatch fails closed.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from lumina_core.market.nt_fees import CostCardError, contract_root, spec_for

_RECORD = struct.Struct("<q4iI")
RECORD_BYTES = _RECORD.size  # 28


class BarArchiveError(ValueError):
    """The bar cannot be stored or the series cannot be read."""


@dataclass(frozen=True, slots=True)
class MinuteBar:
    ts_ns: int
    open_ticks: int
    high_ticks: int
    low_ticks: int
    close_ticks: int
    volume: int

    def price(self, tick_size: float) -> float:
        return float(self.close_ticks) * float(tick_size)


def archive_path(workspace_root: Path | str, symbol: str) -> Path:
    root = contract_root(symbol)
    return Path(workspace_root) / "reports" / "playground_bar_archive" / f"{root}.bars"


def append_minute(
    workspace_root: Path | str,
    symbol: str,
    *,
    ts_ns: int,
    open_px: float,
    high_px: float,
    low_px: float,
    close_px: float,
    volume: int,
    market_open: bool,
) -> MinuteBar:
    """Append one closed minute. A shut book appends nothing."""
    if not market_open:
        raise BarArchiveError("market_shut")
    spec = spec_for(symbol)
    bar = MinuteBar(
        ts_ns=_ts(ts_ns),
        open_ticks=_ticks(open_px, spec.tick_size),
        high_ticks=_ticks(high_px, spec.tick_size),
        low_ticks=_ticks(low_px, spec.tick_size),
        close_ticks=_ticks(close_px, spec.tick_size),
        volume=_volume(volume),
    )
    if bar.high_ticks < max(bar.open_ticks, bar.close_ticks, bar.low_ticks):
        raise BarArchiveError("high_below_price")
    if bar.low_ticks > min(bar.open_ticks, bar.close_ticks, bar.high_ticks):
        raise BarArchiveError("low_above_price")
    path = archive_path(workspace_root, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _find(path, bar.ts_ns)
    payload = _RECORD.pack(bar.ts_ns, bar.open_ticks, bar.high_ticks, bar.low_ticks, bar.close_ticks, bar.volume)
    if existing is not None:
        if existing != payload:
            raise BarArchiveError("timestamp_mismatch")
        return bar
    with path.open("ab") as handle:
        handle.write(payload)
        handle.flush()
    return bar


def repair_path(workspace_root: Path | str, symbol: str) -> Path:
    """Sidecar for minutes recovered after the live file was written. The live file stays append-only."""
    return archive_path(workspace_root, symbol).with_suffix(".repair.bars")


def load_minutes(workspace_root: Path | str, symbol: str) -> tuple[MinuteBar, ...]:
    """Read the live file plus any recovered minutes, in timestamp order. Does not drop a tail."""
    main = _read_records(archive_path(workspace_root, symbol), require_sorted=True)
    extra = _read_records(repair_path(workspace_root, symbol), require_sorted=False)
    if not extra:
        return main
    merged: dict[int, MinuteBar] = {bar.ts_ns: bar for bar in main}
    for bar in extra:
        previous = merged.get(bar.ts_ns)
        if previous is None:
            merged[bar.ts_ns] = bar
            continue
        if previous != bar:
            raise BarArchiveError("timestamp_mismatch")
    return tuple(merged[key] for key in sorted(merged))


def splice_missing(workspace_root: Path | str, symbol: str, bars: tuple[MinuteBar, ...]) -> tuple[int, int]:
    """Insert absent minutes into the repair sidecar. The live file is not opened for write.

    A timestamp already stored must match. A different price is refused and left out.
    Returns ``(added, refused)``.
    """
    main = _read_records(archive_path(workspace_root, symbol), require_sorted=True)
    path = repair_path(workspace_root, symbol)
    extra = list(_read_records(path, require_sorted=False))
    have: dict[int, MinuteBar] = {bar.ts_ns: bar for bar in main}
    for bar in extra:
        previous = have.get(bar.ts_ns)
        if previous is None:
            have[bar.ts_ns] = bar
            continue
        if previous != bar:
            raise BarArchiveError("timestamp_mismatch")
    added = 0
    refused = 0
    for bar in bars:
        previous = have.get(bar.ts_ns)
        if previous is None:
            have[bar.ts_ns] = bar
            extra.append(bar)
            added += 1
            continue
        if previous != bar:
            refused += 1
    if added == 0:
        return 0, refused
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = b"".join(
        _RECORD.pack(bar.ts_ns, bar.open_ticks, bar.high_ticks, bar.low_ticks, bar.close_ticks, bar.volume)
        for bar in extra
    )
    temporary = path.with_suffix(".repair.tmp")
    temporary.write_bytes(blob)
    temporary.replace(path)
    return added, refused


def stitch_front(workspace_root: Path | str, symbol: str, older: tuple[MinuteBar, ...]) -> int:
    """Put real older bars in front. An overlap that differs fails and leaves the file."""
    current = load_minutes(workspace_root, symbol)
    merged: dict[int, MinuteBar] = {bar.ts_ns: bar for bar in current}
    added = 0
    for bar in older:
        have = merged.get(bar.ts_ns)
        if have is None:
            merged[bar.ts_ns] = bar
            added += 1
            continue
        if have != bar:
            raise BarArchiveError("timestamp_mismatch")
    if added == 0:
        return 0
    ordered = tuple(merged[key] for key in sorted(merged))
    if len(ordered) != len(current) + added:
        raise BarArchiveError("row_lost")
    path = archive_path(workspace_root, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = b"".join(
        _RECORD.pack(bar.ts_ns, bar.open_ticks, bar.high_ticks, bar.low_ticks, bar.close_ticks, bar.volume)
        for bar in ordered
    )
    temporary = path.with_suffix(".bars.tmp")
    temporary.write_bytes(blob)
    temporary.replace(path)
    return added


def window(bars: tuple[MinuteBar, ...], *, start_ns: int, end_ns: int) -> tuple[MinuteBar, ...]:
    """Bars with start_ns <= ts < end_ns. Binary search on the sorted file."""
    if end_ns <= start_ns:
        return ()
    lo = _lower(bars, start_ns)
    hi = _lower(bars, end_ns)
    return bars[lo:hi]


def _read_records(path: Path, *, require_sorted: bool) -> tuple[MinuteBar, ...]:
    if not path.is_file():
        return ()
    blob = path.read_bytes()
    if len(blob) % RECORD_BYTES != 0:
        raise BarArchiveError("torn_record")
    out: list[MinuteBar] = []
    previous = -1
    for offset in range(0, len(blob), RECORD_BYTES):
        ts_ns, open_ticks, high_ticks, low_ticks, close_ticks, volume = _RECORD.unpack_from(blob, offset)
        if require_sorted and ts_ns <= previous:
            raise BarArchiveError("not_time_sorted")
        previous = int(ts_ns)
        out.append(
            MinuteBar(
                ts_ns=int(ts_ns),
                open_ticks=int(open_ticks),
                high_ticks=int(high_ticks),
                low_ticks=int(low_ticks),
                close_ticks=int(close_ticks),
                volume=int(volume),
            )
        )
    return tuple(out)


def _find(path: Path, ts_ns: int) -> bytes | None:
    if not path.is_file():
        return None
    blob = path.read_bytes()
    count = len(blob) // RECORD_BYTES
    lo = 0
    hi = count
    while lo < hi:
        mid = (lo + hi) // 2
        stored = _RECORD.unpack_from(blob, mid * RECORD_BYTES)[0]
        if stored < ts_ns:
            lo = mid + 1
        elif stored > ts_ns:
            hi = mid
        else:
            start = mid * RECORD_BYTES
            return blob[start : start + RECORD_BYTES]
    return None


def _lower(bars: tuple[MinuteBar, ...], ts_ns: int) -> int:
    lo = 0
    hi = len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].ts_ns < ts_ns:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _ts(value: int) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise BarArchiveError("timestamp_invalid") from exc
    if out <= 0:
        raise BarArchiveError("timestamp_invalid")
    return out


def _ticks(price: float, tick_size: float) -> int:
    try:
        px = float(price)
        size = float(tick_size)
    except (TypeError, ValueError) as exc:
        raise BarArchiveError("price_invalid") from exc
    if px <= 0.0 or size <= 0.0:
        raise BarArchiveError("price_invalid")
    ticks = px / size
    rounded = round(ticks)
    if abs(ticks - rounded) > 1e-6:
        raise BarArchiveError("price_off_tick")
    return int(rounded)


def _volume(value: int) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise BarArchiveError("volume_invalid") from exc
    if out < 0:
        raise BarArchiveError("volume_invalid")
    return out


def require_root(symbol: str) -> str:
    try:
        return contract_root(symbol)
    except CostCardError as exc:
        raise BarArchiveError(str(exc)) from exc
