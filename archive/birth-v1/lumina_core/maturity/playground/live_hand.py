"""Engine hand for the Playground crawl.

The API clock watches. This module is the only place the engine publishes a
closed bar and asks the crawl for one decision. It does not start REAL, and it
does not kill NinjaTrader.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.playground.crawl import (
    bind_app_order_sink,
    crawl_totals,
    drive_crawl_from_engine,
    engine_ohlc_rows,
    last_policy_decision,
    observation_for_row,
    playground_owns_execution,
    publish_live_bar,
    _load_state,
    _ohlc_row,
)
from lumina_core.maturity.playground.portfolio_seal import cached_sim_account, floor_mode

logger = get_logger("lumina.maturity.playground.live_hand")


def on_closed_candle(
    workspace_root: Path | str,
    engine: Any,
    app: Any,
    candle: dict[str, Any],
    *,
    mode: str,
) -> None:
    """Publish one closed SIM candle and take at most one crawl decision."""
    root = Path(workspace_root)
    trade_mode = str(mode or "").strip().lower()
    if not playground_owns_execution(root, trade_mode):
        return
    closed = _ohlc_row(candle if isinstance(candle, dict) else {})
    if closed is None:
        return
    from lumina_core.engine.ohlc_clock import iso_z, utc_from_any

    ts = utc_from_any(
        closed.get("timestamp")
        or (candle.get("timestamp") if isinstance(candle, dict) else None)
        or (candle.get("timestamp_unix_ms") if isinstance(candle, dict) else None)
    )
    if ts is None:
        logger.warning("playground.live_hand.bar_timestamp_missing")
        return
    price = float(closed["close"])
    bind_app_order_sink(app)
    _apply_live_equity(engine, app, root)
    _archive_closed_minute(root, closed, ts)
    rows = list(engine_ohlc_rows(engine))
    if not rows or float(rows[-1].get("close") or 0.0) != price:
        rows.append(closed)
    if len(rows) > 120:
        rows = rows[-120:]
    state = _load_state(root)
    obs, skip = observation_for_row(
        closed,
        engine=engine,
        data=rows,
        idx=max(0, len(rows) - 1),
        position=int(state.get("position_side") or 0),
        qty=int(state.get("qty") or 0),
        entry_price=float(state.get("entry_px") or 0.0),
    )
    bar_ts = iso_z(ts)
    publish_live_bar(
        root,
        price=price,
        observation=obs,
        ts=bar_ts,
        skip="" if obs else (skip or "obs_incomplete"),
    )
    before_bars = crawl_totals(root)["total_bars"]
    try:
        drive_crawl_from_engine(root, mode=trade_mode)
    except Exception:
        logger.warning("playground.live_hand.drive_failed", exc_info=True)
    _observe_sense(root, ts=bar_ts, close=price, before_bars=before_bars, engine=engine)
    from lumina_core.maturity.playground.progress import merge_playground_progress

    merge_playground_progress(root, {"last_px": price, "last_px_at": ts.timestamp()})


def _native_htf_closes(engine: Any) -> dict[str, list[float]]:
    md = getattr(engine, "market_data", None)
    copy_period = getattr(md, "copy_ohlc_period", None)
    out: dict[str, list[float]] = {}
    if copy_period is None:
        return out
    for period in ("5m", "60m", "240m"):
        frame = copy_period(period, forming=False)
        if frame is None or len(frame) < 2:
            continue
        out[period] = [float(frame["close"].iloc[-2]), float(frame["close"].iloc[-1])]
    return out


def _observe_sense(root: Path, *, ts: str, close: float, before_bars: int, engine: Any = None) -> None:
    """Shadow book only. A failure here must not change the order the crawl already sent."""
    try:
        from lumina_core.maturity.playground.sense_lab import observe_closed_bar

        decision = None
        after = last_policy_decision(root)
        if int(after.get("total_bars") or 0) > int(before_bars):
            decision = after
        observe_closed_bar(
            root,
            ts=ts,
            close=close,
            decision=decision,
            native_htf=_native_htf_closes(engine),
        )
    except Exception:
        logger.warning("playground.live_hand.sense_failed", exc_info=True)


def note_market_view(
    workspace_root: Path | str,
    *,
    charts: list[str],
    listing: str,
    source: str,
    seal_note: str,
    last_px: float | None,
) -> None:
    """One Dutch line. Same text is not rewritten."""
    root = Path(workspace_root)
    if not playground_owns_execution(root, "sim") and not playground_owns_execution(root, "sim_real_guard"):
        return
    from lumina_core.broker.ninjatrader.open_charts import world_sentence
    from lumina_core.maturity.playground.crawl import note_feed
    from lumina_core.maturity.playground.progress import merge_playground_progress

    names = [str(item) for item in charts if str(item).strip()]
    merge_playground_progress(
        root,
        {
            "open_charts": names,
            "chart_listing": str(listing or ""),
            "chart_source": str(source or ""),
            "seal_note": str(seal_note or ""),
        },
    )
    note_feed(
        root,
        world_sentence(
            charts=names,
            source=str(source or ""),
            listing=str(listing or ""),
            seal_note=str(seal_note or ""),
            last_px=last_px if last_px is not None and last_px > 0.0 else None,
        ),
    )


def ensure_sim_runtime(workspace_root: Path | str) -> str:
    """Start the SIM engine when Playground is opened. A live engine is left alone."""
    root = Path(workspace_root)
    mode = floor_mode(None, root)
    from lumina_core.maturity.playground.crawl import note_feed

    if mode != "sim":
        note_feed(root, "Playground start weigert. De runtime blijft uit zolang de modus niet SIM is.")
        return "refused_not_sim"
    try:
        from lumina_launcher.core.process_manager import ProcessManager

        manager = ProcessManager(root, Path("lumina_core/engine/runtime_entrypoint.py"))
        if manager.is_process_alive():
            note_feed(root, "SIM-engine draait al. De crawl beslist op de volgende gesloten candle.")
            return "already_running"
        ok, message = manager.start_bot(mode="sim")
    except Exception as exc:
        logger.warning("playground.live_hand.runtime_start_failed", exc_info=True)
        note_feed(root, f"SIM-engine startte niet: {exc}")
        return "start_failed"
    if not ok:
        note_feed(root, f"SIM-engine startte niet: {message}")
        return "start_failed"
    note_feed(root, f"SIM-engine gestart. {message}")
    return "started"


def _archive_closed_minute(root: Path, closed: dict[str, Any], ts: Any) -> None:
    """Keep the closed minute. A shut book does not append and does not delete."""
    from lumina_core.market.globex_hours import globex_status
    from lumina_core.market.minute_bars import BarArchiveError, append_minute

    if globex_status(ts) != "open":
        return
    try:
        append_minute(
            root,
            str(closed.get("instrument") or "MES"),
            ts_ns=int(ts.timestamp() * 1_000_000_000),
            open_px=float(closed["open"]),
            high_px=float(closed["high"]),
            low_px=float(closed["low"]),
            close_px=float(closed["close"]),
            volume=int(closed.get("volume") or 0),
            market_open=True,
        )
    except (BarArchiveError, KeyError, TypeError, ValueError):
        logger.warning("playground.live_hand.bar_archive_refused", exc_info=True)
        return
    from lumina_core.market.minute_bars import load_minutes
    from lumina_core.maturity.playground.research_kit import on_closed_minute

    stored = [bar for bar in load_minutes(root, str(closed.get("instrument") or "MES")) if bar.ts_ns == int(ts.timestamp() * 1_000_000_000)]
    if stored:
        on_closed_minute(root, str(closed.get("instrument") or "MES"), stored[-1], market_open=True)


def _apply_live_equity(engine: Any, app: Any, root: Path) -> None:
    account = cached_sim_account()
    if account is None or account.equity is None or account.equity <= 0.0:
        return
    equity = float(account.equity)
    engine.account_equity = equity
    from lumina_core.maturity.playground.progress import merge_playground_progress

    merge_playground_progress(root, {"sim_equity": equity})
    if account.cash is not None and account.cash > 0.0:
        engine.account_balance = float(account.cash)
    if app is None:
        return
    app.account_equity = equity
    if account.cash is not None and account.cash > 0.0:
        app.account_balance = float(account.cash)
