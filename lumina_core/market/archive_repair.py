"""Fill an open-hour hole in the minute archive from real NinjaTrader bars.

The live bar file is never rewritten. Recovered minutes land in a sidecar and
are merged on read. A scheduled Globex close is not a hole. A source that has
no print does not become a bar; a scored sentence is left as it is.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.market.globex_hours import globex_status
from lumina_core.market.minute_bars import (
    BarArchiveError,
    MinuteBar,
    archive_path,
    load_minutes,
    splice_missing,
)
from lumina_core.market.nt_fees import CostCardError, contract_root, spec_for
from lumina_core.order_gatekeeper.contract_symbols import front_month_symbol
from lumina_core.maturity.playground.sentence_window import MINUTE_NS

logger = get_logger("lumina.market.archive_repair")

_REAL_NS = 10**17
_NIBBLE = 180
_WAIT_SEC = 3600
Fetcher = Callable[[int, int], list[MinuteBar] | None]


def unresolved_open_holes(workspace_root: Path | str, bars: tuple[MinuteBar, ...]) -> bool:
    """True when an open gap has not yet been answered by the source.

    A source that reported no print is settled. An unasked gap is not a score.
    """
    holes = open_holes(bars)
    if not holes:
        return False
    spans = _empty_spans(Path(workspace_root))
    for start_ns, end_ns in holes:
        cursor = start_ns
        while cursor < end_ns:
            nxt = 0
            for span_start, span_end in spans:
                if span_start <= cursor < span_end:
                    nxt = span_end
                    break
            if nxt <= cursor:
                return True
            cursor = nxt
    return False


def _empty_spans(root: Path) -> list[tuple[int, int]]:
    path = root / "reports" / "playground_tick_repair" / "repairs.jsonl"
    if not path.is_file():
        return []
    spans: list[tuple[int, int]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("reason") != "source_empty":
            continue
        try:
            start_ns = int(row["start_ns"])
            end_ns = int(row["end_ns"])
        except (KeyError, TypeError, ValueError):
            continue
        if end_ns > start_ns:
            spans.append((start_ns, end_ns))
    return spans


def open_holes(bars: tuple[MinuteBar, ...]) -> list[tuple[int, int]]:
    """Open minutes missing between stored bars. A halt or weekend is not a hole.

    A bar on the 17:00 close and the next bar at 18:01 leaves only 18:00 open.
    The halt itself is not asked of NinjaTrader and does not block a score.
    """
    found: list[tuple[int, int]] = []
    for earlier, later in zip(bars, bars[1:], strict=False):
        if int(earlier.ts_ns) < _REAL_NS or int(later.ts_ns) < _REAL_NS:
            continue
        if int(later.ts_ns) - int(earlier.ts_ns) <= MINUTE_NS:
            continue
        found.extend(_open_runs(int(earlier.ts_ns), int(later.ts_ns)))
    return found


def live_open_holes(bars: tuple[MinuteBar, ...], now: datetime) -> list[tuple[int, int]]:
    """Open minutes after the last stored bar, up to the last closed minute."""
    if not bars or now.tzinfo is None:
        return []
    last = int(bars[-1].ts_ns)
    if last < _REAL_NS:
        return []
    end_ns = int(now.timestamp() * 1_000_000_000)
    end_ns -= end_ns % MINUTE_NS
    if end_ns <= last + MINUTE_NS:
        return []
    return _open_runs(last, end_ns)


def hole_fingerprint(bars: tuple[MinuteBar, ...]) -> str:
    """Changes when an open hole appears or disappears. Empty when the slice is whole."""
    holes = open_holes(bars)
    if not holes:
        return ""
    return f"{len(holes)}:{holes[0][0]}:{holes[-1][1]}"


def _open_runs(start_ns: int, end_ns: int) -> list[tuple[int, int]]:
    """Contiguous open minutes in (start_ns, end_ns). Closed minutes are skipped."""
    runs: list[tuple[int, int]] = []
    run_start: int | None = None
    cursor = int(start_ns) + MINUTE_NS
    limit = int(start_ns) + 8 * 24 * 60 * MINUTE_NS
    while cursor < int(end_ns):
        if cursor > limit:
            break
        moment = datetime.fromtimestamp(cursor / 1_000_000_000, tz=timezone.utc)
        try:
            status = globex_status(moment)
        except ValueError:
            break
        if status == "open":
            if run_start is None:
                run_start = cursor
        elif run_start is not None:
            runs.append((run_start, cursor))
            run_start = None
        cursor += MINUTE_NS
    if run_start is not None:
        runs.append((run_start, min(cursor, int(end_ns))))
    return runs


def _next_ask(
    holes: list[tuple[int, int]],
    root: Path,
    clock: float,
) -> tuple[int, int] | None:
    """The next slice that is not in backoff. A failed slice does not block the one after it."""
    for start_ns, end_ns in holes:
        cursor = int(start_ns)
        while cursor < int(end_ns):
            ask_end = min(int(end_ns), cursor + _NIBBLE * MINUTE_NS)
            if not _waiting(root, cursor, ask_end, clock):
                return cursor, ask_end
            cursor = ask_end
    return None


def repair_next_hole(
    workspace_root: Path | str,
    *,
    symbol: str = "",
    fetcher: Fetcher | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Repair the earliest open hole, at most three hours of it. One call, no book rewrite."""
    root = Path(workspace_root)
    root_symbol = symbol or _archive_symbol(root)
    if not root_symbol:
        return {"ok": False, "reason": "symbol_missing", "added": 0}
    symbol = root_symbol
    if not archive_path(root, symbol).is_file():
        return {"ok": True, "reason": "no_archive", "added": 0}
    try:
        bars = load_minutes(root, symbol)
    except BarArchiveError as exc:
        return {"ok": False, "reason": str(exc), "added": 0}
    clock = time.time() if now is None else float(now)
    moment = datetime.fromtimestamp(clock, tz=timezone.utc)
    holes = live_open_holes(bars, moment) + open_holes(bars)
    asked = _next_ask(holes, root, clock)
    if asked is None:
        if holes:
            return {"ok": True, "reason": "waiting", "added": 0}
        return {"ok": True, "reason": "no_hole", "added": 0}
    start_ns, ask_end = asked
    ask = fetcher if fetcher is not None else _nt_fetcher(symbol)
    try:
        fetched = ask(start_ns, ask_end)
    except Exception:
        logger.warning("archive_repair.fetch_failed", exc_info=True)
        fetched = None
    if fetched is None:
        _remember(root, start_ns, ask_end, clock)
        _journal(root, {"reason": "nt_unreachable", "start_ns": start_ns, "end_ns": ask_end, "added": 0})
        return {"ok": True, "reason": "nt_unreachable", "added": 0, "start_ns": start_ns, "end_ns": ask_end}
    accepted = _accepted(fetched, start_ns, ask_end)
    if not accepted:
        _remember(root, start_ns, ask_end, clock)
        _journal(root, {"reason": "source_empty", "start_ns": start_ns, "end_ns": ask_end, "added": 0})
        return {"ok": True, "reason": "source_empty", "added": 0, "start_ns": start_ns, "end_ns": ask_end}
    try:
        added, refused = splice_missing(root, symbol, tuple(accepted))
    except BarArchiveError as exc:
        _journal(root, {"reason": str(exc), "start_ns": start_ns, "end_ns": ask_end, "added": 0})
        return {"ok": False, "reason": str(exc), "added": 0}
    reason = "filled" if added else "mismatch_refused"
    _journal(
        root,
        {"reason": reason, "start_ns": start_ns, "end_ns": ask_end, "added": added, "refused": refused},
    )
    return {
        "ok": True,
        "reason": reason,
        "added": added,
        "refused": refused,
        "start_ns": start_ns,
        "end_ns": ask_end,
    }


def _archive_symbol(root: Path) -> str:
    from lumina_core.maturity.playground.learning_book import read_header

    return str(read_header(root).get("symbol") or "").strip()


def _nt_fetcher(symbol: str) -> Fetcher:
    def fetch(start_ns: int, end_ns: int) -> list[MinuteBar] | None:
        return nt_closed_minutes(start_ns, end_ns, symbol=symbol)

    return fetch


def nt_closed_minutes(start_ns: int, end_ns: int, *, symbol: str) -> list[MinuteBar] | None:
    """Closed 1-minute bars from a connected NinjaTrader client. None when it cannot be asked.

    The fabric supervisor is imported here because unit tests have no broker process.
    An unconnected client is left alone: this does not start or restart the link.
    """
    try:
        from lumina_core.broker.ninjatrader.fabric_link_supervisor import get_fabric_link_supervisor
        from lumina_core.engine.nt_bar_ssot import BarRejected, is_forming_bar, validate_nt_bar
    except Exception:
        return None
    try:
        client = get_fabric_link_supervisor().get_client()
    except Exception:
        return None
    if client is None or not getattr(client, "is_connected", False):
        return None
    fetch = getattr(client, "request_historical_data", None)
    if fetch is None:
        return None
    moment = datetime.fromtimestamp(int(start_ns) / 1_000_000_000, tz=timezone.utc)
    try:
        root_name = contract_root(symbol)
    except CostCardError:
        return None
    instrument = front_month_symbol(root_name, now_utc=moment)
    try:
        response = fetch(
            instrument=instrument,
            bar_period="1m",
            start_unix_ms=int(int(start_ns) // 1_000_000),
            end_unix_ms=int(int(end_ns) // 1_000_000),
            max_bars=_NIBBLE,
        )
    except Exception:
        logger.warning("archive_repair.nt_fetch_failed", exc_info=True)
        return None
    code = str((response or {}).get("code") or "").lower()
    if code not in {"ok", "success"}:
        return None
    spec = spec_for(symbol)
    out: list[MinuteBar] = []
    for raw in (response or {}).get("bars") or []:
        if not isinstance(raw, dict):
            continue
        try:
            bar = validate_nt_bar(raw)
        except BarRejected:
            continue
        if str(bar.get("bar_period") or "") != "1m":
            continue
        if is_forming_bar(bar["timestamp"]):
            continue
        ts_ns = int(bar["timestamp"].timestamp() * 1_000_000_000)
        ts_ns -= ts_ns % MINUTE_NS
        try:
            out.append(
                MinuteBar(
                    ts_ns=ts_ns,
                    open_ticks=_on_tick(float(bar["open"]), spec.tick_size),
                    high_ticks=_on_tick(float(bar["high"]), spec.tick_size),
                    low_ticks=_on_tick(float(bar["low"]), spec.tick_size),
                    close_ticks=_on_tick(float(bar["close"]), spec.tick_size),
                    volume=int(bar["volume"]),
                )
            )
        except BarArchiveError:
            continue
    return out


def _accepted(bars: list[MinuteBar], start_ns: int, end_ns: int) -> list[MinuteBar]:
    kept: list[MinuteBar] = []
    for bar in bars:
        if bar.ts_ns < start_ns or bar.ts_ns >= end_ns:
            continue
        if bar.ts_ns < _REAL_NS:
            continue
        moment = datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=timezone.utc)
        try:
            status = globex_status(moment)
        except ValueError:
            continue
        if status != "open":
            continue
        if bar.high_ticks < max(bar.open_ticks, bar.close_ticks, bar.low_ticks):
            continue
        if bar.low_ticks > min(bar.open_ticks, bar.close_ticks, bar.high_ticks):
            continue
        if bar.volume < 0:
            continue
        kept.append(bar)
    return kept


def _on_tick(price: float, tick_size: float) -> int:
    ticks = float(price) / float(tick_size)
    rounded = round(ticks)
    if abs(ticks - rounded) > 1e-4 or rounded <= 0:
        raise BarArchiveError("price_off_tick")
    return int(rounded)


def _state_path(root: Path) -> Path:
    return root / "reports" / "playground_tick_repair" / "state.json"


def _journal(root: Path, row: dict[str, Any]) -> None:
    path = root / "reports" / "playground_tick_repair" / "repairs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _key(start_ns: int, end_ns: int) -> str:
    return f"{int(start_ns)}:{int(end_ns)}"


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        return {"waits": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"waits": {}}
    if not isinstance(loaded, dict):
        return {"waits": {}}
    waits = loaded.get("waits")
    if not isinstance(waits, dict):
        loaded["waits"] = {}
    return loaded


def _waiting(root: Path, start_ns: int, end_ns: int, now: float) -> bool:
    waits = _load_state(root).get("waits")
    if not isinstance(waits, dict):
        return False
    try:
        seen = float(waits.get(_key(start_ns, end_ns)) or 0.0)
    except (TypeError, ValueError):
        return False
    return seen > 0.0 and (now - seen) < _WAIT_SEC


def _remember(root: Path, start_ns: int, end_ns: int, now: float) -> None:
    state = _load_state(root)
    waits = state.get("waits")
    if not isinstance(waits, dict):
        waits = {}
        state["waits"] = waits
    waits[_key(start_ns, end_ns)] = now
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
