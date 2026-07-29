from __future__ import annotations
import logging

import asyncio
import json
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed
from datetime import datetime
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
        account = getattr(app, "CROSSTRADE_ACCOUNT", self.engine.config.crosstrade_account)
        instrument = getattr(app, "INSTRUMENT", self.engine.config.instrument)
        token = getattr(app, "CROSSTRADE_TOKEN", self.engine.config.crosstrade_token or "")
        request_start = time.perf_counter()
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
