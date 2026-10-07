"""Chart / screen-share helpers for VisualizationService (global residual)."""
from __future__ import annotations

import base64
import json
import queue
import threading
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from PIL import Image

_live_stream_feed_lock = threading.Lock()
_live_feed_log_ts: dict[str, float] = {}
_LIVE_FEED_LOG_THROTTLE_SEC = 45.0


def _live_feed_throttled(logger: Any, key: str, msg: str) -> None:
    now = time.monotonic()
    last = _live_feed_log_ts.get(key, 0.0)
    if now - last < _LIVE_FEED_LOG_THROTTLE_SEC:
        return
    _live_feed_log_ts[key] = now
    logger.info(msg)

class VisualizationChartsMixin:
    def _create_photo_image(self, pil_img: Image.Image) -> Any:
        from PIL import ImageTk

        return ImageTk.PhotoImage(pil_img)
    def _record_live_stream_chart_frame(self, *, base64_char_len: int) -> None:
        """Append a JSONL heartbeat so the Streamlit launcher can detect chart frames (state/live_stream.jsonl)."""
        path = Path(self.engine.config.live_jsonl)
        line = json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "event": "chart_frame",
                "b64_chars": int(base64_char_len),
            },
            ensure_ascii=False,
        )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with _live_stream_feed_lock:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            self.engine.logger.info(
                "LIVE_FEED_JSONL_OK,path=%s,b64_chars=%s",
                path.as_posix(),
                int(base64_char_len),
            )
        except OSError as exc:
            self.engine.logger.warning(
                "LIVE_FEED_JSONL_ABORT,path=%s,reason=os_error,detail=%s",
                path.as_posix(),
                exc,
            )
    def generate_multi_tf_chart(self, ai_fibs: dict | None = None) -> str | None:
        app = self._app()
        start_time = time.perf_counter()
        bars = len(self.engine.ohlc_1min)
        app.logger.info("LIVE_FEED_CHART_GEN_ENTER,ohlc_bars=%s", bars)

        from lumina_core.engine.nt_ohlc_frames import chart_frames, operator_listing

        with self.engine.live_data_lock:
            closed_n = len(self.engine.ohlc_1min)
            if closed_n < 200:
                app.logger.info(
                    "LIVE_FEED_CHART_GEN_ABORT,stage=ohlc_gate,reason=insufficient_data,bars=%s,min_required=200",
                    closed_n,
                )
                app.logger.info("CHART_GEN_SKIPPED,reason=insufficient_data")
                self._note_screen_status(
                    f"Nog {closed_n}/200 gesloten NT 1m-bars voor de grafiek"
                )
                return None
            closed_1m = self.engine.ohlc_1min.copy()
            recent_closed = closed_1m.iloc[-60:]
        frames = chart_frames(self.engine.market_data)
        df = frames.get("1min")
        if df is None or df.empty:
            self._note_screen_status("Geen native NT 1m bars voor de grafiek")
            return None

        tfs = [
            ("1min", "1m"),
            ("5min", "5m"),
            ("15min", "15m"),
            ("30min", "30m"),
            ("60min", "60m"),
            ("240min", "240m"),
        ]
        fig = make_subplots(
            rows=3,
            cols=2,
            subplot_titles=[name for name, _ in tfs],
            vertical_spacing=0.08,
            horizontal_spacing=0.05,
        )

        row_col = [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2)]
        swing_low = float(recent_closed["low"].min()) if not recent_closed.empty else 0.0
        swing_high = float(recent_closed["high"].max()) if not recent_closed.empty else 0.0
        diff = swing_high - swing_low
        fib_levels: dict[str, float] = {}
        if diff > 0:
            for ratio in [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]:
                fib_levels[str(ratio)] = round(swing_high - diff * ratio, 2)

        structure = self.engine.detect_market_structure(closed_1m)

        for i, (tf_name, _period) in enumerate(tfs):
            row, col = row_col[i]
            subplot_row: Any = row
            subplot_col: Any = col
            res = frames.get(tf_name)
            if res is None or res.empty:
                fig.add_annotation(
                    text="geen NT bars",
                    xref="x domain",
                    yref="y domain",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(color="#c8c8c8", size=12),
                    row=row,
                    col=col,
                )
                continue

            fig.add_trace(
                go.Candlestick(
                    x=res.index,
                    open=res["open"],
                    high=res["high"],
                    low=res["low"],
                    close=res["close"],
                    name=tf_name,
                    increasing_line_color="#00ff88",
                    decreasing_line_color="#ff4444",
                ),
                row=row,
                col=col,
            )
            fig.add_trace(
                go.Bar(x=res.index, y=res["volume"], name="Volume", marker_color="#8888ff", opacity=0.4),
                row=row,
                col=col,
            )

            if tf_name == "1min":
                for ratio, price in fib_levels.items():
                    if str(ratio) in {"0.382", "0.618", "0.786"}:
                        fig.add_hline(
                            y=float(price),
                            line_dash="dash",
                            line_color="#ffff00",
                            annotation_text=f"Bot Fib {ratio}",
                            row=subplot_row,
                            col=subplot_col,
                        )

            if ai_fibs and tf_name == "1min":
                for ratio, price in ai_fibs.items():
                    fig.add_hline(
                        y=float(price),
                        line_dash="solid",
                        line_color="#00ff00",
                        annotation_text=f"AI Fib {ratio}",
                        row=subplot_row,
                        col=subplot_col,
                    )

            if tf_name == "1min" and structure.get("bos"):
                fig.add_hline(
                    y=swing_high if "bullish" in str(structure["bos"]) else swing_low,
                    line_color="#00ffff",
                    line_width=2,
                    annotation_text=str(structure["bos"]),
                    row=subplot_row,
                    col=subplot_col,
                )
            if tf_name == "1min" and structure.get("choch"):
                fig.add_hline(
                    y=swing_high,
                    line_color="#ff00ff",
                    line_width=2,
                    annotation_text="CHOCH",
                    row=subplot_row,
                    col=subplot_col,
                )

            order_blocks = structure.get("order_blocks", [])
            if tf_name == "1min" and len(order_blocks) >= 2:
                fig.add_hline(
                    y=order_blocks[0]["price"],
                    line_color="#ff8800",
                    line_dash="dot",
                    annotation_text="Bull OB",
                    row=subplot_row,
                    col=subplot_col,
                )
                fig.add_hline(
                    y=order_blocks[1]["price"],
                    line_color="#ff8800",
                    line_dash="dot",
                    annotation_text="Bear OB",
                    row=subplot_row,
                    col=subplot_col,
                )

        current_price = float(df["close"].iloc[-1])
        regime = self.engine.detect_market_regime(closed_1m)
        listing = operator_listing(app, self.engine)
        fig.update_layout(
            title=f"LUMINA · {listing} | {current_price:.2f} | Regime {regime} | {datetime.now(timezone.utc).strftime('%d %b %H:%M')} UTC",
            height=900,
            width=1400,
            showlegend=False,
            template="plotly_dark",
            margin=dict(l=40, r=40, t=100, b=40),
        )

        img_bytes = BytesIO()
        app.logger.info("LIVE_FEED_CHART_GEN_STEP,stage=plotly_write_image,format=png,scale=2")
        png: bytes | None = None
        try:
            fig.write_image(img_bytes, format="png", scale=2)
            png = img_bytes.getvalue()
        except Exception as exc:
            app.logger.warning("CHART_GEN_EXPORT_SKIPPED,reason=%s", exc)
            app.logger.warning(
                "LIVE_FEED_CHART_GEN_FALLBACK,stage=matplotlib,reason=kaleido_or_static_image_failed,detail=%s",
                exc,
            )
        if not png:
            try:
                from lumina_core.engine.chart_png import render_live_chart_png

                png = render_live_chart_png(
                    df, title=str(fig.layout.title.text or "LUMINA"), frames_by_tf=frames
                )
                app.logger.info("LIVE_FEED_CHART_GEN_STEP,stage=matplotlib_png,bytes=%s", len(png))
            except Exception as exc:
                app.logger.warning(
                    "LIVE_FEED_CHART_GEN_ABORT,stage=matplotlib_png,reason=%s",
                    exc,
                )
                self._note_screen_status("Grafiek kon niet worden gemaakt")
                return None
        base64_img = base64.b64encode(png).decode("utf-8")
        app.logger.info(
            "LIVE_FEED_CHART_GEN_STEP,stage=base64_ready,b64_chars=%s",
            len(base64_img),
        )

        screen_on = bool(getattr(app, "SCREEN_SHARE_ENABLED", self.engine.config.screen_share_enabled))
        if screen_on:
            app.logger.info("LIVE_FEED_PUBLISH_ENTER,screen_share_enabled=true,targets=tk_window,live_stream_jsonl")
            self.update_live_chart(base64_img)
            self._record_live_stream_chart_frame(base64_char_len=len(base64_img))
        else:
            app.logger.info(
                "LIVE_FEED_PUBLISH_SKIP,reason=screen_share_disabled,b64_chars=%s "
                "(no Tk update, no state/live_stream.jsonl heartbeat)",
                len(base64_img),
            )

        duration_ms = (time.perf_counter() - start_time) * 1000
        app.logger.info(
            "CHART_GEN_COMPLETE,duration_ms=%.0f,base64_kb=%s,screen_share_enabled=%s",
            duration_ms,
            len(base64_img) // 1000,
            str(screen_on).lower(),
        )
        app.logger.info(
            "[%s] v28 Chart generated (LIVE_FEED publish path executed per flags above)",
            datetime.now().strftime("%H:%M:%S"),
        )
        return base64_img

    def publish_screen_share_snapshot(self) -> str | None:
        """Draw the screen-share from NT bars. No LLM call and no Kaleido.

        The fast path skips the vision branch, but the window is already open.
        This paints that window from the candles that are already loaded.
        """
        app = self._app()
        screen_on = bool(getattr(app, "SCREEN_SHARE_ENABLED", self.engine.config.screen_share_enabled))
        if not screen_on:
            return None
        from lumina_core.engine.nt_ohlc_frames import chart_frames, operator_listing

        with self.engine.live_data_lock:
            bars = len(self.engine.ohlc_1min)
            if bars < 200:
                self._note_screen_status(f"Nog {bars}/200 gesloten NT 1m-bars voor de grafiek")
                return None
        frames = chart_frames(self.engine.market_data)
        df = frames.get("1min")
        if df is None or df.empty:
            self._note_screen_status("Geen native NT 1m bars voor de grafiek")
            return None
        listing = operator_listing(app, self.engine)
        price = float(df["close"].iloc[-1])
        title = (
            f"LUMINA · {listing} | {price:.2f} | {datetime.now(timezone.utc).strftime('%d %b %H:%M')} UTC"
        )
        try:
            from lumina_core.engine.chart_png import render_live_chart_png

            png = render_live_chart_png(df, title=title, frames_by_tf=frames)
        except Exception as exc:
            app.logger.warning("LIVE_FEED_CHART_GEN_ABORT,stage=matplotlib_png,reason=%s", exc)
            self._note_screen_status("Grafiek kon niet worden gemaakt")
            return None
        if not png:
            self._note_screen_status("Grafiek kon niet worden gemaakt")
            return None
        base64_img = base64.b64encode(png).decode("utf-8")
        app.logger.info(
            "LIVE_FEED_CHART_GEN_STEP,stage=matplotlib_png,bytes=%s,path=screen_share_snapshot",
            len(png),
        )
        self.update_live_chart(base64_img, status_msg="NT-grafiek bijgewerkt")
        return base64_img

    def _note_screen_status(self, message: str) -> None:
        app = self._app()
        screen_on = bool(getattr(app, "SCREEN_SHARE_ENABLED", self.engine.config.screen_share_enabled))
        if not screen_on:
            return
        try:
            self._tk_chart_queue.put_nowait(("status", message))
        except queue.Full:
            pass

    def start_screen_share_window(self) -> None:
        from lumina_core.engine.visualization_charts_window import spawn_screen_share_window

        spawn_screen_share_window(self)

    def update_live_chart(self, chart_base64: str, status_msg: str = "NT-grafiek bijgewerkt") -> None:
        app = self._app()
        screen_on = bool(getattr(app, "SCREEN_SHARE_ENABLED", self.engine.config.screen_share_enabled))
        if not screen_on:
            _live_feed_throttled(
                app.logger,
                "tk_skip_disabled",
                "LIVE_FEED_TK_SKIP,reason=screen_share_disabled",
            )
            return

        try:
            self._tk_chart_queue.put_nowait(("frame", chart_base64, status_msg))
        except queue.Full:
            _live_feed_throttled(
                app.logger,
                "tk_queue_full",
                "LIVE_FEED_TK_QUEUE_FULL,dropped_frame",
            )
