from __future__ import annotations
import logging

import asyncio
import json
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import pandas as pd
import requests
import websockets
from websockets.exceptions import ConnectionClosed

from .errors import ErrorSeverity, LuminaError, log_structured
from .tape_reading_agent import TapeReadingAgent
from lumina_core.first_boot_ui import HISTORICAL_BAR_LIMIT_SAFETY_CAP
from lumina_core.sla_config import market_data_latency_sla_ms

from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class MarketDataIngestService:
    """Websocket and historical market-data ingestion backed by MarketDataManager."""

    engine: LuminaEngine
    tape_agent: TapeReadingAgent = field(default_factory=TapeReadingAgent)
    latency_sla_ms: float = 250.0
    latency_window: deque[float] = field(default_factory=lambda: deque(maxlen=50))
    _sla_breach_streak: int = 0
    _sla_recovery_streak: int = 0

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
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/market_data_service.py:115")
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="MDS_TAPE_PUBLISH_001",
                message=str(_exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            return

    async def websocket_listener(self) -> None:
        app = self._app()
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
                        message="WS connected - 1-min candle builder active",
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

                            ts = datetime.now()
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

                            closed_candle = self.engine.market_data.process_quote_tick(
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

                            if closed_candle is not None:
                                minute_start = ts.replace(second=0, microsecond=0)
                                safe_candle = {
                                    key: (value.isoformat() if isinstance(value, datetime) else value)
                                    for key, value in dict(closed_candle).items()
                                }
                                log_structured(
                                    LuminaError(
                                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                                        code="INFO_PRINT_LEGACY",
                                        message=(
                                            f"[{minute_start.strftime('%H:%M')}] 1-min candle closed -> "
                                            f"O={closed_candle['open']:.2f} H={closed_candle['high']:.2f} "
                                            f"L={closed_candle['low']:.2f} C={closed_candle['close']:.2f} V={closed_candle['volume']}"
                                        ),
                                        context={"candle": safe_candle},
                                    )
                                )

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
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/market_data_service.py:241")
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
        account = getattr(app, "CROSSTRADE_ACCOUNT", self.engine.config.crosstrade_account)
        instrument = getattr(app, "INSTRUMENT", self.engine.config.instrument)
        token = getattr(app, "CROSSTRADE_TOKEN", self.engine.config.crosstrade_token or "")
        request_start = time.perf_counter()
        try:
            response = requests.get(
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

    def load_historical_ohlc(self, days_back: int = 3, limit: int = 5000) -> bool:
        instrument = self._normalize_symbol(getattr(self._app(), "INSTRUMENT", self.engine.config.instrument))
        rows = self.load_historical_ohlc_for_symbol(instrument=instrument, days_back=days_back, limit=limit)
        if rows.empty:
            return False

        self.engine.market_data.append_ohlc_rows(rows)
        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message=f"Loaded {len(rows)} historical 1-min candles -> ohlc_1min now {len(self.engine.ohlc_1min)} rows",
                context={"rows": len(rows)},
            )
        )
        return True

    @staticmethod
    def _bars_response_to_list(data: Any) -> list[dict[str, Any]]:
        bars = (
            data
            if isinstance(data, list)
            else data.get("bars") or data.get("data") or data.get("result") or data.get("ohlc") or []
        )
        return bars if isinstance(bars, list) else []

    @staticmethod
    def _utc_iso_z(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _post_historical_bars(
        self,
        *,
        instrument: str,
        token: str,
        payload: dict[str, Any],
        app: Any,
    ) -> list[dict[str, Any]]:
        try:
            response = requests.post(
                "https://app.crosstrade.io/v1/api/market/bars",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=(10, 45),
            )
            if response.status_code != 200:
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                        code="MDS_HIST_API_004",
                        message=f"API error {response.status_code}: {response.text[:400]}",
                        context={"status_code": response.status_code},
                    )
                )
                return []
            return self._bars_response_to_list(response.json())
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="MDS_HIST_LOAD_005",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            app.logger.error(f"Historical load error: {exc}")
            return []

    def _fetch_historical_bars(
        self,
        instrument: str,
        days_back: int,
        limit: int | None,
        on_chunk: Callable[..., None] | None = None,
    ) -> list[dict[str, Any]]:
        """Load 1-min bars from CrossTrade, paginating with ``from``/``to`` windows.

        A single huge ``daysBack`` + ``limit`` request can stall or hit provider timeouts
        (CrossTrade recommends smaller ranges). We step forward in UTC windows and cap
        each request's ``limit``.
        """
        app = self._app()
        instrument = self._normalize_symbol(instrument)
        token = getattr(app, "CROSSTRADE_TOKEN", self.engine.config.crosstrade_token or "")
        uncapped = limit is None
        if uncapped:
            target_cap: int | None = HISTORICAL_BAR_LIMIT_SAFETY_CAP
            limit_label = f"all bars in window (safety cap {HISTORICAL_BAR_LIMIT_SAFETY_CAP:,})"
        else:
            target_cap = max(1, min(int(limit), HISTORICAL_BAR_LIMIT_SAFETY_CAP))
            limit_label = str(target_cap)
        days_back_i = max(1, int(days_back))

        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message=(
                    f"[v21.6] Loading {limit_label} real 1-min OHLC bars for {instrument} "
                    f"(last {days_back_i} days, paginated)..."
                ),
                context={
                    "instrument": instrument,
                    "limit": target_cap,
                    "days_back": days_back_i,
                    "uncapped": uncapped,
                },
            )
        )

        utc_now = datetime.now(timezone.utc)
        range_start = utc_now - timedelta(days=days_back_i)
        # ~4 calendar days of 1-min bars stays under common per-request caps; RTH-only is lower.
        chunk_days = 4
        per_chunk_limit = 8_000
        max_chunks = max(1, min(256, (days_back_i // chunk_days) + 48))

        windows: list[tuple[datetime, datetime]] = []
        cursor = range_start
        while cursor < utc_now and len(windows) < max_chunks:
            nxt = min(cursor + timedelta(days=chunk_days), utc_now)
            if nxt <= cursor:
                break
            windows.append((cursor, nxt))
            cursor = nxt

        merged: list[dict[str, Any]] = []
        seen_epoch: set[int] = set()
        seen_time: set[str] = set()

        for idx, (win_from, win_to) in enumerate(windows):
            if target_cap is not None and len(merged) >= target_cap:
                break
            if target_cap is None:
                chunk_limit = per_chunk_limit
            else:
                chunk_limit = min(per_chunk_limit, target_cap - len(merged))
            payload = {
                "instrument": instrument,
                "periodType": "minute",
                "period": 1,
                "from": self._utc_iso_z(win_from),
                "to": self._utc_iso_z(win_to),
                "limit": max(100, chunk_limit),
            }
            app.logger.info(
                "Historical bars chunk %s/%s from=%s to=%s limit=%s",
                idx + 1,
                len(windows),
                payload["from"],
                payload["to"],
                chunk_limit,
            )
            bars = self._post_historical_bars(instrument=instrument, token=token, payload=payload, app=app)
            if on_chunk is not None:
                try:
                    on_chunk(
                        chunk_index=idx + 1,
                        chunk_total=len(windows),
                        bars_merged=len(merged) + len(bars),
                        chunk_bars=len(bars),
                        chunk_phase="fetch",
                    )
                except Exception:
                    app.logger.warning("birth.history.on_chunk_failed", exc_info=True)
            for bar in bars:
                ep = bar.get("epoch")
                ts_raw = bar.get("timestamp") or bar.get("time")
                if isinstance(ep, (int, float)):
                    ek = int(ep)
                    if ek in seen_epoch:
                        continue
                    seen_epoch.add(ek)
                elif ts_raw is not None:
                    tk = str(ts_raw)
                    if tk in seen_time:
                        continue
                    seen_time.add(tk)
                merged.append(bar)
                if target_cap is not None and len(merged) >= target_cap:
                    break

        if merged:

            def _bar_sort_key(b: dict[str, Any]) -> tuple[int, float, str]:
                ep = b.get("epoch")
                if isinstance(ep, (int, float)):
                    return (0, float(ep), "")
                ts_raw = b.get("timestamp") or b.get("time")
                if ts_raw is not None:
                    try:
                        return (1, float(pd.to_datetime(ts_raw).value), "")
                    except Exception:
                        return (2, 0.0, str(ts_raw))
                return (3, 0.0, "")

            merged.sort(key=_bar_sort_key)
            if target_cap is not None:
                return merged[:target_cap]
            return merged

        # Fallback: single bounded request (legacy path) for providers that ignore from/to.
        fallback_limit = min(8_000, target_cap if target_cap is not None else HISTORICAL_BAR_LIMIT_SAFETY_CAP)
        payload_fb = {
            "instrument": instrument,
            "periodType": "minute",
            "period": 1,
            "daysBack": days_back_i,
            "limit": fallback_limit,
        }
        app.logger.warning(
            "birth.history.paginated_empty fallback=daysBack limit=%s daysBack=%s",
            fallback_limit,
            days_back_i,
        )
        fallback_bars = self._post_historical_bars(
            instrument=instrument, token=token, payload=payload_fb, app=app
        )
        if not fallback_bars:
            app.logger.error(
                "birth.history.load_failed instrument=%s days_back=%s limit=%s (0 bars after paginated+fallback)",
                instrument,
                days_back_i,
                target_cap,
            )
        return fallback_bars

    def load_historical_ohlc_for_symbol(self, instrument: str, days_back: int = 3, limit: int = 5000) -> pd.DataFrame:
        bars = self._fetch_historical_bars(instrument=instrument, days_back=days_back, limit=limit)
        rows: list[dict[str, Any]] = []
        for bar in bars:
            ts_str = bar.get("timestamp") or bar.get("time")
            if not ts_str:
                continue
            ts = pd.to_datetime(ts_str)
            if ts.tzinfo is not None:
                ts = ts.tz_convert(None)
            rows.append(
                {
                    "timestamp": ts,
                    "open": float(bar.get("open") or bar.get("last") or 0),
                    "high": float(bar.get("high") or bar.get("last") or 0),
                    "low": float(bar.get("low") or bar.get("last") or 0),
                    "close": float(bar.get("close") or bar.get("last") or 0),
                    "volume": int(bar.get("volume", 0)),
                }
            )

        if not rows:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return pd.DataFrame(rows)

    def load_historical_ohlc_extended(
        self,
        days_back: int = 30,
        limit: int | None = 120000,
        ticks_per_bar: int = 4,
        on_chunk: Callable[..., None] | None = None,
    ) -> list[dict[str, Any]]:
        """Load historical bars and expand each bar into pseudo ticks.

        Crosstrade historical endpoint is bar-based; this creates a deterministic
        tick stream (open/high/low/close path) for simulation workloads.
        """
        app = self._app()
        instrument = self._normalize_symbol(getattr(app, "INSTRUMENT", self.engine.config.instrument))
        try:
            bars = self._fetch_historical_bars(
                instrument=instrument,
                days_back=days_back,
                limit=limit,
                on_chunk=on_chunk,
            )

            ticks: list[dict[str, Any]] = []
            total_bars = len(bars)
            expand_batch = 500
            for bar_index, bar in enumerate(bars):
                ts_str = bar.get("timestamp") or bar.get("time")
                if not ts_str:
                    continue
                bar_ts = pd.to_datetime(ts_str)
                if bar_ts.tzinfo is not None:
                    bar_ts = bar_ts.tz_convert(None)

                o = float(bar.get("open") or bar.get("last") or 0.0)
                h = float(bar.get("high") or bar.get("last") or 0.0)
                low_price = float(bar.get("low") or bar.get("last") or 0.0)
                c = float(bar.get("close") or bar.get("last") or 0.0)
                v = max(1, int(bar.get("volume", 1)))

                # Price path with directional bias from open->close.
                path = [o, h, low_price, c]
                if c < o:
                    path = [o, low_price, h, c]
                if ticks_per_bar > 4:
                    extra = [c + (h - low_price) * 0.25, c - (h - low_price) * 0.25]
                    path.extend(extra[: max(0, ticks_per_bar - 4)])

                per_tick_vol = max(1, int(v / max(1, len(path))))
                cum_vol = 0
                for idx, px in enumerate(path):
                    cum_vol += per_tick_vol
                    spread = max(0.25, abs(h - low_price) * 0.02)
                    ticks.append(
                        {
                            "timestamp": (bar_ts + pd.Timedelta(seconds=idx * (60 / max(1, len(path))))).isoformat(),
                            "last": float(px),
                            "bid": float(px - spread / 2.0),
                            "ask": float(px + spread / 2.0),
                            "volume": int(cum_vol),
                        }
                    )
                if on_chunk is not None and total_bars > 0 and (
                    (bar_index + 1) % expand_batch == 0 or (bar_index + 1) == total_bars
                ):
                    try:
                        on_chunk(
                            chunk_index=bar_index + 1,
                            chunk_total=total_bars,
                            bars_merged=bar_index + 1,
                            chunk_bars=0,
                            chunk_phase="expand",
                        )
                    except Exception:
                        app.logger.warning("birth.history.on_chunk_failed", exc_info=True)

            return ticks
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="MDS_HIST_EXTENDED_006",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            app.logger.error(f"Historical extended load error: {exc}")
            return []

    def gap_recovery_daemon(self) -> None:
        while True:
            time.sleep(300)
            try:
                with self.engine.live_data_lock:
                    if len(self.engine.ohlc_1min) < 50:
                        continue
                    df = self.engine.ohlc_1min[["timestamp"]].copy()
                    deltas = df["timestamp"].diff().dt.total_seconds()
                    max_gap = deltas.max() if len(deltas) > 1 else 0
                if max_gap > 120:
                    log_structured(
                        LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_LEARNING,
                            code="INFO_PRINT_LEGACY",
                            message=f"GAP DETECTED ({max_gap / 60:.1f} min) -> recovery",
                            context={"max_gap_sec": max_gap},
                        )
                    )
                    self.load_historical_ohlc(days_back=2, limit=2000)
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                    code="MDS_GAP_RECOVERY_007",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                self._app().logger.error(f"Gap recovery error: {exc}")
