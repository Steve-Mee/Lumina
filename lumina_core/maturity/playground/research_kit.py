"""Playground research kit. Verbs only. No named market rule.

ADR-0056. The frozen policy does not send an order. A name sends one only
after its own forward bar, and only if it is the single hand.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from lumina_core.market.minute_bars import MinuteBar, load_minutes
from lumina_core.market.nt_fees import CostCardError, contract_root, point_value_usd, round_turn_fee_usd, spec_for
from lumina_core.order_gatekeeper.contract_symbols import live_listing
from lumina_core.maturity.phase_runners.awakening_shot import (
    INCUMBENT_PARENT_LEDGER_NAME,
    artifacts_dir,
)
from lumina_core.maturity.playground.sentence_window import MINUTE_NS, signal_on, tail_can_grade
from lumina_core.maturity.playground.session_flat import hold_crosses_halt, overnight_allowed
from lumina_core.maturity.playground.learning_book import (
    FORWARD_MIN,
    LearningBookError,
    append_name,
    append_names,
    append_outcome,
    load_names,
    load_outcomes,
    mark_period,
    period_budget,
    read_header,
)

FORBIDDEN = (
    "h1",
    "h2",
    "null b",
    "null_b",
    "fibonacci",
    "head and shoulders",
    "doji",
    "hammer",
    "engulfing",
    " abc",
    "abc ",
)
_COMPARES = ("range_pos", "return", "volatility")
_QUARTERS = ("top", "bottom")
_STOPS = (0.001, 0.0015, 0.002)
_HOLDS = (20, 30, 60)


class ResearchError(ValueError):
    """The kit refused the step."""


@dataclass(frozen=True, slots=True)
class HandOrder:
    name: str
    side: int
    qty: int
    stop_pct: float
    target_pct: float
    hold: int


def on_school_clock(workspace_root: str | Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Open book: choose the one hand if she is flat. Shut book: do not invent a search."""
    from lumina_core.market.globex_hours import globex_status
    from lumina_core.maturity.playground.crawl import _load_state

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        return {"ok": False, "reason": "naive_timestamp"}
    root = workspace_root
    from lumina_core.market.birth_minute_archive import ensure_school_from_birth

    ensure_school_from_birth(root)
    status = globex_status(moment)
    if status != "open":
        transcribe_scratch(root, now=moment)
    from lumina_core.maturity.playground.progress import load_playground_progress, merge_playground_progress

    header = read_header(root)
    progress = load_playground_progress(root)
    listing = str(progress.get("chart_listing") or "")
    symbol = str(header.get("symbol") or "")
    if listing:
        try:
            symbol = contract_root(listing)
        except CostCardError:
            symbol = str(header.get("symbol") or "")
    rolled = live_listing(listing or symbol, now_utc=moment)
    if rolled and rolled != listing:
        merge_playground_progress(root, {"chart_listing": rolled})
    drawn = 0
    mutated = 0
    scored: dict[str, Any] | None = None
    bars: tuple[MinuteBar, ...] = ()
    if symbol:
        try:
            bars = load_minutes(root, symbol)
        except (OSError, ValueError):
            bars = ()
        for period_id in list((header.get("periods") or {})):
            drawn += freeze_bar_span(root, str(period_id), symbol=symbol, now=moment)
            if status != "open":
                mutated += mutate_after_proof(root, str(period_id), symbol=symbol, now=moment)
            scored = _score_if_measured(root, str(period_id), symbol)
        advance_waiting(root, bars, symbol=symbol)
    if status == "weekend":
        return {
            "ok": True,
            "reason": "weekend_draw",
            "drawn": drawn,
            "mutated": mutated,
            "scored": scored,
        }
    if status != "open":
        return {
            "ok": True,
            "reason": "closed_draw",
            "drawn": drawn,
            "mutated": mutated,
            "scored": scored,
        }
    state = _load_state(root)
    flat = int(state.get("position_side") or 0) == 0
    chosen = select_hand(
        root,
        book_open_ns=int(moment.timestamp() * 1_000_000_000),
        flat=flat,
        market_shut=False,
    )
    return {"ok": True, "reason": "open", "hand": chosen}


def write_period(
    workspace_root: str | Any,
    *,
    period_id: str,
    budget: int,
    seed: int,
    cutoff_ns: int,
    tape_count: int,
    tail_start_ns: int,
    tail_end_ns: int,
    now: datetime,
) -> dict[str, Any]:
    from lumina_core.maturity.playground.learning_book import write_operator_period

    return write_operator_period(
        workspace_root,
        period_id=period_id,
        budget=budget,
        seed=seed,
        cutoff_ns=cutoff_ns,
        tape_count=tape_count,
        tail_start_ns=tail_start_ns,
        tail_end_ns=tail_end_ns,
        now=now,
    )


def freeze_bar_span(workspace_root: str | Any, period_id: str, *, symbol: str, now: datetime) -> int:
    """One sentence per bar length, 1 through 1440. The tail is not read. A second call adds nothing."""
    period = period_budget(workspace_root, period_id)
    if period is None:
        raise ResearchError("budget_missing")
    if now.tzinfo is None:
        raise ResearchError("naive_timestamp")
    if period.get("span_frozen") is True or period.get("tail_seen") is True:
        return 0
    existing = _unique_period(workspace_root, period_id)
    have = {
        (int(row["sentence"]["bar_minutes"]), str(row["sentence"].get("compare") or ""))
        for row in existing
        if isinstance(row.get("sentence"), dict) and str(row["sentence"].get("bar_minutes") or "").isdigit()
    }
    made: list[dict[str, Any]] = []
    for length in range(1, 1441):
        for compare in _COMPARES:
            if (length, compare) in have:
                continue
            sentence = {
                "bar_minutes": length,
                "window": 2,
                "window_unit": "bars",
                "compare": compare,
                "quarter": "top",
                "vol_min": 0.001,
                "side": 1 if length % 2 else -1,
                "stop_pct": 0.001,
                "target_pct": 0.001,
                "hold": 20,
                "forward_bar": FORWARD_MIN,
                "clock": None,
            }
            _refuse_template(sentence)
            made.append(
                _frozen_row(
                    name=f"{period_id}-b{length}-{compare}",
                    parent="",
                    sentence=sentence,
                    period=period,
                    period_id=period_id,
                    symbol=symbol,
                    now=now,
                    status="lab",
                )
            )
    append_names(workspace_root, made)
    mark_period(workspace_root, period_id, span_frozen=True)
    return len(made)


def mutate_after_proof(workspace_root: str | Any, period_id: str, *, symbol: str, now: datetime) -> int:
    """A child is born from a tested parent and is scored on minutes after that proof."""
    period = period_budget(workspace_root, period_id)
    if period is None or period.get("tail_seen") is True:
        return 0
    if now.tzinfo is None:
        raise ResearchError("naive_timestamp")
    made = 0
    latest = _latest_names(workspace_root)
    for parent in list(latest.values()):
        if str(parent.get("budget_id") or "") != str(period_id):
            continue
        if str(parent.get("parent") or ""):
            continue
        fills = [
            int(item["fill_ns"])
            for item in load_outcomes(workspace_root)
            if str(item.get("name") or "") == str(parent.get("name") or "") and item.get("fill_ns") is not None
        ]
        if not fills:
            continue
        child_name = f"{parent['name']}-clock"
        if child_name in latest:
            continue
        sentence = dict(parent.get("sentence") or {})
        if not sentence:
            continue
        sentence["clock"] = {"start_min": 15 * 60, "end_min": 16 * 60}
        row = _frozen_row(
            name=child_name,
            parent=str(parent["name"]),
            sentence=sentence,
            period=period,
            period_id=period_id,
            symbol=symbol,
            now=now,
            status="lab",
        )
        row["cutoff_ns"] = max(fills) + 1
        append_name(workspace_root, row)
        made += 1
    return made


def transcribe_scratch(workspace_root: str | Any, *, now: datetime) -> bool:
    """Copy the open paper pad into the book, then clear it. A second halt does not wipe the copy."""
    from lumina_core.maturity.playground.learning_book import book_dir

    if now.tzinfo is None:
        return False
    opens = _load_open_paper(workspace_root)
    root = book_dir(workspace_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "transcripts.jsonl"
    key = now.astimezone(timezone.utc).date().isoformat()
    if path.is_file() and key in path.read_text(encoding="utf-8"):
        return False
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"day": key, "open_paper": opens}, sort_keys=True) + "\n")
        handle.flush()
    _save_open_paper(workspace_root, {})
    return True


def draw_first_sentences(workspace_root: str | Any, period_id: str, *, symbol: str, now: datetime) -> list[dict[str, Any]]:
    """Seeded draw. Empty parent. Refuses a template and a late seed."""
    period = period_budget(workspace_root, period_id)
    if period is None:
        raise ResearchError("budget_missing")
    if now.tzinfo is None:
        raise ResearchError("naive_timestamp")
    existing = _unique_period(workspace_root, period_id)
    firsts = [row for row in existing if not str(row.get("parent") or "")]
    cap = _first_cap(int(period["budget"]))
    if len(firsts) >= cap or len(existing) >= int(period["budget"]):
        return []
    rng = _rng(int(period["seed"]), len(firsts), _mutation_count(existing))
    made: list[dict[str, Any]] = []
    room = min(cap - len(firsts), int(period["budget"]) - len(existing))
    for _ in range(room):
        sentence = _one_sentence(rng)
        _refuse_template(sentence)
        name = f"{period_id}-{len(existing) + len(made) + 1}"
        row = _frozen_row(
            name=name,
            parent="",
            sentence=sentence,
            period=period,
            period_id=period_id,
            symbol=symbol,
            now=now,
            status="lab",
        )
        append_name(workspace_root, row)
        made.append(row)
    return made


def mutate_children(workspace_root: str | Any, period_id: str, *, symbol: str, now: datetime) -> list[dict[str, Any]]:
    """One new child per call-batch, up to the slots the first sentences did not take."""
    period = period_budget(workspace_root, period_id)
    if period is None:
        raise ResearchError("budget_missing")
    if now.tzinfo is None:
        raise ResearchError("naive_timestamp")
    existing = _unique_period(workspace_root, period_id)
    room = int(period["budget"]) - len(existing)
    if room <= 0:
        return []
    parents = [row for row in existing if isinstance(row.get("sentence"), dict)]
    if not parents:
        return []
    buried = {_canonical(row.get("sentence")) for row in _latest_names(workspace_root).values() if str(row.get("status") or "") == "buried"}
    firsts = [row for row in existing if not str(row.get("parent") or "")]
    rng = _rng(int(period["seed"]), len(firsts), _mutation_count(existing))
    made: list[dict[str, Any]] = []
    for _ in range(room):
        parent = parents[rng.randrange(len(parents))]
        sentence = _mutate(dict(parent["sentence"]), rng)
        _refuse_template(sentence)
        if _canonical(sentence) in buried or _canonical(sentence) == _canonical(parent.get("sentence")):
            continue
        name = f"{period_id}-m{len(existing) + len(made) + 1}"
        row = _frozen_row(
            name=name,
            parent=str(parent["name"]),
            sentence=sentence,
            period=period,
            period_id=period_id,
            symbol=symbol,
            now=now,
            status="lab",
        )
        append_name(workspace_root, row)
        made.append(row)
        parents.append(row)
        _push_child_past_parent_proof(workspace_root, row, str(parent["name"]))
    return made


def score_period(
    workspace_root: str | Any,
    period_id: str,
    bars: tuple[MinuteBar, ...],
    *,
    symbol: str,
    policy_replay_mean_r: float | None,
) -> dict[str, Any]:
    """Score the search slice, then the locked tail once. No order."""
    period = period_budget(workspace_root, period_id)
    if period is None:
        raise ResearchError("budget_missing")
    if policy_replay_mean_r is None:
        return {"ok": False, "reason": "policy_baseline_missing", "admitted": [], "buried": []}
    cutoff = int(period["cutoff_ns"])
    tail_start = int(period["tail_start_ns"])
    tail_end = int(period["tail_end_ns"])
    search = tuple(bar for bar in bars if bar.ts_ns < tail_start and bar.ts_ns < cutoff)
    tail = tuple(bar for bar in bars if tail_start <= bar.ts_ns < tail_end and bar.ts_ns < cutoff)
    if not search or not tail:
        raise ResearchError("slice_empty")
    from lumina_core.market.archive_repair import hole_fingerprint

    search_holes = hole_fingerprint(search)
    tail_holes = hole_fingerprint(tail)
    fingerprint = f"{search_holes}|{tail_holes}"
    names = [row for row in _unique_period(workspace_root, period_id) if str(row.get("status") or "") == "lab"]
    admitted: list[str] = []
    buried: list[str] = []
    waiting: list[str] = []
    search_len = len(search)
    scored_n = 0
    for row in names:
        if scored_n >= 1:
            break
        sentence = row.get("sentence") if isinstance(row.get("sentence"), dict) else {}
        if fingerprint != "|" and str(row.get("hole_wait") or "") == fingerprint:
            continue
        need = _minutes_needed(sentence)
        if str(sentence.get("window_unit") or "bars") == "bars" and need > search_len:
            _bury(workspace_root, row, "window_longer_than_slice")
            buried.append(str(row["name"]))
            scored_n += 1
            continue
        if not tail_can_grade(sentence, tail):
            _set_status(workspace_root, row, "waiting_tail", wait_reason="tail_cannot_hold")
            waiting.append(str(row["name"]))
            scored_n += 1
            continue
        if "search_mean_r" not in row:
            search_mean = _mean_r(row, search, symbol)
            row = {**row, "search_mean_r": search_mean, "status": "lab"}
            append_name(workspace_root, row)
        else:
            search_mean = row.get("search_mean_r")
        if search_mean is None and search_holes:
            _set_status(workspace_root, row, "lab", hole_wait=fingerprint)
            waiting.append(str(row["name"]))
            scored_n += 1
            continue
        if search_mean is None or float(search_mean) <= 0.0:
            _bury(workspace_root, row, "search_failed")
            buried.append(str(row["name"]))
            scored_n += 1
            continue
        tail_mean = _mean_r(row, tail, symbol)
        if tail_mean is None and tail_holes:
            _set_status(workspace_root, {**row, "search_mean_r": search_mean}, "lab", hole_wait=fingerprint)
            waiting.append(str(row["name"]))
            scored_n += 1
            continue
        passes = tail_mean is not None and float(tail_mean) > 0.0 and float(tail_mean) > float(policy_replay_mean_r)
        if passes:
            _set_status(workspace_root, row, "forward", tail_mean_r=tail_mean)
            admitted.append(str(row["name"]))
        else:
            _bury(workspace_root, row, "tail_failed")
            buried.append(str(row["name"]))
        scored_n += 1
    return {"ok": True, "reason": "scored", "admitted": admitted, "buried": buried, "waiting": waiting}


def measured_plant_mean_r(workspace_root: str | Any) -> float | None:
    """Mean trade_r of the sealed plant book. A missing book is unmeasured, not zero."""
    path = artifacts_dir(workspace_root) / INCUMBENT_PARENT_LEDGER_NAME
    if not path.is_file():
        return None
    values: list[float] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(row, dict) or row.get("plant") is True:
            continue
        raw = row.get("trade_r")
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            return None
    if not values:
        return None
    return float(sum(values) / float(len(values)))


def _score_if_measured(workspace_root: str | Any, period_id: str, symbol: str) -> dict[str, Any] | None:
    """Score only when the tail exists and the plant mean comes from the sealed book."""
    replay = measured_plant_mean_r(workspace_root)
    if replay is None:
        return {"ok": False, "reason": "policy_baseline_missing", "admitted": [], "buried": []}
    try:
        bars = load_minutes(workspace_root, symbol)
    except (OSError, ValueError):
        return {"ok": False, "reason": "policy_baseline_missing", "admitted": [], "buried": []}
    if not bars:
        return {"ok": False, "reason": "policy_baseline_missing", "admitted": [], "buried": []}
    try:
        result = score_period(
            workspace_root,
            period_id,
            bars,
            symbol=symbol,
            policy_replay_mean_r=replay,
        )
    except ResearchError:
        return {"ok": False, "reason": "slice_empty", "admitted": [], "buried": []}
    if result.get("reason") == "tape_unmeasured":
        return result
    mark_period(workspace_root, period_id, tail_seen=not _lab_names(workspace_root, period_id))
    return result


_ET = ZoneInfo("America/New_York")
_WAIT_YEAR_CAP = 20


def advance_waiting(workspace_root: str | Any, bars: tuple[MinuteBar, ...], *, symbol: str) -> dict[str, Any]:
    """Seal one future tail for a sentence this exam cannot hold, then grade it once.

    The tail starts at the sentence cutoff and ends on a calendar rule, or on the
    minute count the sentence needs. The end is written once. Prices do not choose it.
    The birth holdout is not scored again, and its winning trades are not copied.
    """
    if not bars:
        return {"ok": True, "reason": "no_bars", "scored": 0}
    sealed_n = 0
    for row in list(_latest_names(workspace_root).values()):
        if str(row.get("status") or "") != "waiting_tail":
            continue
        if row.get("wait_sealed") is True:
            continue
        bounds = _wait_bounds(row, bars)
        if bounds is None:
            continue
        start_ns, end_ns = bounds
        _set_status(
            workspace_root,
            row,
            "waiting_tail",
            wait_sealed=True,
            wait_tail_start_ns=int(start_ns),
            wait_tail_end_ns=int(end_ns),
        )
        sealed_n += 1
    scored = 0
    for row in list(_latest_names(workspace_root).values()):
        if scored >= 1:
            break
        if str(row.get("status") or "") != "waiting_tail" or row.get("wait_sealed") is not True:
            continue
        end_ns = int(row.get("wait_tail_end_ns") or 0)
        if end_ns <= 0 or int(bars[-1].ts_ns) < end_ns:
            continue
        start_ns = int(row.get("wait_tail_start_ns") or 0)
        tail_bars = tuple(bar for bar in bars if start_ns <= int(bar.ts_ns) < end_ns)
        from lumina_core.market.archive_repair import unresolved_open_holes

        if unresolved_open_holes(workspace_root, tail_bars):
            continue
        seen = len(tail_bars)
        if str(row.get("wait_reason") or "") == "tail_unmeasured" and int(row.get("wait_seen_bars") or -1) == seen:
            continue
        _grade_waiting(workspace_root, row, bars, symbol)
        scored += 1
    return {"ok": True, "reason": "waiting", "sealed": sealed_n, "scored": scored}


def _wait_bounds(row: dict[str, Any], bars: tuple[MinuteBar, ...]) -> tuple[int, int] | None:
    sentence = row.get("sentence")
    if not isinstance(sentence, dict):
        return None
    origin = int(row.get("cutoff_ns") or 0)
    if origin <= 0:
        return None
    need = _minutes_needed(sentence)
    if need >= 10**9:
        return None
    clock = sentence.get("clock") if isinstance(sentence.get("clock"), dict) else None
    months = clock.get("months") if isinstance(clock, dict) else None
    if isinstance(months, list) and months:
        return _season_bounds(origin, [int(item) for item in months], need)
    if str(sentence.get("window_unit") or "bars") == "calendar":
        return _bucket_bounds(origin, str(sentence.get("calendar") or ""), need)
    required = need + 2
    unseen = [bar for bar in bars if int(bar.ts_ns) >= origin]
    if len(unseen) < required:
        return None
    end_ns = int(unseen[required - 1].ts_ns) + MINUTE_NS
    weekdays = clock.get("weekdays") if isinstance(clock, dict) else None
    if isinstance(weekdays, list) and weekdays:
        end_ns = _cover_weekday(origin, end_ns, {int(item) for item in weekdays})
    return origin, end_ns


def _season_bounds(origin_ns: int, months: list[int], need: int) -> tuple[int, int] | None:
    needed = sorted({int(item) for item in months if 1 <= int(item) <= 12})
    if not needed:
        return None
    end_ns = _season_end_after(origin_ns, needed)
    span = (need + 2) * MINUTE_NS
    guard = 0
    while end_ns - int(origin_ns) < span:
        end_ns = _season_end_after(end_ns, needed)
        guard += 1
        if guard > _WAIT_YEAR_CAP:
            return None
    return int(origin_ns), int(end_ns)


def _season_end_after(origin_ns: int, months: list[int]) -> int:
    origin = datetime.fromtimestamp(int(origin_ns) / 1_000_000_000, tz=timezone.utc).astimezone(_ET)
    first = int(months[0])
    last = int(months[-1])
    year = int(origin.year)
    start = datetime(year, first, 1, tzinfo=_ET)
    if start <= origin:
        year += 1
    end_year = year if last >= first else year + 1
    if last == 12:
        end = datetime(end_year + 1, 1, 1, tzinfo=_ET)
    else:
        end = datetime(end_year, last + 1, 1, tzinfo=_ET)
    return int(end.timestamp() * 1_000_000_000)


def _bucket_bounds(origin_ns: int, kind: str, need: int) -> tuple[int, int] | None:
    end_ns = _next_bucket_end(origin_ns, kind)
    if end_ns is None:
        return None
    span = (max(need, 1) + 2) * MINUTE_NS
    guard = 0
    while end_ns - int(origin_ns) < span:
        nxt = _next_bucket_end(end_ns, kind)
        if nxt is None or nxt <= end_ns:
            return None
        end_ns = nxt
        guard += 1
        if guard > _WAIT_YEAR_CAP:
            return None
    return int(origin_ns), int(end_ns)


def _next_bucket_end(origin_ns: int, kind: str) -> int | None:
    origin = datetime.fromtimestamp(int(origin_ns) / 1_000_000_000, tz=timezone.utc).astimezone(_ET)
    if kind == "day":
        start = origin.replace(hour=0, minute=0, second=0, microsecond=0)
        if start < origin:
            start = start + timedelta(days=1)
        end = start + timedelta(days=1)
    elif kind == "week":
        start = origin.replace(hour=0, minute=0, second=0, microsecond=0)
        if start < origin or origin.weekday() != 0:
            start = start + timedelta(days=(7 - start.weekday()) % 7 or 7)
        end = start + timedelta(days=7)
    elif kind == "month":
        start = origin.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start < origin:
            start = _add_month(start)
        end = _add_month(start)
    elif kind == "quarter":
        month = ((origin.month - 1) // 3) * 3 + 1
        start = origin.replace(month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
        if start < origin:
            start = _add_month(start, 3)
        end = _add_month(start, 3)
    else:
        return None
    return int(end.timestamp() * 1_000_000_000)


def _add_month(moment: datetime, count: int = 1) -> datetime:
    month = int(moment.month) - 1 + int(count)
    year = int(moment.year) + month // 12
    month = month % 12 + 1
    return moment.replace(year=year, month=month, day=1)


def _cover_weekday(origin_ns: int, end_ns: int, weekdays: set[int]) -> int:
    cursor = datetime.fromtimestamp(int(origin_ns) / 1_000_000_000, tz=timezone.utc).astimezone(_ET)
    end = datetime.fromtimestamp(int(end_ns) / 1_000_000_000, tz=timezone.utc).astimezone(_ET)
    seen = False
    while cursor < end:
        if cursor.weekday() in weekdays:
            seen = True
            break
        cursor += timedelta(days=1)
    if seen:
        return int(end_ns)
    extra = end
    for _ in range(8):
        if extra.weekday() in weekdays:
            break
        extra += timedelta(days=1)
    close = extra.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return int(close.timestamp() * 1_000_000_000)


def _grade_waiting(
    workspace_root: str | Any,
    row: dict[str, Any],
    bars: tuple[MinuteBar, ...],
    symbol: str,
) -> None:
    sentence = row.get("sentence")
    if not isinstance(sentence, dict):
        _bury(workspace_root, row, "sentence_missing")
        return
    start_ns = int(row.get("wait_tail_start_ns") or 0)
    end_ns = int(row.get("wait_tail_end_ns") or 0)
    tail = tuple(bar for bar in bars if start_ns <= int(bar.ts_ns) < end_ns)
    if not tail_can_grade(sentence, tail):
        _set_status(
            workspace_root,
            row,
            "waiting_tail",
            wait_reason="tail_unmeasured",
            wait_seen_bars=len(tail),
        )
        return
    search_end = int(row.get("search_end_ns") or 0)
    search = tuple(bar for bar in bars if int(bar.ts_ns) < search_end)
    search_mean = _mean_r(row, search, symbol)
    if search_mean is None or float(search_mean) <= 0.0:
        _bury(workspace_root, {**row, "search_mean_r": search_mean}, "search_failed")
        return
    plant = measured_plant_mean_r(workspace_root)
    if plant is None:
        return
    tail_mean = _mean_r({**row, "search_mean_r": search_mean}, tail, symbol)
    if tail_mean is not None and float(tail_mean) > 0.0 and float(tail_mean) > float(plant):
        _set_status(workspace_root, row, "forward", search_mean_r=search_mean, tail_mean_r=tail_mean)
        return
    _bury(workspace_root, {**row, "search_mean_r": search_mean}, "tail_failed")


def _lab_names(workspace_root: str | Any, period_id: str) -> list[dict[str, Any]]:
    return [row for row in _unique_period(workspace_root, period_id) if str(row.get("status") or "") == "lab"]


def freeze_forward_span(workspace_root: str | Any, name: str, span: int) -> None:
    """X is written before the first outcome. A later edit is void."""
    if int(span) < FORWARD_MIN:
        raise ResearchError("forward_bar_too_small")
    if any(str(row.get("name") or "") == str(name) for row in load_outcomes(workspace_root)):
        raise ResearchError("forward_bar_frozen")
    current = _latest_names(workspace_root).get(str(name))
    if current is None:
        raise ResearchError("name_missing")
    _set_status(workspace_root, current, str(current.get("status") or "lab"), forward_bar=int(span))


def _minutes_needed(sentence: dict[str, Any]) -> int:
    try:
        size = int(sentence.get("bar_minutes") or 1)
        count = int(sentence.get("window") or 1)
    except (TypeError, ValueError):
        return 10**9
    if size < 1 or count < 1:
        return 10**9
    return size * count


def replay_from_observation(observation: dict[str, Any] | None) -> float | None:
    """A builder default is not a plant walk. Missing stays missing, never zero."""
    if not isinstance(observation, dict):
        return None
    if observation.get("drawdown_measured") is not True and observation.get("drawdown") in (0, 0.0, None):
        return None
    if observation.get("trend_slope_measured") is not True and observation.get("trend_slope_5") in (0, 0.0, None):
        return None
    raw = observation.get("mean_r")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def note_forward_outcome(
    workspace_root: str | Any,
    *,
    name: str,
    signal_close_ns: int,
    fill_ns: int,
    net_r: float,
    reason: str,
) -> None:
    if int(fill_ns) <= int(signal_close_ns):
        raise ResearchError("fill_not_after_signal")
    if reason not in {"stop", "target", "time"}:
        raise ResearchError("reason_invalid")
    append_outcome(
        workspace_root,
        {
            "name": name,
            "signal_close_ns": int(signal_close_ns),
            "fill_ns": int(fill_ns),
            "net_r": float(net_r),
            "reason": reason,
        },
    )


def select_hand(workspace_root: str | Any, *, book_open_ns: int, flat: bool, market_shut: bool) -> str | None:
    """One hand. Earliest freeze stamp, then raw-byte name. Only at an open, and only when flat."""
    names = _latest_names(workspace_root)
    current = [row for row in names.values() if str(row.get("status") or "") == "hand"]
    if current:
        return str(current[0]["name"])
    if market_shut or not flat:
        return None
    ready = []
    for row in names.values():
        if str(row.get("status") or "") != "forward":
            continue
        outcomes = [item for item in load_outcomes(workspace_root) if str(item.get("name") or "") == str(row.get("name"))]
        bar = max(int(row.get("forward_bar") or FORWARD_MIN), FORWARD_MIN)
        if len(outcomes) < bar:
            continue
        mean = sum(float(item["net_r"]) for item in outcomes) / float(len(outcomes))
        if mean <= 0.0:
            continue
        from lumina_core.maturity.playground.rule_exam import rule_exam_passed

        sentence = row.get("sentence")
        symbol = str(row.get("symbol") or "")
        if not isinstance(sentence, dict) or not rule_exam_passed(
            workspace_root, str(row.get("name") or ""), sentence, symbol
        ):
            continue
        ready.append(row)
    if not ready:
        return None
    ready.sort(key=lambda row: (str(row.get("freeze_stamp") or ""), str(row.get("name") or "").encode()))
    chosen = ready[0]
    _set_status(workspace_root, chosen, "hand", hand_since_ns=int(book_open_ns))
    return str(chosen["name"])


def coloring_hand(workspace_root: str | Any) -> tuple[str, int] | None:
    """The one hand and the instant its green-day clock started. None before that."""
    names = _latest_names(workspace_root)
    hands = [row for row in names.values() if str(row.get("status") or "") == "hand"]
    if len(hands) != 1:
        return None
    row = hands[0]
    since = int(row.get("hand_since_ns") or 0)
    if since <= 0 or not str(row.get("name") or ""):
        return None
    return str(row["name"]), since


def hand_order(
    workspace_root: str | Any,
    *,
    symbol: str,
    price: float,
    equity: float | None,
    now_ns: int,
) -> HandOrder | None:
    """The single hand, after its forward bar. None when the policy would have traded."""
    names = _latest_names(workspace_root)
    hands = [row for row in names.values() if str(row.get("status") or "") == "hand"]
    if len(hands) != 1:
        return None
    row = hands[0]
    if int(now_ns) < int(row.get("hand_since_ns") or 0):
        return None
    sentence = row.get("sentence")
    if not isinstance(sentence, dict):
        return None
    try:
        spec = spec_for(symbol)
        stored = load_minutes(workspace_root, symbol)
        minute_ns = int(now_ns) - (int(now_ns) % MINUTE_NS)
        fill = next((bar for bar in stored if int(bar.ts_ns) == minute_ns), None)
        if fill is None:
            return None
        close_px = fill.close_ticks * spec.tick_size
        if abs(float(price) - close_px) > spec.tick_size * 0.5:
            return None
        prior = tuple(bar for bar in stored if int(bar.ts_ns) < minute_ns)
        if not signal_true(sentence, prior, tick_size=spec.tick_size):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    qty = sim_qty(symbol, price=price, stop_pct=float(sentence["stop_pct"]), equity=equity)
    if qty is None:
        return None
    if not overnight_allowed(workspace_root) and hold_crosses_halt(int(now_ns), int(sentence["hold"])):
        return None
    return HandOrder(
        name=str(row["name"]),
        side=int(sentence["side"]),
        qty=qty,
        stop_pct=float(sentence["stop_pct"]),
        target_pct=float(sentence["target_pct"]),
        hold=int(sentence["hold"]),
    )


def sim_qty(symbol: str, *, price: float, stop_pct: float, equity: float | None) -> int | None:
    """Contracts that fit inside 2% of measured SIM equity. Missing equity is no order."""
    if equity is None or float(equity) <= 0.0 or float(price) <= 0.0 or float(stop_pct) <= 0.0:
        return None
    risk = float(price) * float(stop_pct) * float(point_value_usd(symbol))
    if risk <= 0.0:
        return None
    budget = 0.02 * float(equity)
    qty = int(budget // risk)
    if qty < 1:
        return None
    return qty


def signal_true(sentence: dict[str, Any], history: tuple[MinuteBar, ...], *, tick_size: float) -> bool:
    return signal_on(sentence, history, tick_size=tick_size)


def _mean_r(row: dict[str, Any], bars: tuple[MinuteBar, ...], symbol: str) -> float | None:
    sentence = row.get("sentence")
    if not isinstance(sentence, dict):
        return None
    spec = spec_for(symbol)
    scores: list[float] = []
    need = _minutes_needed(sentence)
    if need >= 10**9 or len(bars) <= need + 1:
        return None
    for index in range(need, len(bars) - 1):
        history = bars[index - need : index]
        if not signal_true(sentence, history, tick_size=spec.tick_size):
            continue
        fill = bars[index]
        closed = _trade_exit(sentence, bars, index, spec.tick_size)
        if closed is None:
            continue
        exit_px, reason = closed
        entry = fill.close_ticks * spec.tick_size
        side = int(sentence["side"])
        gross = (exit_px - entry) * float(side) * float(spec.point_value_usd)
        fee = round_turn_fee_usd(symbol, 1)
        risk = entry * float(sentence["stop_pct"]) * float(spec.point_value_usd)
        if risk <= 0.0:
            continue
        scores.append((gross - fee) / risk)
        _ = reason
    if not scores:
        return None
    return float(sum(scores) / float(len(scores)))


def ohlc_exit(
    *,
    side: int,
    stop_px: float,
    target_px: float,
    bar: MinuteBar,
    tick_size: float,
) -> tuple[float, str] | None:
    """Fill of one bar. A gap fills at the open. A bar that touches both fills the stop."""
    opened = bar.open_ticks * tick_size
    high = bar.high_ticks * tick_size
    low = bar.low_ticks * tick_size
    if side > 0:
        if opened <= stop_px:
            return opened, "stop"
        if opened >= target_px:
            return opened, "target"
        if low <= stop_px:
            return stop_px, "stop"
        if high >= target_px:
            return target_px, "target"
        return None
    if side < 0:
        if opened >= stop_px:
            return opened, "stop"
        if opened <= target_px:
            return opened, "target"
        if high >= stop_px:
            return stop_px, "stop"
        if low <= target_px:
            return target_px, "target"
    return None


def _trade_exit(
    sentence: dict[str, Any],
    bars: tuple[MinuteBar, ...],
    fill_index: int,
    tick_size: float,
) -> tuple[float, str] | None:
    entry = bars[fill_index].close_ticks * tick_size
    side = int(sentence["side"])
    stop_px = entry * (1.0 - float(sentence["stop_pct"])) if side > 0 else entry * (1.0 + float(sentence["stop_pct"]))
    target_px = entry * (1.0 + float(sentence["target_pct"])) if side > 0 else entry * (1.0 - float(sentence["target_pct"]))
    last = min(len(bars) - 1, fill_index + int(sentence["hold"]))
    for cursor in range(fill_index + 1, last + 1):
        hit = ohlc_exit(side=side, stop_px=stop_px, target_px=target_px, bar=bars[cursor], tick_size=tick_size)
        if hit is not None:
            return hit
    if last > fill_index:
        return bars[last].close_ticks * tick_size, "time"
    return None


def _exit_bar(
    sentence: dict[str, Any],
    bars: tuple[MinuteBar, ...],
    fill_index: int,
    tick_size: float,
) -> tuple[MinuteBar | None, str]:
    entry = bars[fill_index].close_ticks * tick_size
    side = int(sentence["side"])
    stop_px = entry * (1.0 - float(sentence["stop_pct"])) if side > 0 else entry * (1.0 + float(sentence["stop_pct"]))
    target_px = entry * (1.0 + float(sentence["target_pct"])) if side > 0 else entry * (1.0 - float(sentence["target_pct"]))
    last = min(len(bars) - 1, fill_index + int(sentence["hold"]))
    for cursor in range(fill_index + 1, last + 1):
        bar = bars[cursor]
        high = bar.high_ticks * tick_size
        low = bar.low_ticks * tick_size
        if side > 0 and low <= stop_px:
            return bar, "stop"
        if side < 0 and high >= stop_px:
            return bar, "stop"
        if side > 0 and high >= target_px:
            return bar, "target"
        if side < 0 and low <= target_px:
            return bar, "target"
    if last > fill_index:
        return bars[last], "time"
    return None, ""


def on_closed_minute(workspace_root: str | Any, symbol: str, bar: MinuteBar, *, market_open: bool) -> int:
    """Paper-follow every forward name. A shut book does nothing. The hand is not opened here."""
    if not market_open:
        return 0
    from lumina_core.market.minute_bars import load_minutes

    prior = tuple(item for item in load_minutes(workspace_root, symbol) if item.ts_ns < bar.ts_ns)
    spec = spec_for(symbol)
    opens = _load_open_paper(workspace_root)
    closed = 0
    for row in _latest_names(workspace_root).values():
        if str(row.get("status") or "") != "forward":
            continue
        if str(row.get("symbol") or symbol) not in {symbol, contract_root_of(symbol)}:
            continue
        if bar.ts_ns < int(row.get("cutoff_ns") or 0):
            continue
        name = str(row["name"])
        sentence = row.get("sentence")
        if not isinstance(sentence, dict):
            continue
        slot = opens.get(name)
        if slot is None:
            if signal_true(sentence, prior, tick_size=spec.tick_size):
                if not overnight_allowed(workspace_root) and hold_crosses_halt(
                    bar.ts_ns, int(sentence["hold"])
                ):
                    continue
                opens[name] = {
                    "entry_ns": bar.ts_ns,
                    "signal_ns": prior[-1].ts_ns,
                    "entry_px": bar.close_ticks * spec.tick_size,
                    "side": int(sentence["side"]),
                    "stop_pct": float(sentence["stop_pct"]),
                    "target_pct": float(sentence["target_pct"]),
                    "hold": int(sentence["hold"]),
                    "held": 0,
                }
            continue
        slot["held"] = int(slot.get("held") or 0) + 1
        reason = _paper_exit(slot, bar, spec.tick_size)
        if reason is None and int(slot["held"]) >= int(slot["hold"]):
            reason = "time"
        if reason is None:
            opens[name] = slot
            continue
        entry = float(slot["entry_px"])
        side = int(slot["side"])
        stop_px = entry * (1.0 - float(slot["stop_pct"])) if side > 0 else entry * (1.0 + float(slot["stop_pct"]))
        target_px = entry * (1.0 + float(slot["target_pct"])) if side > 0 else entry * (1.0 - float(slot["target_pct"]))
        hit = ohlc_exit(side=side, stop_px=stop_px, target_px=target_px, bar=bar, tick_size=spec.tick_size)
        exit_px = hit[0] if hit is not None else bar.close_ticks * spec.tick_size
        gross = (exit_px - entry) * float(side) * float(spec.point_value_usd)
        risk = entry * float(slot["stop_pct"]) * float(spec.point_value_usd)
        if risk > 0.0:
            note_forward_outcome(
                workspace_root,
                name=name,
                signal_close_ns=int(slot["signal_ns"]) if slot.get("signal_ns") else int(slot["entry_ns"]) - 1,
                fill_ns=bar.ts_ns,
                net_r=(gross - round_turn_fee_usd(symbol, 1)) / risk,
                reason=reason,
            )
            closed += 1
        opens.pop(name, None)
    _save_open_paper(workspace_root, opens)
    return closed


def contract_root_of(symbol: str) -> str:
    from lumina_core.market.nt_fees import contract_root

    return contract_root(symbol)


def _paper_exit(slot: dict[str, Any], bar: MinuteBar, tick_size: float) -> str | None:
    entry = float(slot["entry_px"])
    side = int(slot["side"])
    high = bar.high_ticks * tick_size
    low = bar.low_ticks * tick_size
    stop_px = entry * (1.0 - float(slot["stop_pct"])) if side > 0 else entry * (1.0 + float(slot["stop_pct"]))
    target_px = entry * (1.0 + float(slot["target_pct"])) if side > 0 else entry * (1.0 - float(slot["target_pct"]))
    if side > 0 and low <= stop_px:
        return "stop"
    if side < 0 and high >= stop_px:
        return "stop"
    if side > 0 and high >= target_px:
        return "target"
    if side < 0 and low <= target_px:
        return "target"
    return None


def _unique_period(workspace_root: str | Any, period_id: str) -> list[dict[str, Any]]:
    order: list[str] = []
    latest: dict[str, dict[str, Any]] = {}
    for row in load_names(workspace_root):
        if str(row.get("budget_id") or "") != period_id:
            continue
        name = str(row.get("name") or "")
        if name not in latest:
            order.append(name)
        latest[name] = row
    return [latest[name] for name in order]


def _first_cap(budget: int) -> int:
    if budget <= 1:
        return 1
    return max(1, budget // 2)


def _mutation_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if str(row.get("parent") or ""))


def _rng(seed: int, n_first: int, n_mutations: int) -> random.Random:
    rng = random.Random(int(seed))
    for _ in range(n_first):
        _one_sentence(rng)
    blank = {"window": 5, "window_unit": "bars", "compare": "return", "quarter": "top", "vol_min": 0.001, "side": 1, "stop_pct": 0.001, "target_pct": 0.001, "hold": 20, "clock": None}
    for _ in range(n_mutations):
        _mutate(blank, rng)
    return rng


def _mutate(sentence: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    kind = rng.choice(("window", "side", "stop", "hold", "clock", "compare", "bar"))
    side = rng.choice((-1, 1))
    stop = rng.choice(_STOPS)
    target = rng.choice(_STOPS)
    hold = rng.choice(_HOLDS)
    compare = rng.choice(_COMPARES)
    quarter = rng.choice(_QUARTERS)
    out = dict(sentence)
    if kind == "window":
        out["window"] = 1 + int(rng.randrange(30))
        out["window_unit"] = str(rng.choice(("bars", "calendar")))
    elif kind == "bar":
        out["bar_minutes"] = 1 + int(rng.randrange(1440))
    elif kind == "side":
        out["side"] = int(side)
    elif kind == "stop":
        out["stop_pct"] = float(stop)
        out["target_pct"] = float(target)
    elif kind == "hold":
        out["hold"] = int(hold)
    elif kind == "clock":
        out["clock"] = _drawn_clock(rng)
    else:
        out["compare"] = compare
        out["quarter"] = quarter
    return out


def _canonical(sentence: object) -> str:
    if not isinstance(sentence, dict):
        return ""
    return json.dumps(sentence, sort_keys=True, separators=(",", ":"))


def _load_open_paper(workspace_root: str | Any) -> dict[str, Any]:
    from lumina_core.maturity.playground.learning_book import book_dir

    path = book_dir(workspace_root) / "open_paper.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_open_paper(workspace_root: str | Any, opens: dict[str, Any]) -> None:
    from lumina_core.maturity.playground.learning_book import book_dir

    path = book_dir(workspace_root) / "open_paper.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(opens, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _drawn_clock(rng: random.Random) -> dict[str, Any]:
    hour = rng.randrange(0, 23)
    clock: dict[str, Any] = {"start_min": hour * 60, "end_min": hour * 60 + 60}
    if rng.randrange(2) == 0:
        clock["weekdays"] = [rng.randrange(0, 5)]
    if rng.randrange(2) == 0:
        clock["months"] = [1 + rng.randrange(12)]
    return clock


def _one_sentence(rng: random.Random) -> dict[str, Any]:
    compare = rng.choice(_COMPARES)
    return {
        "bar_minutes": 1 + int(rng.randrange(1440)),
        "window": 1 + int(rng.randrange(30)),
        "window_unit": str(rng.choice(("bars", "calendar"))),
        "calendar": str(rng.choice(("day", "week", "month", "quarter"))),
        "compare": compare,
        "quarter": rng.choice(_QUARTERS),
        "vol_min": 0.001,
        "side": int(rng.choice((-1, 1))),
        "stop_pct": float(rng.choice(_STOPS)),
        "target_pct": float(rng.choice(_STOPS)),
        "hold": int(rng.choice(_HOLDS)),
        "forward_bar": FORWARD_MIN,
        "clock": _drawn_clock(rng),
    }


def _refuse_template(sentence: dict[str, Any]) -> None:
    text = json.dumps(sentence, sort_keys=True).lower()
    if any(token in text for token in FORBIDDEN):
        raise ResearchError("template_forbidden")


def _frozen_row(
    *,
    name: str,
    parent: str,
    sentence: dict[str, Any],
    period: dict[str, Any],
    period_id: str,
    symbol: str,
    now: datetime,
    status: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "parent": parent,
        "freeze_stamp": now.astimezone(timezone.utc).isoformat(),
        "cutoff_ns": int(period["cutoff_ns"]),
        "window_unit": str(sentence["window_unit"]),
        "sentence": sentence,
        "symbol": symbol,
        "search_start_ns": 0,
        "search_end_ns": int(period["tail_start_ns"]),
        "tail_start_ns": int(period["tail_start_ns"]),
        "tail_end_ns": int(period["tail_end_ns"]),
        "forward_bar": max(FORWARD_MIN, int(sentence.get("forward_bar") or FORWARD_MIN)),
        "budget_id": period_id,
        "status": status,
    }


def _push_child_past_parent_proof(workspace_root: str | Any, row: dict[str, Any], parent_name: str) -> None:
    """A weekend child is tested after the days that suggested it, not on them."""
    fills = [
        int(item["fill_ns"])
        for item in load_outcomes(workspace_root)
        if str(item.get("name") or "") == parent_name and item.get("fill_ns") is not None
    ]
    if not fills:
        return
    _set_status(workspace_root, row, str(row.get("status") or "lab"), cutoff_ns=max(fills) + 1)


def _latest_names(workspace_root: str | Any) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for row in load_names(workspace_root):
        found[str(row.get("name") or "")] = row
    return found


def _mark_scored(workspace_root: str | Any, row: dict[str, Any], *, search_mean_r: float | None) -> None:
    append_name(workspace_root, {**row, "search_mean_r": search_mean_r, "status": "lab"})


def _bury(workspace_root: str | Any, row: dict[str, Any], reason: str) -> None:
    append_name(workspace_root, {**row, "status": "buried", "bury_reason": reason})


def _set_status(workspace_root: str | Any, row: dict[str, Any], status: str, **extra: Any) -> None:
    append_name(workspace_root, {**row, "status": status, **extra})


def canonical_text(sentence: dict[str, Any]) -> str:
    return json.dumps(sentence, sort_keys=True, separators=(",", ":"))


def _guard_book_error(exc: LearningBookError) -> ResearchError:
    return ResearchError(str(exc))
