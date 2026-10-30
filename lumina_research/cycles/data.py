"""Discover real futures bars. Synthetic tapes are refused for P2 empirical cycles."""

from __future__ import annotations

import csv
import json
import os
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from lumina_research.agents.objects import as_object_dict, as_object_list
from lumina_research.validation.contracts import spec_for

_RECORD = struct.Struct("<q4iI")
MIN_BARS = 241
SEARCH_BAR_SIZES: tuple[str, ...] = ("1m", "5m", "1d")
INSTRUMENTS: tuple[str, ...] = ("ES", "NQ", "MES", "MNQ")
ENV_DATA_DIR = "LUMINA_RESEARCH_DATA_DIR"


class DataRefused(ValueError):
    """Real market data is missing, malformed, or too short for the Validation Gate."""


@dataclass(frozen=True, slots=True)
class ResearchBar:
    ts_ns: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class LoadedTape:
    instrument: str
    bar_size: str
    path: Path
    bars: tuple[ResearchBar, ...]
    holdout_start_ns: int | None = None


@dataclass(frozen=True, slots=True)
class DataStatus:
    usable: bool
    tapes: tuple[LoadedTape, ...]
    searched: tuple[str, ...]
    missing: tuple[str, ...]
    required: Mapping[str, str]


def discover_data(*, repo_root: Path, data_dir: Path | None = None) -> DataStatus:
    """Load real bars only. Never invent a tape."""
    roots = _search_roots(repo_root, data_dir)
    tapes: list[LoadedTape] = []
    missing: list[str] = []
    searched = tuple(str(path) for path in roots)
    for instrument in INSTRUMENTS:
        loaded = _load_instrument(instrument, roots)
        if loaded is None:
            missing.append(instrument)
        else:
            tapes.append(loaded)
    usable = any(len(item.bars) >= MIN_BARS for item in tapes)
    required = {
        "instruments": "P2 first cycle: MES and MNQ 1m; ES/NQ accepted later",
        "bar_size": "NT8 1-minute bars first; 5m or 1d accepted only as a documented fallback",
        "period": "recent 2-3 years; train split must still have >= 241 bars after the holdout lock",
        "holdout": (
            "last 9 calendar months (allowed 6-12); P2 NT8 tapes pin 2026-01-28T23:00:00Z "
            "(legacy 2026-01-29T00:00:00Z recorded, holdout unopened); "
            "access_bars(purpose=selection|tuning|calibration|gate) fails closed on holdout timestamps"
        ),
        "format": "UTF-8 CSV header timestamp,open,high,low,close,volume (UTC ISO-8601 with offset)",
        "paths": (
            f"${ENV_DATA_DIR}/{{MES,MNQ}}/1m/nt8_{{mes,mnq}}_1m.csv ; "
            "data/research/{MES,MNQ}/1m/*.csv ; "
            "optional data/research/VIX/1d/vix.csv for regime labels"
        ),
        "code": "lumina_research.cycles.data.discover_data + lumina_research.cycles.holdout.access_bars",
    }
    return DataStatus(usable=usable, tapes=tuple(tapes), searched=searched, missing=tuple(missing), required=required)


def read_csv_bars(path: Path) -> tuple[ResearchBar, ...]:
    return _read_csv(path)


def tape_for(status: DataStatus, instrument: str) -> LoadedTape:
    for item in status.tapes:
        if item.instrument == instrument and len(item.bars) >= MIN_BARS:
            return item
    if status.tapes:
        longest = max(status.tapes, key=lambda row: len(row.bars))
        if len(longest.bars) >= MIN_BARS:
            return longest
    raise DataRefused(f"no usable real tape for {instrument!r}")


def _search_roots(repo_root: Path, data_dir: Path | None) -> tuple[Path, ...]:
    rows: list[Path] = []
    if data_dir is not None:
        rows.append(data_dir)
    env = os.environ.get(ENV_DATA_DIR, "").strip()
    if env:
        rows.append(Path(env))
    rows.append(repo_root / "data" / "research")
    rows.append(repo_root / "reports" / "playground_bar_archive")
    unique: list[Path] = []
    seen: set[str] = set()
    for path in rows:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return tuple(unique)


def _load_instrument(instrument: str, roots: tuple[Path, ...]) -> LoadedTape | None:
    spec = spec_for(instrument)
    for root in roots:
        binary = root / f"{spec.root}.bars"
        if binary.is_file():
            bars = _read_binary(binary, spec.tick_size)
            if len(bars) >= MIN_BARS:
                return LoadedTape(instrument=spec.root, bar_size="1m", path=binary, bars=bars)
        for size in SEARCH_BAR_SIZES:
            folder = root / spec.root / size
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*")):
                if path.suffix.lower() == ".csv":
                    bars = _read_csv(path)
                elif path.suffix.lower() in {".jsonl", ".json"}:
                    bars = _read_jsonl(path)
                else:
                    continue
                if len(bars) >= MIN_BARS:
                    return LoadedTape(instrument=spec.root, bar_size=size, path=path, bars=bars)
    return None


def _read_csv(path: Path) -> tuple[ResearchBar, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [_bar_from_mapping(row) for row in reader]
    return tuple(item for item in rows if item is not None)


def _read_jsonl(path: Path) -> tuple[ResearchBar, ...]:
    rows: list[ResearchBar] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            loaded: object = json.loads(line)
        except json.JSONDecodeError:
            continue
        mapping = as_object_dict(loaded)
        if mapping is None:
            continue
        bar = _bar_from_mapping(mapping)
        if bar is not None:
            rows.append(bar)
    if not rows and path.suffix.lower() == ".json":
        try:
            loaded_file: object = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ()
        file_items = as_object_list(loaded_file)
        if file_items is not None:
            for item in file_items:
                mapping = as_object_dict(item)
                if mapping is None:
                    continue
                bar = _bar_from_mapping(mapping)
                if bar is not None:
                    rows.append(bar)
    return tuple(rows)


def _read_binary(path: Path, tick_size: float) -> tuple[ResearchBar, ...]:
    payload = path.read_bytes()
    if len(payload) % _RECORD.size != 0:
        raise DataRefused(f"corrupt bar archive {path}")
    bars: list[ResearchBar] = []
    for offset in range(0, len(payload), _RECORD.size):
        ts_ns, open_t, high_t, low_t, close_t, volume = _RECORD.unpack_from(payload, offset)
        bars.append(
            ResearchBar(
                ts_ns=int(ts_ns),
                open=float(open_t) * tick_size,
                high=float(high_t) * tick_size,
                low=float(low_t) * tick_size,
                close=float(close_t) * tick_size,
                volume=float(volume),
            )
        )
    return tuple(bars)


def _bar_from_mapping(row: Mapping[str, object]) -> ResearchBar | None:
    try:
        ts_raw = row.get("timestamp", row.get("ts_ns", row.get("time")))
        open_px = _as_float(row.get("open"))
        high_px = _as_float(row.get("high"))
        low_px = _as_float(row.get("low"))
        close_px = _as_float(row.get("close"))
        volume = _as_float(row.get("volume", 0.0))
    except (KeyError, TypeError, ValueError):
        return None
    if open_px is None or high_px is None or low_px is None or close_px is None or volume is None:
        return None
    ts_ns = _timestamp_ns(ts_raw)
    if ts_ns is None:
        return None
    if high_px < max(open_px, close_px, low_px) or low_px > min(open_px, close_px, high_px):
        return None
    return ResearchBar(ts_ns=ts_ns, open=open_px, high=high_px, low=low_px, close=close_px, volume=volume)


def _timestamp_ns(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 10**15 else value * 1_000_000_000
    if isinstance(value, float):
        return int(value * 1_000_000_000)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            pass
        stamp = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(stamp)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return int(parsed.timestamp() * 1_000_000_000)
    return None


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
