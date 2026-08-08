"""Market / news / loop helpers (M5 extract)."""
from __future__ import annotations

from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.engine.operations")


class OperationsMarketMixin:
    def detect_swing_and_fibs(self) -> tuple[float, float, dict[str, float]]:
        with self.engine.live_data_lock:
            if len(self.engine.ohlc_1min) < 50:
                return 0.0, 0.0, {}
            recent = self.engine.ohlc_1min.iloc[-60:]

        swing_low = float(recent["low"].min())
        swing_high = float(recent["high"].max())
        diff = swing_high - swing_low
        fib_levels: dict[str, float] = {}
        for ratio in [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]:
            fib_levels[str(ratio)] = round(swing_high - diff * ratio, 2)
        return swing_high, swing_low, fib_levels

    def get_mtf_snapshots(self) -> str:
        timeframes = self.engine.config.timeframes
        with self.engine.live_data_lock:
            if len(self.engine.ohlc_1min) < 60:
                return "PARTIAL_DATA_ONLY"
            df = self.engine.ohlc_1min.copy()

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        snapshots: dict[str, Any] = {}
        for tf_name, seconds in timeframes.items():
            resampled = (
                df.set_index("timestamp")
                .resample(f"{seconds // 60}min")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
            )
            if len(resampled) > 0:
                row = resampled.iloc[-1]
                snapshots[tf_name] = {
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                }
            else:
                snapshots[tf_name] = {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0}
        return json.dumps(snapshots, ensure_ascii=False)

    def get_high_impact_news(self) -> dict[str, Any]:
        app = self._app()
        api_key = self.engine.config.finnhub_api_key
        if not api_key:
            return {"events": [], "overall_sentiment": "neutral", "impact": "medium"}

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            response = requests.get(
                f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={today}",
                headers={"X-Finnhub-Token": api_key},
                timeout=15,
            )
            if response.status_code == 200:
                events = response.json().get("economicCalendar", [])
                high_impact = [
                    event
                    for event in events
                    if event.get("impact") in ["high", "3"]
                    or event.get("event", "").lower() in ["fomc", "nfp", "cpi", "ppi"]
                ]
                sentiment = "neutral"
                if any(
                    "rate" in event.get("event", "").lower() or "fomc" in event.get("event", "").lower()
                    for event in high_impact
                ):
                    sentiment = (
                        "bullish"
                        if len([event for event in high_impact if "cut" in str(event).lower()]) > 0
                        else "bearish"
                    )
                return {
                    "events": high_impact[:4],
                    "overall_sentiment": sentiment,
                    "impact": "high" if high_impact else "medium",
                }
        except requests.RequestException as exc:
            app.logger.error(f"Finnhub request error: {exc}")
        except (ValueError, TypeError) as exc:
            app.logger.error(f"Finnhub parse error: {exc}")
        return {"events": [], "overall_sentiment": "neutral", "impact": "medium"}

    def speak(self, text: str) -> None:
        app = self._app()
        if not bool(getattr(app, "VOICE_ENABLED", False)) or not getattr(app, "tts_engine", None):
            return
        try:
            clean_text = text.replace("...", ". ").replace(" – ", ", ")
            log_event(app.logger, "ops.speak", preview=clean_text[:140])
            app.tts_engine.say(clean_text)
            app.tts_engine.runAndWait()
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="OPS_TTS_002",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            app.logger.error(f"TTS_ERROR: {exc}")

    def is_market_open(self) -> bool:
        session_guard = getattr(self.engine, "session_guard", None)
        if session_guard is None:
            self._app().logger.warning("OPS_MARKET_OPEN_FAIL_CLOSED,error_code=SESSION_GUARD_UNAVAILABLE")
            return False
        try:
            return bool(session_guard.is_trading_session())
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="OPS_SESSION_GUARD_006",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            self._app().logger.warning(
                "OPS_MARKET_OPEN_FAIL_CLOSED,error_code=SESSION_GUARD_ERROR,detail=%s",
                exc,
            )
            return False

    def run_forever_loop(self) -> None:
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="\n🛑 Graceful shutdown gestart...",
                    context={},
                )
            )
            self.engine.save_state()
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="\u2705 Alle data veilig opgeslagen.",
                    context={},
                )
            )
        except SystemExit:
            self.engine.save_state()
