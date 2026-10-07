"""Closed minutes from the counted Birth tick tape.

The lab searches this file, not the tick dict list. A minute with no tick is
not invented. The first cutoff is the first First Watch holdout bar: search
lies strictly before it, and that holdout is the locked tail.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.market.minute_bars import (
    MinuteBar,
    archive_path,
    stitch_front,
)
from lumina_core.market.nt_fees import spec_for

MINUTE_NS = 60 * 1_000_000_000


class BirthArchiveError(ValueError):
    """The tick tape cannot become an honest minute archive."""


def tick_timestamp_ns(row: dict[str, Any]) -> int | None:
    raw = row.get("timestamp") or row.get("ts") or row.get("ts_iso")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        value = int(raw)
        if value > 10**15:
            return value
        if value > 10**11:
            return value * 1_000_000
        if value > 10**8:
            return value * 1_000_000_000
        return None
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return int(parsed.astimezone(timezone.utc).timestamp() * 1_000_000_000)


def _price(row: dict[str, Any]) -> float | None:
    for key in ("last", "close", "price"):
        raw = row.get(key)
        if isinstance(raw, bool) or raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0.0:
            return value
    return None


def _on_grid(price: float, tick_size: float) -> int | None:
    ticks = float(price) / float(tick_size)
    rounded = round(ticks)
    if abs(ticks - rounded) > 1e-4:
        return None
    if rounded <= 0:
        return None
    return int(rounded)


def minutes_from_ticks(ticks: list[dict[str, Any]], *, symbol: str) -> tuple[MinuteBar, ...]:
    """One bar per minute that actually printed. Silent minutes stay absent."""
    spec = spec_for(symbol)
    buckets: dict[int, list[tuple[int, int]]] = {}
    for row in ticks:
        if not isinstance(row, dict):
            continue
        ts_ns = tick_timestamp_ns(row)
        price = _price(row)
        if ts_ns is None or price is None:
            continue
        grid = _on_grid(price, spec.tick_size)
        if grid is None:
            continue
        try:
            volume = int(row.get("volume") or 0)
        except (TypeError, ValueError):
            volume = 0
        if volume < 0:
            continue
        minute = ts_ns - (ts_ns % MINUTE_NS)
        buckets.setdefault(minute, []).append((grid, volume))
    bars: list[MinuteBar] = []
    for minute in sorted(buckets):
        prints = buckets[minute]
        prices = [item[0] for item in prints]
        bars.append(
            MinuteBar(
                ts_ns=minute,
                open_ticks=prices[0],
                high_ticks=max(prices),
                low_ticks=min(prices),
                close_ticks=prices[-1],
                volume=sum(item[1] for item in prints),
            )
        )
    return tuple(bars)


def split_search_and_tail(
    bars: tuple[MinuteBar, ...],
    *,
    holdout_start_ns: int,
) -> tuple[tuple[MinuteBar, ...], tuple[MinuteBar, ...]]:
    """Search is strictly before the holdout. The holdout is the locked tail."""
    start = int(holdout_start_ns)
    search = tuple(bar for bar in bars if bar.ts_ns < start)
    tail = tuple(bar for bar in bars if bar.ts_ns >= start)
    return search, tail


def stream_birth_cache(workspace_root: Path | str) -> dict[str, int]:
    """Build the minute archive from the saved Birth tick file. Does not load it all at once."""
    from lumina_core.birth.tick_cache_persist import (
        cache_manifest_path,
        split_cache_path,
        ticks_cache_path,
    )
    from lumina_core.market.minute_bars import _RECORD

    root = Path(workspace_root)
    ticks_path = ticks_cache_path(root)
    if not ticks_path.is_file():
        raise BirthArchiveError("ticks_missing")
    split_path = split_cache_path(root)
    if not split_path.is_file():
        raise BirthArchiveError("split_missing")
    split = json.loads(split_path.read_text(encoding="utf-8"))
    indices = split.get("holdout_indices") if isinstance(split, dict) else None
    if not isinstance(indices, list) or not indices:
        raise BirthArchiveError("holdout_index_missing")
    holdout_index = int(indices[0])
    manifest_path = cache_manifest_path(root)
    manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    root_symbol = _archive_root(manifest_raw if isinstance(manifest_raw, dict) else {})
    spec = spec_for(root_symbol)
    destination = archive_path(root, root_symbol)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".bars.building")
    counted = 0
    minutes = 0
    holdout_start_ns: int | None = None
    current_minute: int | None = None
    bucket: list[tuple[int, int]] | None = None
    last_minute = -1
    with ticks_path.open("r", encoding="utf-8") as source, temporary.open("wb") as sink:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            if counted == holdout_index:
                holdout_start_ns = tick_timestamp_ns(row)
            counted += 1
            ts_ns = tick_timestamp_ns(row)
            price = _price(row)
            if ts_ns is None or price is None:
                continue
            grid = _on_grid(price, spec.tick_size)
            if grid is None:
                continue
            try:
                volume = int(row.get("volume") or 0)
            except (TypeError, ValueError):
                volume = 0
            if volume < 0:
                continue
            minute = ts_ns - (ts_ns % MINUTE_NS)
            if minute < last_minute:
                temporary.unlink(missing_ok=True)
                raise BirthArchiveError("ticks_not_time_sorted")
            if current_minute is None:
                current_minute = minute
                bucket = [(grid, volume)]
            elif minute != current_minute:
                _write_bucket(sink, _RECORD, int(current_minute), bucket or [])
                minutes += 1
                last_minute = int(current_minute)
                current_minute = minute
                bucket = [(grid, volume)]
            else:
                bucket.append((grid, volume))
        if current_minute is not None and bucket:
            _write_bucket(sink, _RECORD, int(current_minute), bucket)
            minutes += 1
            last_minute = int(current_minute)
    if holdout_start_ns is None:
        temporary.unlink(missing_ok=True)
        raise BirthArchiveError("holdout_tick_missing")
    temporary.replace(destination)
    from lumina_core.maturity.playground.learning_book import record_archive_fact

    tail_end = last_minute + MINUTE_NS
    record_archive_fact(
        root,
        tape_count=counted,
        minute_count=minutes,
        holdout_start_ns=int(holdout_start_ns) - (int(holdout_start_ns) % MINUTE_NS),
        tail_end_ns=tail_end,
        symbol=root_symbol,
    )
    manifest = cache_manifest_path(root)
    seed = 1
    if manifest.is_file():
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        token = str(raw.get("raw_ticks_hash") or "1")[:8]
        seed = int(token, 16) if token else 1
    return {
        "tape_count": counted,
        "minute_count": minutes,
        "holdout_start_ns": int(holdout_start_ns) - (int(holdout_start_ns) % MINUTE_NS),
        "tail_end_ns": tail_end,
        "seed": seed,
    }


def _write_bucket(sink: Any, record: Any, minute: int, bucket: list[tuple[int, int]]) -> None:
    prices = [item[0] for item in bucket]
    payload = record.pack(
        minute,
        prices[0],
        max(prices),
        min(prices),
        prices[-1],
        sum(item[1] for item in bucket),
    )
    sink.write(payload)


def _archive_root(manifest: dict[str, Any]) -> str:
    """The tape's own root. A missing instrument is not guessed."""
    from lumina_core.market.nt_fees import CostCardError, contract_root

    instruments = manifest.get("instruments")
    if isinstance(instruments, list):
        for item in instruments:
            try:
                return contract_root(str(item))
            except CostCardError:
                continue
    raise BirthArchiveError("symbol_missing")


def ensure_school_from_birth(workspace_root: Path | str) -> dict[str, Any]:
    """Turn the saved Birth tape into the school archive and seal the first period."""
    from lumina_core.birth.tick_cache_persist import cache_manifest_path
    from lumina_core.maturity.playground.learning_book import read_header
    from lumina_core.maturity.playground.progress import load_playground_progress, merge_playground_progress
    from lumina_core.maturity.playground.research_kit import write_period

    root = Path(workspace_root)
    header = read_header(root)
    symbol = str(header.get("symbol") or "")
    if not symbol:
        manifest_path = cache_manifest_path(root)
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
            symbol = _archive_root(raw if isinstance(raw, dict) else {})
        except (OSError, json.JSONDecodeError, BirthArchiveError):
            return {"ok": False, "reason": "symbol_missing"}
    archive = archive_path(root, symbol)
    if not archive.is_file() or int(header.get("minute_count") or 0) <= 0:
        try:
            built = stream_birth_cache(root)
        except BirthArchiveError as exc:
            return {"ok": False, "reason": str(exc)}
        header = read_header(root)
    else:
        built = {
            "tape_count": int(header.get("tape_count") or 0),
            "minute_count": int(header.get("minute_count") or 0),
            "holdout_start_ns": int(header.get("holdout_start_ns") or 0),
            "tail_end_ns": int(header.get("tail_end_ns") or 0),
            "seed": _seed_from_manifest(root),
        }
    if not header.get("periods"):
        now = datetime.now(timezone.utc)
        write_period(
            root,
            period_id="birth-holdout",
            budget=1,
            seed=int(built.get("seed") or 1),
            cutoff_ns=int(header["tail_end_ns"]),
            tape_count=int(header["tape_count"]),
            tail_start_ns=int(header["holdout_start_ns"]),
            tail_end_ns=int(header["tail_end_ns"]),
            now=now,
        )
    from lumina_core.order_gatekeeper.contract_symbols import live_listing

    progress = load_playground_progress(root)
    listing = str(progress.get("chart_listing") or "")
    rolled = live_listing(listing or symbol)
    if rolled and rolled != listing:
        merge_playground_progress(root, {"chart_listing": rolled})
    return {"ok": True, "reason": "ready", "minute_count": int(header.get("minute_count") or built["minute_count"])}


def _seed_from_manifest(workspace_root: Path) -> int:
    from lumina_core.birth.tick_cache_persist import cache_manifest_path

    path = cache_manifest_path(workspace_root)
    if not path.is_file():
        return 1
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1
    token = str(raw.get("raw_ticks_hash") or "")[:8]
    if not token:
        return 1
    try:
        return int(token, 16)
    except ValueError:
        return 1


def write_birth_minutes(
    workspace_root: Path | str,
    ticks: list[dict[str, Any]],
    *,
    symbol: str,
    holdout_start_ns: int,
) -> dict[str, int]:
    """Count the ticks, write the minutes, and record the cutoff. No search starts."""
    from lumina_core.maturity.playground.learning_book import record_archive_fact

    counted = sum(1 for row in ticks if isinstance(row, dict))
    bars = minutes_from_ticks(ticks, symbol=symbol)
    if bars and int(holdout_start_ns) <= bars[0].ts_ns:
        raise BirthArchiveError("holdout_not_after_search")
    search, tail = split_search_and_tail(bars, holdout_start_ns=int(holdout_start_ns))
    if bars:
        stitch_front(workspace_root, symbol, bars)
    tail_end = tail[-1].ts_ns + MINUTE_NS if tail else int(holdout_start_ns)
    record_archive_fact(
        workspace_root,
        tape_count=counted,
        minute_count=len(bars),
        holdout_start_ns=int(holdout_start_ns),
        tail_end_ns=tail_end,
        symbol=symbol,
    )
    return {
        "tape_count": counted,
        "minute_count": len(bars),
        "search_minutes": len(search),
        "tail_minutes": len(tail),
        "holdout_start_ns": int(holdout_start_ns),
        "tail_end_ns": tail_end,
        "archive_bytes": archive_path(workspace_root, symbol).stat().st_size if bars else 0,
    }
