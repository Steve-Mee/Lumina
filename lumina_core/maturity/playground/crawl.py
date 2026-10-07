"""Predict-only Playground crawl. Orders go through place_order. No learn(), no zero-obs."""

from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

from lumina_core.birth.birth_exit_policy_export import load_frozen_policy
from lumina_core.order_gatekeeper.contract_symbols import live_listing
from lumina_core.io.atomic_fs import atomic_write_text
from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import load_continuum
from lumina_core.maturity.playground.fills import record_policy_close
from lumina_core.maturity.playground.habitat import write_occupancy
from lumina_core.maturity.playground.select import load_policy_identities
from lumina_core.rl.observation_builder import build_observation_vector
from lumina_core.rl.trend_features import MIN_TREND_LOOKBACK

logger = get_logger("lumina.maturity.playground.crawl")

BARS_REL = Path("state") / "lumina_playground_bars.jsonl"
CRAWL_REL = Path("state") / "lumina_playground_crawl.json"
FILL_STARVE_BARS = 500
SIM_MODES = frozenset({"sim", "sim_real_guard"})

OrderSink = Callable[..., dict[str, Any]]
_INTENT: ContextVar[dict[str, Any] | None] = ContextVar("playground_crawl_intent", default=None)
_FILL: ContextVar[dict[str, Any] | None] = ContextVar("playground_crawl_fill", default=None)
_REJECT: ContextVar[str] = ContextVar("playground_order_reject", default="")
_SINK: OrderSink | None = None


def crawl_order_intent() -> dict[str, Any] | None:
    return _INTENT.get()


def resolve_crawl_submission(intent: dict[str, Any] | None, mode: str) -> dict[str, Any] | None:
    """SIM crawl uses the chart and drops the dream hold. REAL keeps both. Empty chart refuses."""
    if not isinstance(intent, dict):
        return None
    if str(mode or "").strip().lower() not in SIM_MODES:
        return None
    instrument = str(intent.get("instrument") or "").strip()
    if not instrument:
        return {"reject": "chart_listing_missing"}
    return {
        "symbol": instrument,
        "hold_until_ts": 0.0,
        "stop_px": intent.get("stop_px"),
        "target_px": intent.get("target_px"),
    }


def note_venue_fill(*, order_id: str, fill_px: float, stop_px: float) -> None:
    _FILL.set({"order_id": str(order_id), "fill_px": float(fill_px), "stop_px": float(stop_px)})


def note_order_reject(reason: str) -> None:
    """Last place_order refusal. The crawl heartbeat copies this string."""
    _REJECT.set(str(reason or "rejected")[:120])


def take_order_reject() -> str:
    reason = str(_REJECT.get() or "")
    _REJECT.set("")
    return reason


def take_venue_fill() -> dict[str, Any] | None:
    fill = _FILL.get()
    _FILL.set(None)
    return fill


def bind_app_order_sink(app: Any) -> None:
    """Runner thread calls this sink. The venue fill is whatever place_order just recorded."""

    def sink(
        *,
        action: str,
        qty: int,
        stop_px: float,
        target_px: float,
        instrument: str,
    ) -> dict[str, Any]:
        _ = (stop_px, target_px, instrument)
        place = getattr(app, "place_order", None)
        if not callable(place):
            return {"ok": False}
        ok = bool(place(action, int(qty)))
        fill = take_venue_fill()
        if ok and isinstance(fill, dict) and str(fill.get("order_id") or "").strip():
            return {"ok": True, **fill}
        reason = take_order_reject()
        if ok and not reason:
            reason = "accepted_without_fill_px"
        return {"ok": False, "reason": reason or "place_order_rejected"}

    bind_order_sink(sink)


def bind_order_sink(sink: OrderSink | None) -> None:
    global _SINK
    _SINK = sink


def current_order_sink() -> OrderSink | None:
    return _SINK


def note_feed(workspace_root: Path | str, note: str) -> None:
    """One line the Playground screen can show. Same text is not rewritten."""
    from lumina_core.maturity.playground.progress import (
        load_playground_progress,
        merge_playground_progress,
    )

    root = Path(workspace_root)
    text = str(note or "").strip()
    if str(load_playground_progress(root).get("feed_note") or "") == text:
        return
    merge_playground_progress(root, {"feed_note": text})


def claim_live_tick(
    workspace_root: Path | str,
    *,
    mode: str,
    price: float,
    row: dict[str, Any],
    engine: Any,
    data: list[dict[str, Any]],
    idx: int,
) -> bool:
    """Publish one SIM bar for the runner. True when Playground owns execution."""
    if not playground_owns_execution(workspace_root, mode):
        return False
    state = _load_state(Path(workspace_root))
    obs, skip = observation_for_row(
        row,
        engine=engine,
        data=data,
        idx=idx,
        position=int(state.get("position_side") or 0),
        qty=int(state.get("qty") or 0),
        entry_price=float(state.get("entry_px") or 0.0),
    )
    publish_live_bar(
        workspace_root,
        price=float(price),
        observation=obs,
        ts=datetime.now(timezone.utc).isoformat(),
        skip=skip or "obs_incomplete",
    )
    return True


def playground_owns_execution(workspace_root: Path | str, mode: str) -> bool:
    if str(mode or "").strip().lower() not in SIM_MODES:
        return False
    data = load_continuum(workspace_root)
    return str(data.get("active_phase") or "") == "playground"


def load_crawl_policy(
    workspace_root: Path | str,
    *,
    loader: Callable[[Path | str], Any | None] = load_frozen_policy,
) -> tuple[Any | None, str]:
    """Awakening child only. Birth zip and a sha mismatch never load."""
    ids = load_policy_identities(workspace_root)
    child = str(ids.get("child_sha") or "")
    awake = str(ids.get("awakening_child_sha") or "")
    birth = str(ids.get("birth_sha") or "")
    path = str(ids.get("child_zip") or "")
    if not child or not awake or not birth or not path:
        return None, "policy_sha_refused"
    if child != awake or child == birth:
        return None, "policy_sha_refused"
    model = loader(path)
    if model is None:
        return None, "policy_load_failed"
    return model, "ok"


_STRUCTURE = frozenset(
    {
        "regime",
        "open",
        "high",
        "low",
        "volume",
        "trend_slope_5",
        "bible_confluence",
        "volume_delta",
        "bid_ask_imbalance",
    }
)


def row_has_market_structure(row: dict[str, Any]) -> bool:
    """A price-only tick is not an observation. Builder defaults must not fill it."""
    for key in _STRUCTURE:
        if key in row and row.get(key) not in (None, ""):
            return True
    return False


def _tail_lines(path: Path, *, max_bytes: int = 65536) -> list[str]:
    """Last complete lines. The clock must not read the whole bars file."""
    try:
        size = path.stat().st_size
    except OSError:
        return []
    try:
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
            blob = handle.read()
    except OSError:
        return []
    lines = blob.decode("utf-8", errors="replace").splitlines()
    if size > max_bytes and lines:
        lines = lines[1:]
    return lines


def bars_are_flowing(workspace_root: Path | str, *, fresh_sec: float = 300.0) -> bool:
    path = Path(workspace_root) / BARS_REL
    if not path.is_file():
        return False
    lines = _tail_lines(path)
    for raw in reversed(lines):
        text = raw.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        stamp = str(row.get("ts") or "")
        if not stamp:
            return False
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc).timestamp() - parsed.timestamp()
        return age <= float(fresh_sec)
    return False


def last_bar_age_sec(workspace_root: Path | str) -> float | None:
    path = Path(workspace_root) / BARS_REL
    if not path.is_file():
        return None
    lines = _tail_lines(path)
    for raw in reversed(lines):
        text = raw.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        stamp = str(row.get("ts") or "")
        if not stamp:
            return None
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, datetime.now(timezone.utc).timestamp() - parsed.timestamp())
    return None


def publish_live_bar(
    workspace_root: Path | str,
    *,
    price: float,
    observation: list[float] | None,
    ts: str,
    skip: str = "",
) -> None:
    try:
        px = float(price)
    except (TypeError, ValueError):
        return
    if px <= 0.0:
        return
    path = Path(workspace_root) / BARS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"price": px, "ts": str(ts or "")}
    if observation and _obs_usable(observation):
        row["observation"] = [float(x) for x in observation]
    else:
        row["observation"] = None
        row["skip"] = skip or "obs_incomplete"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def observation_for_row(
    row: dict[str, Any],
    *,
    engine: Any,
    data: list[dict[str, Any]],
    idx: int,
    position: int,
    qty: int,
    entry_price: float,
) -> tuple[list[float] | None, str]:
    """Same builder as the eval env. A failed or all-zero vector is not an observation."""
    price = _f(row.get("close", row.get("last")))
    if price is None or price <= 0.0:
        return None, "price_missing"
    if len(data) < MIN_TREND_LOOKBACK:
        return None, "trend_window_short"
    if not _confidence_known(row, engine):
        return None, "confidence_missing"
    try:
        vec = build_observation_vector(
            row=row,
            engine=engine,
            data=data,
            idx=idx,
            position=int(position),
            qty=int(qty),
            entry_price=float(entry_price),
            equity=float(getattr(engine, "account_equity", 0.0) or 0.0),
            drawdown=0.0,
            rolling_sharpe=0.0,
            trade_mode="sim",
        )
    except Exception:
        logger.warning("playground.crawl.obs_failed", exc_info=True)
        return None, "obs_incomplete"
    values = [float(x) for x in np.asarray(vec, dtype=np.float32).reshape(-1)]
    if not _obs_usable(values):
        return None, "obs_incomplete"
    return values, ""


def _exchange_closed(ts: object) -> bool:
    """A readable closed stamp blocks the order. An unreadable stamp is not a close."""
    from lumina_core.market.globex_hours import globex_status, parse_instant

    instant = parse_instant(ts)
    if instant is None:
        return False
    return globex_status(instant) != "open"


def _minute_exit_side(
    root: Path,
    instrument: str,
    price: float,
    now_ns: int,
    state: dict[str, Any],
) -> int | None:
    """Keep the side, flatten, or ignore a print that is not the closed minute."""
    from lumina_core.market.minute_bars import load_minutes
    from lumina_core.market.nt_fees import CostCardError, spec_for
    from lumina_core.maturity.playground.research_kit import ohlc_exit

    try:
        spec = spec_for(instrument)
    except CostCardError:
        return None
    minute_ns = int(now_ns) - (int(now_ns) % 60_000_000_000)
    try:
        stored = load_minutes(root, instrument)
    except (OSError, ValueError):
        return None
    fill = next((bar for bar in stored if bar.ts_ns == minute_ns), None)
    if fill is None:
        return None
    close_px = fill.close_ticks * spec.tick_size
    if abs(float(price) - close_px) > spec.tick_size * 0.5:
        return None
    side = int(state.get("position_side") or 0)
    try:
        stop_px = float(state.get("stop_px"))
        target_px = float(state.get("target_px"))
    except (TypeError, ValueError):
        return side
    if ohlc_exit(side=side, stop_px=stop_px, target_px=target_px, bar=fill, tick_size=spec.tick_size) is not None:
        return 0
    return side


def _book_has_hand(workspace_root: Path) -> bool:
    from lumina_core.maturity.playground.learning_book import load_names

    return any(str(row.get("status") or "") == "hand" for row in load_names(workspace_root))


def _bar_ns(ts: object) -> int:
    from lumina_core.market.globex_hours import parse_instant

    instant = parse_instant(ts)
    if instant is None:
        return 0
    return int(instant.timestamp() * 1_000_000_000)


def _note_closed_print(root: Path, ts: object) -> None:
    from lumina_core.market.globex_hours import globex_status, parse_instant
    from lumina_core.maturity.playground.journal import append_experiment_entry
    from lumina_core.maturity.playground.sense_lab import load_sense, save_sense

    instant = parse_instant(ts)
    if instant is None or globex_status(instant) == "open":
        return
    state = load_sense(root)
    if state.get("unexpected_print_noted"):
        return
    append_experiment_entry(
        root,
        title="print while globex closed",
        lines=[
            f"A bar arrived at {instant.isoformat()} while the book was {globex_status(instant)}.",
            "It was kept as an observation. It was not an order.",
            "Do not re-test: trading that print, or treating the last open price as a fill inside the hole.",
        ],
    )
    state["unexpected_print_noted"] = True
    save_sense(root, state)


def advance_crawl(
    workspace_root: Path | str,
    *,
    policy: Any | None,
    place_order: OrderSink | None,
    instrument: str,
    mode: str = "sim",
    max_decisions: int | None = None,
    max_steps: int | None = None,
) -> dict[str, Any]:
    """Consume new SIM bars. One place_order per entry or exit. No tape write without a fill.

    A bar without a usable observation counts as blind, not as a decision.
    A usable bar with no order sink stays on the cursor so the next poll can send it.
    """
    root = Path(workspace_root)
    state = _load_state(root)
    state["reject_reason"] = ""
    if policy is None and not _book_has_hand(root):
        _remember_reason(root, state, "policy_unavailable")
        return _status(state, armed=False, reason="policy_unavailable", bars=0, orders_unfilled=False)
    trade_mode = str(mode or "").strip().lower()
    if trade_mode not in SIM_MODES:
        return _status(state, armed=False, reason="mode_not_sim", bars=0, orders_unfilled=False)
    bars, file_lines = _unread_bars(root, cursor=int(state.get("cursor") or 0))
    from lumina_core.maturity.playground.progress import load_playground_progress
    from lumina_core.maturity.playground.research_kit import hand_order

    seen = 0
    decisions = 0
    window_hit = False
    last_skip = ""
    stopped_at: int | None = None
    for bar in bars:
        line_no = int(bar["_line"])
        if max_steps is not None and seen >= max_steps:
            stopped_at = line_no
            break
        seen += 1
        px = float(bar["price"])
        state["live_px"] = px
        if _exchange_closed(bar.get("ts")):
            last_skip = "exchange_closed"
            _count_skip(state, last_skip)
            _note_closed_print(root, bar.get("ts"))
            continue
        obs = bar.get("observation")
        obs_ok = policy is not None and _obs_matches(policy, obs)
        flat = int(state.get("position_side") or 0) == 0
        equity = load_playground_progress(root).get("sim_equity")
        handed = None
        if flat:
            handed = hand_order(
                root,
                symbol=instrument,
                price=px,
                equity=float(equity) if equity not in (None, "") else None,
                now_ns=_bar_ns(bar.get("ts")),
            )
        if not obs_ok and handed is None and flat:
            state["blind_bars"] = int(state.get("blind_bars") or 0) + 1
            last_skip = str(bar.get("skip") or "obs_incomplete")
            _count_skip(state, last_skip)
            logger.info("playground.crawl.bar_skipped reason=%s", last_skip)
            _starve_pending(state)
            continue
        forced_flat = False
        if not flat:
            kept = _minute_exit_side(root, instrument, px, _bar_ns(bar.get("ts")), state)
            if kept is None:
                last_skip = "minute_mismatch"
                _count_skip(state, last_skip)
                continue
            forced_flat = kept == 0
        if max_decisions is not None and decisions >= max_decisions:
            stopped_at = line_no
            break
        decisions += 1
        state["total_bars"] = int(state.get("total_bars") or 0) + 1
        if int(state.get("position_side") or 0) == 0:
            state["flat_bars"] = int(state.get("flat_bars") or 0) + 1
        action = _predict_crawl_action(policy, obs) if obs_ok else None
        decoded = _decode_action(action) if action is not None else None
        if decoded is None and handed is None and flat:
            last_skip = "predict_failed" if action is None else "action_undecoded"
            _count_skip(state, last_skip)
            logger.info("playground.crawl.bar_skipped reason=%s", last_skip)
            _starve_pending(state)
            continue
        if decoded is None:
            decoded = (0, 0, 0.0, 0.0)
        side, qty, stop_pct, target_pct = decoded
        if int(state.get("position_side") or 0) == 0:
            state["hand_name"] = ""
            state["bars_in_trade"] = 0
            if handed is None:
                side = 0
            else:
                side = int(handed.side)
                qty = int(handed.qty)
                stop_pct = float(handed.stop_pct)
                target_pct = float(handed.target_pct)
                state["hand_name"] = handed.name
                state["hand_hold"] = int(handed.hold)
        else:
            state["bars_in_trade"] = int(state.get("bars_in_trade") or 0) + 1
            side = int(state.get("position_side") or 0)
            hold = int(state.get("hand_hold") or 0)
            if forced_flat or (hold > 0 and int(state["bars_in_trade"]) >= hold):
                side = 0
        needs_sink = handed is not None or int(state.get("position_side") or 0) != 0
        if needs_sink and place_order is None:
            last_skip = "order_sink_missing"
            stopped_at = line_no
            break
        if action is not None:
            state["last_action0"] = float(action.reshape(-1)[0])
        state["last_policy_side"] = int(side)
        state["reject_reason"] = ""
        window_hit = _act(
            root,
            state,
            place_order=place_order,
            instrument=instrument,
            mode=trade_mode,
            price=px,
            side=side,
            qty=qty,
            stop_pct=stop_pct,
            target_pct=target_pct,
        ) or window_hit
        if state.get("reject_reason"):
            last_skip = str(state["reject_reason"])
            _count_skip(state, last_skip)
    state["cursor"] = stopped_at if stopped_at is not None else file_lines
    if window_hit:
        state["unfilled_edge_seq"] = int(state.get("unfilled_edge_seq") or 0) + 1
    reason = str(state.get("reject_reason") or "") or last_skip or ("crawl" if seen else "no_bar")
    state["last_reason"] = reason
    write_occupancy(
        root,
        flat_bars=int(state.get("flat_bars") or 0),
        total_bars=int(state.get("total_bars") or 0),
        live_px=_f(state.get("live_px")),
    )
    _save_state(root, state)
    return _status(state, armed=True, reason=reason, bars=seen, orders_unfilled=window_hit)


def last_policy_decision(workspace_root: Path | str) -> dict[str, Any]:
    """Last decoded policy action. Absent until a real decision. Not an order."""
    state = _load_state(Path(workspace_root))
    return {
        "total_bars": int(state.get("total_bars") or 0),
        "action0": state.get("last_action0"),
        "side": state.get("last_policy_side"),
    }


def crawl_totals(workspace_root: Path | str) -> dict[str, int]:
    state = _load_state(Path(workspace_root))
    return {
        "total_bars": int(state.get("total_bars") or 0),
        "flat_bars": int(state.get("flat_bars") or 0),
        "blind_bars": int(state.get("blind_bars") or 0),
    }


def unfilled_edge_seq(workspace_root: Path | str) -> int:
    return int(_load_state(Path(workspace_root)).get("unfilled_edge_seq") or 0)


def watch_crawl(workspace_root: Path | str, *, seen_seq: int) -> tuple[dict[str, Any], int]:
    """Read the engine's crawl. This process does not move the cursor."""
    root = Path(workspace_root)
    state = _load_state(root)
    age = last_bar_age_sec(root)
    if age is None or age > 30.0:
        reason = "supervisor_not_publishing"
    else:
        reason = str(state.get("last_reason") or "crawl")
    seq = int(state.get("unfilled_edge_seq") or 0)
    edge = seq > int(seen_seq)
    status = _status(state, armed=True, reason=reason, bars=0, orders_unfilled=edge)
    return status, seq


_POLICY_BY_SHA: dict[str, Any] = {}


def cached_crawl_policy(workspace_root: Path | str) -> tuple[Any | None, str]:
    ids = load_policy_identities(workspace_root)
    child = str(ids.get("child_sha") or "")
    cached = _POLICY_BY_SHA.get(child)
    if child and cached is not None:
        return cached, "ok"
    model, reason = load_crawl_policy(workspace_root)
    if model is not None and child:
        _POLICY_BY_SHA[child] = model
    return model, reason


def _bar_epoch(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def skip_stale_backlog(workspace_root: Path | str, *, fresh_sec: float = 180.0) -> int:
    """Move the cursor past bars that are too old to send.

    Those bars stay in the jsonl. They are not decisions and they place no order.
    A fresh bar stays on the cursor for the one live decision.
    """
    root = Path(workspace_root)
    state = _load_state(root)
    bars, file_lines = _unread_bars(root, cursor=int(state.get("cursor") or 0))
    if not bars:
        return 0
    now = datetime.now(timezone.utc).timestamp()
    skipped = 0
    fresh_at: int | None = None
    for bar in bars:
        age = _bar_epoch(bar.get("ts"))
        if age is not None and (now - age) <= float(fresh_sec):
            fresh_at = int(bar["_line"])
            break
        skipped += 1
    if skipped <= 0:
        return 0
    book = state.get("skip_counts")
    if not isinstance(book, dict):
        book = {}
        state["skip_counts"] = book
    book["stale_backlog"] = int(book.get("stale_backlog") or 0) + skipped
    state["blind_bars"] = int(state.get("blind_bars") or 0) + skipped
    state["cursor"] = file_lines if fresh_at is None else fresh_at
    state["last_reason"] = "stale_backlog"
    _save_state(root, state)
    logger.info("playground.crawl.stale_backlog skipped=%s cursor=%s", skipped, state["cursor"])
    return skipped


def drive_crawl_from_engine(workspace_root: Path | str, *, mode: str) -> dict[str, Any]:
    """The engine owns place_order. One decision per call. Waiting does not trade the backlog."""
    root = Path(workspace_root)
    rebase_blind_denominator(root)
    if not playground_owns_execution(root, mode):
        return _status(_empty_state(), armed=False, reason="not_playground", bars=0, orders_unfilled=False)
    from lumina_core.maturity.playground.habitat import waiting_operator
    from lumina_core.maturity.playground.progress import load_playground_progress

    prog = load_playground_progress(root)
    paused = bool(prog.get("paused"))
    if paused or waiting_operator(root):
        reason = "paused" if paused else "waiting_operator"
        return _status(_load_state(root), armed=True, reason=reason, bars=0, orders_unfilled=False)
    listing = str(prog.get("chart_listing") or "").strip()
    from lumina_core.maturity.playground.learning_book import read_header

    root_symbol = listing or str(read_header(root).get("symbol") or "")
    rolled = live_listing(root_symbol)
    if rolled:
        listing = rolled
    policy, _reason = cached_crawl_policy(root)
    skip_stale_backlog(root)
    return advance_crawl(
        root,
        policy=policy,
        place_order=current_order_sink(),
        instrument=listing,
        mode=mode,
        max_decisions=1,
        max_steps=30,
    )


def rebase_blind_denominator(workspace_root: Path | str) -> bool:
    """One correction: blind bars leave the decision denominator. The jsonl stays. Cursor stays."""
    root = Path(workspace_root)
    state = _load_state(root)
    if state.get("sensor_denominator_corrected"):
        return False
    total = int(state.get("total_bars") or 0)
    if total <= 0:
        return False
    from lumina_core.maturity.playground.tape import tape_skill_metrics

    n_p = int(tape_skill_metrics(root).get("n_p") or 0)
    skips = state.get("skip_counts") if isinstance(state.get("skip_counts"), dict) else {}
    blind_named = int(skips.get("obs_incomplete") or 0)
    poisoned = n_p == 0 and blind_named >= 0.9 * float(total)
    state["sensor_denominator_corrected"] = True
    if not poisoned:
        _save_state(root, state)
        return False
    state["blind_bars"] = int(state.get("blind_bars") or 0) + total
    state["total_bars"] = 0
    state["flat_bars"] = 0
    _save_state(root, state)
    write_occupancy(root, flat_bars=0, total_bars=0, live_px=_f(state.get("live_px")))
    from lumina_core.maturity.playground.journal import append_experiment_entry
    from lumina_core.maturity.playground.progress import merge_playground_progress

    merge_playground_progress(root, {"occupancy": None})
    append_experiment_entry(
        root,
        title="sensor denominator",
        lines=[
            f"blind_bars: {state['blind_bars']}",
            "decision bars reset to 0",
            "n_p stayed 0",
            "bars jsonl kept",
            "cursor kept",
            "occupancy missing until a real decision bar",
            "not a pass",
        ],
    )
    return True


def engine_ohlc_rows(engine: Any) -> list[dict[str, Any]]:
    """Closed 1-minute bars plus the candle that is still forming. At most 120 rows."""
    frame = getattr(engine, "ohlc_1min", None)
    lock = getattr(engine, "live_data_lock", None)
    current = getattr(engine, "current_candle", None)
    try:
        if lock is not None:
            with lock:
                records = _frame_records(frame)
                current = getattr(engine, "current_candle", None)
        else:
            records = _frame_records(frame)
    except Exception:
        logger.warning("playground.crawl.ohlc_failed", exc_info=True)
        return []
    rows = [row for row in (_ohlc_row(rec) for rec in records) if row is not None]
    if isinstance(current, dict):
        live = _ohlc_row(current)
        if live is not None:
            rows.append(live)
    if len(rows) > 120:
        return rows[-120:]
    return rows


def _fill_count(root: Path) -> int:
    from lumina_core.maturity.playground.tape import load_tape_rows

    return sum(1 for row in load_tape_rows(root) if str(row.get("kind") or "") == "fill")


def _act(
    root: Path,
    state: dict[str, Any],
    *,
    place_order: OrderSink,
    instrument: str,
    mode: str,
    price: float,
    side: int,
    qty: int,
    stop_pct: float,
    target_pct: float,
) -> bool:
    held = int(state.get("position_side") or 0)
    if held == 0 and side == 0:
        return False
    if held == 0 and side != 0:
        if stop_pct <= 0.0 or target_pct <= 0.0:
            logger.info("playground.crawl.bar_skipped reason=stop_missing")
            state["reject_reason"] = "stop_missing"
            return False
        stop_px = price * (1.0 - stop_pct) if side > 0 else price * (1.0 + stop_pct)
        target_px = price * (1.0 + target_pct) if side > 0 else price * (1.0 - target_pct)
        filled = _submit(
            place_order,
            action="BUY" if side > 0 else "SELL",
            qty=qty,
            stop_px=stop_px,
            target_px=target_px,
            instrument=instrument,
        )
        if filled is None:
            state["pending_unfilled"] = True
            state["bars_since_unfilled"] = int(state.get("bars_since_unfilled") or 0) + 1
            state["reject_reason"] = take_order_reject() or "place_order_rejected"
            if _fill_count(root) > int(state.get("fills_seen") or 0):
                state["reject_reason"] = "fill_without_position"
            state["fills_seen"] = _fill_count(root)
            return _window_ready(state)
        state["pending_unfilled"] = False
        state["bars_since_unfilled"] = 0
        state["reject_reason"] = ""
        state["fills_seen"] = _fill_count(root)
        state["position_side"] = side
        state["entry_px"] = filled["fill_px"]
        state["entry_order_id"] = filled["order_id"]
        state["stop_px"] = filled["stop_px"]
        state["target_px"] = target_px
        state["qty"] = qty
        state["last_order_id"] = filled["order_id"]
        return False
    if held == 0:
        return False
    stop_px = _f(state.get("stop_px"))
    target_px = _f(state.get("target_px"))
    entry_px = _f(state.get("entry_px"))
    hit = _exit_due(price=price, side=held, stop_px=stop_px, target_px=target_px, action_side=side)
    if not hit:
        return False
    if stop_px is None or entry_px is None:
        logger.info("playground.crawl.exit_skipped reason=stop_missing")
        state["reject_reason"] = "stop_missing"
        return False
    exit_action = "SELL" if held > 0 else "BUY"
    filled = _submit(
        place_order,
        action=exit_action,
        qty=int(state.get("qty") or 1),
        stop_px=float(stop_px),
        target_px=float(target_px or price),
        instrument=instrument,
    )
    if filled is None:
        state["pending_unfilled"] = True
        state["bars_since_unfilled"] = int(state.get("bars_since_unfilled") or 0) + 1
        state["reject_reason"] = take_order_reject() or "place_order_rejected"
        return _window_ready(state)
    close = record_policy_close(
        root,
        order_id=str(filled["order_id"]),
        entry_px=float(entry_px),
        exit_px=float(filled["fill_px"]),
        stop_px=float(filled["stop_px"]),
        target_px=_f(state.get("target_px")),
        side=held,
        qty=int(state.get("qty") or 1),
        instrument=instrument,
        mode=mode,
        source="ops_place_order",
        rule_name=str(state.get("hand_name") or ""),
    )
    state["last_order_id"] = str(filled["order_id"])
    if not close.get("ok"):
        logger.info("playground.crawl.close_refused reason=%s", close.get("reason"))
        return False
    state["pending_unfilled"] = False
    state["bars_since_unfilled"] = 0
    state["position_side"] = 0
    state["entry_px"] = None
    state["entry_order_id"] = ""
    state["stop_px"] = None
    state["target_px"] = None
    state["qty"] = 0
    return False


def _submit(
    place_order: OrderSink,
    *,
    action: str,
    qty: int,
    stop_px: float,
    target_px: float,
    instrument: str,
) -> dict[str, Any] | None:
    intent = {
        "action": action,
        "qty": int(qty),
        "stop_px": float(stop_px),
        "target_px": float(target_px),
        "instrument": instrument,
    }
    token = _INTENT.set(intent)
    try:
        result = place_order(
            action=action,
            qty=int(qty),
            stop_px=float(stop_px),
            target_px=float(target_px),
            instrument=instrument,
        )
    finally:
        _INTENT.reset(token)
    if not isinstance(result, dict) or not result.get("ok"):
        if not _REJECT.get():
            reason = str(result.get("reason") or "") if isinstance(result, dict) else ""
            note_order_reject(reason or "place_order_rejected")
        return None
    oid = str(result.get("order_id") or "").strip()
    try:
        fill_px = float(result.get("fill_px"))
        used_stop = float(result.get("stop_px"))
    except (TypeError, ValueError):
        return None
    if not oid or fill_px <= 0.0 or used_stop <= 0.0:
        return None
    return {"order_id": oid, "fill_px": fill_px, "stop_px": used_stop}


def _exit_due(
    *,
    price: float,
    side: int,
    stop_px: float | None,
    target_px: float | None,
    action_side: int,
) -> bool:
    if action_side == 0 or action_side == -side:
        return True
    if stop_px is None or target_px is None:
        return False
    if side > 0:
        return price <= stop_px or price >= target_px
    return price >= stop_px or price <= target_px


def _predict_crawl_action(policy: Any, obs: Any) -> np.ndarray | None:
    """Policy forward. An exception is not a HOLD and not the Birth fallback action."""
    predict = getattr(policy, "predict", None)
    if not callable(predict):
        return None
    try:
        raw = predict(np.asarray(obs, dtype=np.float32).reshape(1, -1), deterministic=True)
    except Exception:
        logger.warning("playground.crawl.predict_failed", exc_info=True)
        return None
    action = raw[0] if isinstance(raw, (tuple, list)) and len(raw) >= 1 else raw
    try:
        return np.asarray(action, dtype=np.float32).reshape(-1)
    except (TypeError, ValueError):
        return None


def _count_skip(state: dict[str, Any], reason: str) -> None:
    if not reason:
        return
    book = state.get("skip_counts")
    if not isinstance(book, dict):
        book = {}
        state["skip_counts"] = book
    book[str(reason)] = int(book.get(str(reason)) or 0) + 1


def _decode_action(action: np.ndarray) -> tuple[int, int, float, float] | None:
    arr = np.asarray(action, dtype=np.float32).reshape(-1)
    if arr.size < 4:
        return None
    bucket = int(np.clip(np.round(float(arr[0])), 0, 2))
    side = 0 if bucket == 0 else (1 if bucket == 1 else -1)
    qty = max(1, int(1 + float(np.clip(arr[1], 0.0, 1.0)) * 9))
    return side, qty, float(arr[2]), float(arr[3])


def _obs_usable(values: list[float] | None) -> bool:
    if not values:
        return False
    try:
        nums = [float(x) for x in values]
    except (TypeError, ValueError):
        return False
    if not nums or all(x == 0.0 for x in nums):
        return False
    return True


def _obs_matches(policy: Any, obs: Any) -> bool:
    if not isinstance(obs, list) or not _obs_usable(obs):
        return False
    space = getattr(policy, "observation_space", None)
    shape = getattr(space, "shape", None)
    if not shape:
        return True
    return len(obs) == int(shape[-1])


def _starve_pending(state: dict[str, Any]) -> None:
    if state.get("pending_unfilled"):
        state["bars_since_unfilled"] = int(state.get("bars_since_unfilled") or 0) + 1


def _window_ready(state: dict[str, Any]) -> bool:
    if int(state.get("bars_since_unfilled") or 0) < FILL_STARVE_BARS:
        return False
    state["bars_since_unfilled"] = 0
    return True


def _unread_bars(root: Path, *, cursor: int) -> tuple[list[dict[str, Any]], int]:
    path = root / BARS_REL
    if not path.is_file():
        return [], cursor
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], cursor
    out: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if index < max(0, cursor):
            continue
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        try:
            px = float(row.get("price"))
        except (TypeError, ValueError):
            continue
        if px <= 0.0:
            continue
        row["price"] = px
        row["_line"] = index
        out.append(row)
    return out, len(lines)


def _load_state(root: Path) -> dict[str, Any]:
    path = root / CRAWL_REL
    if not path.is_file():
        return _empty_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty_state()
    if not isinstance(raw, dict):
        return _empty_state()
    base = _empty_state()
    base.update(raw)
    return base


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / CRAWL_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(state, ensure_ascii=True, indent=2) + "\n")


def _empty_state() -> dict[str, Any]:
    return {
        "cursor": 0,
        "flat_bars": 0,
        "total_bars": 0,
        "live_px": None,
        "position_side": 0,
        "entry_px": None,
        "entry_order_id": "",
        "stop_px": None,
        "target_px": None,
        "qty": 0,
        "pending_unfilled": False,
        "bars_since_unfilled": 0,
        "last_order_id": "",
        "reject_reason": "",
        "fills_seen": 0,
        "skip_counts": {},
        "blind_bars": 0,
        "last_reason": "",
        "unfilled_edge_seq": 0,
        "sensor_denominator_corrected": False,
    }


def _status(
    state: dict[str, Any],
    *,
    armed: bool,
    reason: str,
    bars: int,
    orders_unfilled: bool,
) -> dict[str, Any]:
    return {
        "armed": armed,
        "reason": reason,
        "bars": int(bars),
        "orders_unfilled": bool(orders_unfilled),
        "last_order_id": str(state.get("last_order_id") or ""),
        "flat_bars": int(state.get("flat_bars") or 0),
        "total_bars": int(state.get("total_bars") or 0),
        "blind_bars": int(state.get("blind_bars") or 0),
        "skip_counts": dict(state.get("skip_counts") or {}),
    }


def _remember_reason(root: Path, state: dict[str, Any], reason: str) -> None:
    if str(state.get("last_reason") or "") == reason:
        return
    state["last_reason"] = reason
    _save_state(root, state)


def _confidence_known(row: dict[str, Any], engine: Any) -> bool:
    dream: dict[str, Any] = {}
    if hasattr(engine, "get_current_dream_snapshot"):
        raw = engine.get_current_dream_snapshot()
        if isinstance(raw, dict):
            dream = raw
    for source in (row, dream):
        for key in ("bible_confluence", "confluence_score", "confidence"):
            if _f(source.get(key)) is not None:
                return True
    return False


def _frame_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    tail = frame.tail(120).copy() if hasattr(frame, "tail") else frame
    if hasattr(tail, "to_dict"):
        raw = tail.to_dict(orient="records")
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(tail, list):
        return [row for row in tail if isinstance(row, dict)]
    return []


def _ohlc_row(rec: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(rec, dict):
        return None
    try:
        from lumina_core.engine.nt_bar_ssot import validate_nt_bar

        bar = validate_nt_bar(rec)
    except Exception:
        return None
    return {
        "timestamp": bar["timestamp"],
        "open": bar["open"],
        "high": bar["high"],
        "low": bar["low"],
        "close": bar["close"],
        "last": bar["close"],
        "volume": bar["volume"],
    }


def _f(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number
