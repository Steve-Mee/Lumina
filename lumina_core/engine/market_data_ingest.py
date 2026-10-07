from __future__ import annotations
import logging

import asyncio
import json
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import requests
import websockets
from websockets.exceptions import ConnectionClosed
from datetime import datetime, timezone
from .errors import ErrorSeverity, LuminaError, log_structured
from .tape_reading_agent import TapeReadingAgent
from lumina_core.sla_config import market_data_latency_sla_ms

from .lumina_engine import LuminaEngine


def _mds():
    """Late-bind façade module so monkeypatches on market_data_service apply."""
    from lumina_core.engine import market_data_service as mds

    return mds


@dataclass(slots=True)
class MarketDataIngestCore:
    """Websocket/live market-data ingestion (history lives in MarketDataHistoryMixin)."""

    engine: LuminaEngine
    tape_agent: TapeReadingAgent = field(default_factory=TapeReadingAgent)
    latency_sla_ms: float = 250.0
    latency_window: deque[float] = field(default_factory=lambda: deque(maxlen=50))
    _sla_breach_streak: int = 0
    _sla_recovery_streak: int = 0
    last_requested_instrument: str = ""
    last_resolved_instrument: str = ""

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("MarketDataIngestService requires a LuminaEngine")
        self.latency_sla_ms = float(market_data_latency_sla_ms())

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    @staticmethod
    def _extract_numeric(payload: dict[str, Any], keys: tuple[str, ...], default: float = 0.0) -> float:
        for key in keys:
            value = payload.get(key)
            if key in payload and value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return float(default)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return str(symbol).strip().upper()

    def _set_fast_path_only(self, enabled: bool, reason: str) -> None:
        app = self._app()
        current = bool(getattr(app, "FAST_PATH_ONLY", False))
        if current == enabled:
            return
        setattr(app, "FAST_PATH_ONLY", enabled)
        state = "enabled" if enabled else "disabled"
        app.logger.warning(f"FAST_PATH_ONLY {state} (market data): {reason}")

    def _record_latency(self, elapsed_ms: float, source: str) -> None:
        app = self._app()
        self.latency_window.append(float(elapsed_ms))

        if elapsed_ms > self.latency_sla_ms:
            self._sla_breach_streak += 1
            self._sla_recovery_streak = 0
            if self._sla_breach_streak >= 3:
                self._set_fast_path_only(
                    True,
                    f"{source} latency {elapsed_ms:.1f}ms above SLA {self.latency_sla_ms:.1f}ms",
                )
        else:
            self._sla_recovery_streak += 1
            self._sla_breach_streak = 0
            if self._sla_recovery_streak >= 5:
                self._set_fast_path_only(False, f"{source} latency recovered ({elapsed_ms:.1f}ms)")

        avg_latency = sum(self.latency_window) / max(1, len(self.latency_window))
        setattr(app, "MARKET_DATA_LATENCY_MS", round(avg_latency, 2))

    def _publish_tape_signal(self, tape_signal: dict[str, Any]) -> None:
        blackboard = getattr(self.engine, "blackboard", None)
        if blackboard is None or not hasattr(blackboard, "add_proposal"):
            return
        tape_payload = {
            "tape_signal": str(tape_signal.get("signal", "HOLD")),
            "tape_direction": str(tape_signal.get("direction", "NEUTRAL")),
            "tape_confidence": float(tape_signal.get("confidence", 0.0) or 0.0),
            "tape_reason": str(tape_signal.get("reason", "")),
            "tape_fast_path_trigger": bool(tape_signal.get("fast_path_trigger", False)),
            "cumulative_delta_10": float(tape_signal.get("cumulative_delta_10", 0.0) or 0.0),
            "bid_ask_imbalance": float(tape_signal.get("bid_ask_imbalance", 1.0) or 1.0),
        }
        try:
            blackboard.add_proposal(
                topic="agent.tape.proposal",
                producer="market_data_service",
                payload=tape_payload,
                confidence=float(tape_signal.get("confidence", 0.0) or 0.0),
            )
            blackboard.publish_sync(
                topic="market.tape",
                producer="market_data_service",
                payload=dict(tape_signal),
                confidence=float(tape_signal.get("confidence", 0.0) or 0.0),
            )
        except Exception as _exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/market_data_ingest.py")
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="MDS_TAPE_PUBLISH_001",
                message=str(_exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            return

    def _live_provider(self) -> str:
        """fabric | crosstrade for live quotes (Fabric default — ADR-0040)."""
        cfg = getattr(self.engine, "config", None)
        provider = str(getattr(cfg, "broker_live_provider", "") or "").strip().lower()
        if provider in {"ninjatrader", "nt", "fabric"}:
            return "fabric"
        try:
            from lumina_core.engine.engine_config_helpers import (
                _config_yaml_nested,
                clear_yaml_config_cache,
            )

            clear_yaml_config_cache()
            yaml_lp = str(_config_yaml_nested("", "broker", "live_provider") or "").strip().lower()
            if yaml_lp in {"ninjatrader", "nt", "fabric"}:
                return "fabric"
            if yaml_lp == "crosstrade":
                return "crosstrade"
        except Exception:
            yaml_lp = ""
        env_lp = str(__import__("os").getenv("BROKER_LIVE_PROVIDER") or "").strip().lower()
        if env_lp in {"ninjatrader", "nt", "fabric"}:
            return "fabric"
        # Explicit Crosstrade only — never silent default to CT (ADR-0040).
        if provider == "crosstrade" or env_lp == "crosstrade":
            return "crosstrade"
        return "fabric"

    @staticmethod
    def _quote_ts(quote: dict[str, Any]) -> datetime:
        from lumina_core.engine.ohlc_clock import utc_from_any, utc_from_unix_ms

        ts = utc_from_unix_ms(quote.get("timestamp_unix_ms"))
        if ts is not None:
            return ts
        ts = utc_from_any(quote.get("timestamp"))
        if ts is not None:
            return ts
        return datetime.now(timezone.utc)

    def _drain_nt_bars(self, app: Any, client: Any, workspace: Any) -> None:
        """Apply queued native NT Last bars. Quotes never close candles."""
        take = getattr(client, "take_bar", None)
        if take is None:
            return
        from lumina_core.engine.nt_bar_periods import canonicalize_period
        from lumina_core.engine.nt_bar_ssot import BarRejected, is_recent_closed_bar
        from lumina_core.engine.ohlc_clock import iso_z

        swarm_manager = getattr(app, "swarm_manager", None)
        for _ in range(20_000):
            bar = take()
            if not bar:
                break
            inst = str(bar.get("instrument") or "").strip().upper()
            period = canonicalize_period(bar.get("bar_period") or "1m") or "1m"
            bar["bar_period"] = period
            closed = None
            try:
                if swarm_manager is not None and hasattr(swarm_manager, "apply_nt_bar"):
                    swarm_manager.apply_nt_bar(inst, bar)
                closed = self.engine.market_data.apply_nt_bar(bar)
            except BarRejected as exc:
                app.logger.warning(
                    "nt.bar.rejected code=%s inst=%s period=%s",
                    getattr(exc, "code", ""),
                    inst,
                    period,
                )
                continue
            if closed is None:
                continue
            if period != "1m":
                continue
            ts = closed.get("timestamp")
            try:
                live = is_recent_closed_bar(ts)
            except (TypeError, ValueError):
                live = False
            if not live:
                continue
            try:
                from lumina_core.maturity.playground.live_hand import on_closed_candle

                on_closed_candle(
                    workspace,
                    self.engine,
                    app,
                    closed,
                    mode=str(getattr(self.engine.config, "trade_mode", "sim")),
                )
            except Exception:
                app.logger.debug("playground.candle_hand_failed", exc_info=True)
            try:
                stamp = iso_z(ts) if ts is not None else ""
            except Exception:
                stamp = str(ts)
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message=(
                        f"[{stamp}] NT {period} bar closed -> "
                        f"O={closed['open']:.2f} H={closed['high']:.2f} "
                        f"L={closed['low']:.2f} C={closed['close']:.2f} "
                        f"V={closed['volume']}"
                    ),
                    context={"source": "nt_bars_request"},
                )
            )

    def _hydrate_native_periods(self, app: Any, client: Any, instrument: str) -> None:
        """Closed history for every native TF. Live Update still owns the forming bar."""
        fetch = getattr(client, "request_historical_data", None)
        if fetch is None or not instrument:
            return
        from lumina_core.engine.nt_bar_periods import CANONICAL_LIVE, live_bars_back
        from lumina_core.engine.nt_bar_ssot import BarRejected

        for period in CANONICAL_LIVE:
            try:
                resp = fetch(
                    instrument=instrument,
                    bar_period=period,
                    max_bars=live_bars_back(period),
                )
            except Exception:
                app.logger.debug("fabric.live.hydrate_rpc_failed period=%s", period, exc_info=True)
                continue
            code = str((resp or {}).get("code") or "").lower()
            if code not in {"ok", "success"}:
                app.logger.warning(
                    "fabric.live.hydrate_rejected period=%s code=%s",
                    period,
                    (resp or {}).get("code"),
                )
                continue
            for raw in (resp or {}).get("bars") or []:
                raw = dict(raw)
                raw["bar_period"] = period
                try:
                    self.engine.market_data.apply_nt_bar(raw)
                except BarRejected:
                    continue

    def _reconcile_nt_book(self, app: Any, client: Any, instrument: str) -> None:
        from datetime import datetime, timezone

        from lumina_core.engine.bar_integrity import reconcile_against_nt, tape_is_live
        from lumina_core.engine.nt_bar_ssot import BarRejected

        md = self.engine.market_data
        closed = md.copy_ohlc()
        local_ts = []
        if closed is not None and not closed.empty:
            local_ts = list(closed["timestamp"])
        last_ms = 0
        if local_ts:
            from lumina_core.engine.ohlc_clock import utc_from_any as _utc

            parsed = _utc(local_ts[-1])
            if parsed is not None:
                last_ms = int(parsed.timestamp() * 1000)
        now = datetime.now(timezone.utc)
        quotes_live = tape_is_live(md.live_quotes, now)
        fetch = getattr(client, "request_historical_data", None)
        nt_ok = False
        rows: list[dict[str, Any]] = []
        if fetch is not None and instrument:
            try:
                from lumina_core.engine.nt_bar_periods import live_bars_back

                resp = fetch(
                    instrument=instrument,
                    bar_period="1m",
                    start_unix_ms=last_ms,
                    end_unix_ms=int(now.timestamp() * 1000),
                    max_bars=live_bars_back("1m") if last_ms <= 0 else 180,
                )
                code = str((resp or {}).get("code") or "").lower()
                nt_ok = code in {"ok", "success"}
                rows = list((resp or {}).get("bars") or [])
            except Exception:
                nt_ok = False
                rows = []
        status, missing = reconcile_against_nt(
            local_closed=list(local_ts),
            nt_rows=rows,
            nt_ok=nt_ok,
            now=now,
            quotes_live=quotes_live,
        )
        filled = 0
        for raw in missing:
            raw = dict(raw)
            raw["bar_period"] = "1m"
            try:
                md.apply_nt_bar(raw)
                filled += 1
            except BarRejected:
                continue
        if filled:
            closed = md.copy_ohlc()
            local_ts = list(closed["timestamp"]) if closed is not None and not closed.empty else []
            status, _ = reconcile_against_nt(
                local_closed=list(local_ts),
                nt_rows=rows,
                nt_ok=nt_ok,
                now=now,
                quotes_live=quotes_live,
                filled_count=filled,
            )
        md.integrity = status
        app.BAR_BOOK_COMPLETE = bool(status.complete)
        app.BAR_BOOK_LOCK_ENTRIES = bool(status.lock_new_entries)
        self._publish_bar_integrity(status)

    def _publish_bar_integrity(self, status: Any) -> None:
        blackboard = getattr(self.engine, "blackboard", None)
        if blackboard is None or not hasattr(blackboard, "publish_sync"):
            return
        try:
            blackboard.publish_sync(
                topic="market.bar_integrity",
                producer="market_data_service",
                payload=status.as_payload(),
                confidence=1.0 if status.complete else 0.0,
            )
        except Exception:
            logging.exception("bar_integrity.publish_failed")
        try:
            from lumina_core.io.atomic_fs import atomic_write_text
            from pathlib import Path
            import json

            root = getattr(getattr(self.engine, "config", None), "workspace_root", None)
            if root is None:
                return
            path = Path(root) / "state" / "lumina_bar_integrity.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(path, json.dumps(status.as_payload(), ensure_ascii=True, indent=2) + "\n")
        except Exception:
            logging.debug("bar_integrity.state_write_failed", exc_info=True)

    async def _fabric_live_listener(self) -> None:
        """Poll Fabric live quote cache (NT MarketDataUpdate stream). No CrossTrade."""
        from pathlib import Path

        from lumina_core.broker.ninjatrader.open_charts import subscription_plan

        app = self._app()
        configured = self._normalize_symbol(
            getattr(app, "INSTRUMENT", self.engine.config.instrument)
        )
        configured_swarm = [
            self._normalize_symbol(s)
            for s in getattr(app, "SWARM_SYMBOLS", self.engine.config.swarm_symbols)
        ]
        workspace = getattr(getattr(self.engine, "config", None), "workspace_root", None) or getattr(
            app, "workspace_root", None
        )
        if workspace is None:
            workspace = Path(__file__).resolve().parents[2]
        instrument, subscribed_symbols, chart_source = subscription_plan(
            configured, configured_swarm, []
        )
        last_tick_print = 0.0
        next_chart_scan = 0.0
        subscribed_key: tuple[str, ...] = ()

        client = None
        try:
            from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
                ensure_fabric_link_supervisor,
                get_fabric_link_supervisor,
            )

            ensure_fabric_link_supervisor(getattr(self.engine, "config", None), mode_context="sim")
            client = get_fabric_link_supervisor().get_client()
        except Exception:
            app.logger.debug("fabric.live.supervisor_unavailable", exc_info=True)

        if client is None or not getattr(client, "is_connected", False):
            try:
                from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient

                fabric_cfg = FabricConfig.from_engine_config(
                    getattr(self.engine, "config", None), mode_context="sim"
                )
                client = FabricGrpcClient(fabric_cfg)
                if not client.connect():
                    app.logger.error(
                        "Fabric live market data: connect failed — start NT8 LUMINA AddOn"
                    )
                    return
            except Exception as exc:
                app.logger.error("Fabric live market data unavailable: %s", exc)
                return

        def _sync_charts(force: bool) -> None:
            nonlocal instrument, subscribed_symbols, chart_source, subscribed_key, next_chart_scan
            now_scan = time.time()
            if not force and now_scan < next_chart_scan:
                return
            next_chart_scan = now_scan + 30.0
            try:
                from lumina_core.broker.ninjatrader.open_charts import read_open_charts

                observed = read_open_charts()
            except Exception:
                app.logger.debug("fabric.live.charts_unread", exc_info=True)
                observed = []
            instrument, symbols, chart_source = subscription_plan(
                configured, configured_swarm, observed
            )
            if symbols and tuple(symbols) != subscribed_key:
                try:
                    from lumina_core.engine.nt_bar_periods import CANONICAL_LIVE

                    client.subscribe_market_data(
                        symbols,
                        include_ticks=True,
                        include_bars=True,
                        bar_period="1m",
                        bar_periods=list(CANONICAL_LIVE),
                    )
                except Exception:
                    app.logger.debug("fabric.live.subscribe_failed", exc_info=True)
                    return
                subscribed_symbols = symbols
                subscribed_key = tuple(symbols)
                if instrument:
                    app.INSTRUMENT = instrument
                    try:
                        self.engine.config.instrument = instrument
                    except Exception:
                        pass
                    self.last_resolved_instrument = instrument
                app.logger.info(
                    "fabric.live.charts source=%s primary=%s symbols=%s",
                    chart_source,
                    instrument,
                    ",".join(symbols),
                )
                try:
                    self._hydrate_native_periods(app, client, instrument)
                except Exception:
                    app.logger.debug("fabric.live.htf_hydrate_failed", exc_info=True)
            try:
                from lumina_core.maturity.playground.portfolio_seal import maintain_sim_floor

                sentence = maintain_sim_floor(self.engine, workspace)
                from lumina_core.maturity.playground.live_hand import note_market_view

                last_px = None
                quotes = getattr(self.engine, "live_quotes", None)
                if quotes:
                    try:
                        last_px = float(quotes[-1].get("last") or 0.0)
                    except (AttributeError, TypeError, ValueError):
                        last_px = None
                note_market_view(
                    workspace,
                    charts=list(observed),
                    listing=str(instrument or ""),
                    source=str(chart_source or ""),
                    seal_note=str(sentence or ""),
                    last_px=last_px,
                )
            except Exception:
                app.logger.debug("fabric.live.portfolio_floor_failed", exc_info=True)

        try:
            _sync_charts(True)
        except Exception:
            app.logger.debug("fabric.live.subscribe_failed", exc_info=True)

        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message="Fabric live market data active (native NT — no CrossTrade)",
                context={"symbols": subscribed_symbols},
            )
        )

        while True:
            tick_start = time.perf_counter()
            try:
                _sync_charts(False)
                self._drain_nt_bars(app, client, workspace)
                now_loop = time.time()
                if now_loop >= float(getattr(self, "_next_bar_reconcile", 0.0) or 0.0):
                    self._next_bar_reconcile = now_loop + 30.0
                    try:
                        self._reconcile_nt_book(app, client, instrument)
                    except Exception:
                        app.logger.debug("fabric.live.bar_reconcile_failed", exc_info=True)
                for quote_symbol in subscribed_symbols:
                    q = client.get_last_quote(quote_symbol) if hasattr(client, "get_last_quote") else None
                    if not q:
                        continue
                    price = float(q.get("last") or 0.0)
                    if price <= 0:
                        continue
                    bid = float(q.get("bid") or price)
                    ask = float(q.get("ask") or price)
                    vol_cum = int(q.get("volume") or 0)
                    ts = self._quote_ts(q)

                    swarm_manager = getattr(app, "swarm_manager", None)
                    if swarm_manager is not None and hasattr(swarm_manager, "process_quote_tick"):
                        swarm_manager.process_quote_tick(
                            symbol=quote_symbol,
                            ts=ts,
                            price=price,
                            bid=bid,
                            ask=ask,
                            volume_cumulative=vol_cum,
                        )

                    if quote_symbol != instrument and not quote_symbol.startswith(
                        instrument.split()[0] if instrument else ""
                    ):
                        root = instrument.split()[0] if instrument else ""
                        if not quote_symbol.startswith(root):
                            continue

                    if quote_symbol == instrument or quote_symbol.startswith(
                        (instrument.split()[0] if instrument else "") + " "
                    ) or quote_symbol == (instrument.split()[0] if instrument else ""):
                        self.engine.market_data.process_quote_tick(
                            ts=ts,
                            price=price,
                            bid=bid,
                            ask=ask,
                            volume_cumulative=vol_cum,
                        )
                        tape_snapshot = self.engine.market_data.get_tape_snapshot()
                        tape_signal = self.tape_agent.score_momentum(tape_snapshot)
                        self.engine.market_data.last_tape_signal = tape_signal
                        self._publish_tape_signal(tape_signal)

                        if time.time() - last_tick_print >= float(
                            getattr(app, "TICK_PRINT_INTERVAL_SEC", 2.0)
                        ):
                            log_structured(
                                LuminaError(
                                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                                    code="INFO_PRINT_LEGACY",
                                    message=f"LIVE tick (fabric) -> last={price:.2f}",
                                    context={"price": price, "source": "fabric"},
                                )
                            )
                            last_tick_print = time.time()

                elapsed_ms = (time.perf_counter() - tick_start) * 1000.0
                self._record_latency(elapsed_ms, source="fabric_live")
            except Exception as exc:
                app.logger.error("Fabric live poll error: %s", exc)
            await asyncio.sleep(0.25)

    async def websocket_listener(self) -> None:
        app = self._app()
        if self._live_provider() == "fabric":
            await self._fabric_live_listener()
            return

        last_tick_print = 0.0
        uri = "wss://app.crosstrade.io/ws/stream"
        headers = {
            "Authorization": f"Bearer {getattr(app, 'CROSSTRADE_TOKEN', self.engine.config.crosstrade_token or '')}"
        }
        instrument = self._normalize_symbol(getattr(app, "INSTRUMENT", self.engine.config.instrument))
        configured_swarm = [
            self._normalize_symbol(s) for s in getattr(app, "SWARM_SYMBOLS", self.engine.config.swarm_symbols)
        ]
        if instrument not in configured_swarm:
            configured_swarm.insert(0, instrument)
        subscribed_symbols = [s for s in configured_swarm if s]
        try:
            async with websockets.connect(uri, additional_headers=headers, ping_interval=20, ping_timeout=20) as ws:
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="INFO_PRINT_LEGACY",
                        message="WS connected - CrossTrade tape only (1m OHLC is NT BarsRequest)",
                        context={},
                    )
                )
                await ws.send(json.dumps({"action": "subscribe", "instruments": subscribed_symbols}))

                async for message in ws:
                    tick_start = time.perf_counter()
                    try:
                        data = json.loads(message)
                        if data.get("type") != "marketData":
                            continue

                        for quote in data.get("quotes", []):
                            quote_symbol = self._normalize_symbol(str(quote.get("instrument", "")))
                            if quote_symbol not in subscribed_symbols:
                                continue

                            ts = datetime.now(timezone.utc)
                            price = self._extract_numeric(quote, ("last", "lastPrice", "tradePrice"), 0.0)
                            bid = self._extract_numeric(quote, ("bid", "bidPrice", "bestBid"), price)
                            ask = self._extract_numeric(quote, ("ask", "askPrice", "bestAsk"), price)
                            vol_cum = int(self._extract_numeric(quote, ("volume", "totalVolume", "cumVolume"), 0.0))

                            swarm_manager = getattr(app, "swarm_manager", None)
                            if swarm_manager is not None and hasattr(swarm_manager, "process_quote_tick"):
                                swarm_manager.process_quote_tick(
                                    symbol=quote_symbol,
                                    ts=ts,
                                    price=price,
                                    bid=bid,
                                    ask=ask,
                                    volume_cumulative=vol_cum,
                                )

                            if quote_symbol != instrument:
                                continue

                            self.engine.market_data.process_quote_tick(
                                ts=ts,
                                price=price,
                                bid=bid,
                                ask=ask,
                                volume_cumulative=vol_cum,
                            )

                            tape_snapshot = self.engine.market_data.get_tape_snapshot()
                            tape_signal = self.tape_agent.score_momentum(tape_snapshot)
                            self.engine.market_data.last_tape_signal = tape_signal
                            self._publish_tape_signal(tape_signal)

                            if time.time() - last_tick_print >= float(getattr(app, "TICK_PRINT_INTERVAL_SEC", 2.0)):
                                tape_txt = (
                                    f"delta10={tape_signal.get('cumulative_delta_10', 0.0):.0f} "
                                    f"imb={tape_signal.get('bid_ask_imbalance', 1.0):.2f} "
                                    f"sig={tape_signal.get('signal', 'HOLD')}"
                                )
                                log_structured(
                                    LuminaError(
                                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                                        code="INFO_PRINT_LEGACY",
                                        message=f"LIVE tick -> last={price:.2f} | {tape_txt}",
                                        context={"price": price, "tape": tape_signal.get("signal", "HOLD")},
                                    )
                                )
                                last_tick_print = time.time()
                        elapsed_ms = (time.perf_counter() - tick_start) * 1000.0
                        self._record_latency(elapsed_ms, source="websocket")
                    except Exception as exc:
                        err = LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                            code="MDS_WS_PARSE_002",
                            message=str(exc),
                            context={"traceback": traceback.format_exc()},
                        )
                        log_structured(err)
                        app.logger.error(f"WS parse error: {exc}")
        except ConnectionClosed as closed_exc:
            # Peer idle timeout, TCP reset, or missing close frame — expected in long-lived feeds.
            app.logger.warning("WebSocket closed (%s); using REST fallback", closed_exc)
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="MDS_WS_CLOSED_008",
                message=str(closed_exc),
                context={
                    "code": getattr(closed_exc, "code", None),
                    "reason": getattr(closed_exc, "reason", None),
                },
            )
            log_structured(err)
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="WS failed -> REST fallback",
                    context={},
                )
            )
        except Exception as _exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/market_data_ingest.py")
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="MDS_WS_CONNECT_003",
                message=str(_exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="WS failed -> REST fallback",
                    context={},
                )
            )

    def start_websocket(self) -> None:
        asyncio.run(self.websocket_listener())

    def fetch_quote(self) -> tuple[float, int]:
        app = self._app()
        instrument = getattr(app, "INSTRUMENT", self.engine.config.instrument)
        request_start = time.perf_counter()

        if self._live_provider() == "fabric":
            try:
                from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
                    get_fabric_link_supervisor,
                )

                client = get_fabric_link_supervisor().get_client()
                if client is not None and hasattr(client, "get_last_quote"):
                    q = client.get_last_quote(str(instrument or ""))
                    if q and float(q.get("last") or 0) > 0:
                        elapsed_ms = (time.perf_counter() - request_start) * 1000.0
                        self._record_latency(elapsed_ms, source="fetch_quote_fabric")
                        return float(q["last"]), int(q.get("volume") or 0)
            except Exception:
                app.logger.debug("fabric.fetch_quote_failed", exc_info=True)
            elapsed_ms = (time.perf_counter() - request_start) * 1000.0
            self._record_latency(elapsed_ms, source="fetch_quote_fabric")
            return 0.0, 0

        account = getattr(app, "CROSSTRADE_ACCOUNT", self.engine.config.crosstrade_account)
        token = getattr(app, "CROSSTRADE_TOKEN", self.engine.config.crosstrade_token or "")
        try:
            response = _mds().requests.get(
                f"https://app.crosstrade.io/v1/api/accounts/{account}/quote?instrument={instrument}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=8,
            )
            if response.status_code == 200:
                data = response.json()
                elapsed_ms = (time.perf_counter() - request_start) * 1000.0
                self._record_latency(elapsed_ms, source="fetch_quote")
                return float(data.get("last", 0)), int(data.get("volume", 0))
        except requests.RequestException as exc:
            app.logger.error(f"Fetch quote request error: {exc}")
        except (ValueError, TypeError) as exc:
            app.logger.error(f"Fetch quote parse error: {exc}")
        elapsed_ms = (time.perf_counter() - request_start) * 1000.0
        self._record_latency(elapsed_ms, source="fetch_quote")
        return 0.0, 0
