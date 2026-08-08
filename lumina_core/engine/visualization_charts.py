"""Chart / screen-share helpers for VisualizationService (global residual)."""
from __future__ import annotations

import base64
import json
import queue
import threading
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
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
    def _create_photo_image(pil_img: Image.Image) -> Any:
        from PIL import ImageTk

        return ImageTk.PhotoImage(pil_img)
    def _record_live_stream_chart_frame(self, *, base64_char_len: int) -> None:
        """Append a JSONL heartbeat so the Streamlit launcher can detect chart frames (state/live_stream.jsonl)."""
        path = Path(self.engine.config.live_jsonl)
        line = json.dumps(
            {
                "ts": datetime.now().isoformat(timespec="seconds"),
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

        with self.engine.live_data_lock:
            if len(self.engine.ohlc_1min) < 200:
                app.logger.info(
                    "LIVE_FEED_CHART_GEN_ABORT,stage=ohlc_gate,reason=insufficient_data,bars=%s,min_required=200",
                    len(self.engine.ohlc_1min),
                )
                app.logger.info("CHART_GEN_SKIPPED,reason=insufficient_data")
                return None
            df = self.engine.ohlc_1min.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)

        tfs = [
            ("1min", "1min"),
            ("5min", "5min"),
            ("15min", "15min"),
            ("30min", "30min"),
            ("60min", "60min"),
            ("240min", "240min"),
        ]
        fig = make_subplots(
            rows=3,
            cols=2,
            subplot_titles=[name for name, _ in tfs],
            vertical_spacing=0.08,
            horizontal_spacing=0.05,
        )

        row_col = [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2)]
        recent = self.engine.ohlc_1min.iloc[-60:]
        swing_low = float(recent["low"].min())
        swing_high = float(recent["high"].max())
        diff = swing_high - swing_low
        fib_levels: dict[str, float] = {}
        for ratio in [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]:
            fib_levels[str(ratio)] = round(swing_high - diff * ratio, 2)

        structure = self.engine.detect_market_structure(self.engine.ohlc_1min)

        for i, (tf_name, freq) in enumerate(tfs):
            res = (
                df.resample(freq)
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
            )
            if len(res) < 20:
                continue
            row, col = row_col[i]
            subplot_row: Any = row
            subplot_col: Any = col

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

            if tf_name in ["1min", "15min"]:
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

            if ai_fibs and tf_name in ["1min", "15min"]:
                for ratio, price in ai_fibs.items():
                    fig.add_hline(
                        y=float(price),
                        line_dash="solid",
                        line_color="#00ff00",
                        annotation_text=f"AI Fib {ratio}",
                        row=subplot_row,
                        col=subplot_col,
                    )

            if structure.get("bos"):
                fig.add_hline(
                    y=swing_high if "bullish" in str(structure["bos"]) else swing_low,
                    line_color="#00ffff",
                    line_width=2,
                    annotation_text=str(structure["bos"]),
                    row=subplot_row,
                    col=subplot_col,
                )
            if structure.get("choch"):
                fig.add_hline(
                    y=swing_high,
                    line_color="#ff00ff",
                    line_width=2,
                    annotation_text="CHOCH",
                    row=subplot_row,
                    col=subplot_col,
                )

            order_blocks = structure.get("order_blocks", [])
            if len(order_blocks) >= 2:
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
        regime = self.engine.detect_market_regime(df.reset_index())
        instrument = getattr(app, "INSTRUMENT", self.engine.config.instrument)
        fig.update_layout(
            title=f"LUMINA v24 – MES {instrument} | Prijs {current_price:.2f} | Regime: {regime} | AI Fibs getekend | {datetime.now().strftime('%d %b %H:%M')}",
            height=900,
            width=1400,
            showlegend=False,
            template="plotly_dark",
            margin=dict(l=40, r=40, t=100, b=40),
        )

        img_bytes = BytesIO()
        app.logger.info("LIVE_FEED_CHART_GEN_STEP,stage=plotly_write_image,format=png,scale=2")
        try:
            fig.write_image(img_bytes, format="png", scale=2)
        except Exception as exc:
            app.logger.warning("CHART_GEN_EXPORT_SKIPPED,reason=%s", exc)
            app.logger.warning(
                "LIVE_FEED_CHART_GEN_ABORT,stage=export_png,reason=kaleido_or_static_image_failed,detail=%s",
                exc,
            )
            return None
        img_bytes.seek(0)
        base64_img = base64.b64encode(img_bytes.read()).decode("utf-8")
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
    def start_screen_share_window(self) -> None:
        app = self._app()
        if not bool(getattr(app, "SCREEN_SHARE_ENABLED", self.engine.config.screen_share_enabled)):
            app.logger.info("LIVE_FEED_BOOT_SKIP,component=tk_screen_share,reason=screen_share_disabled_in_config")
            return

        app.logger.info("LIVE_FEED_BOOT_STEP,component=tk_screen_share,action=spawn_daemon_thread")

        def create_window() -> None:
            try:
                import tkinter as tk
            except Exception as exc:
                app.logger.warning(
                    "LIVE_FEED_BOOT_ABORT,component=tk_screen_share,reason=tkinter_import_failed,detail=%s",
                    exc,
                )
                app.logger.warning("Screen-share window disabled: tkinter unavailable (%s)", exc)
                return

            root = tk.Tk()
            root.title("LUMINA Live Trader Screen Share – Clean Professional View")
            root.attributes("-topmost", True)
            root.geometry("1480x920")
            root.configure(bg="#0a0a0a")

            title = tk.Label(
                root,
                text="LUMINA Live Trader Screen Share",
                font=("Consolas", 18, "bold"),
                fg="#00ff88",
                bg="#0a0a0a",
            )
            title.pack(pady=8)

            chart_label = tk.Label(root, bg="#0a0a0a")
            chart_label.pack(padx=20, pady=10, fill="both", expand=True)
            root_any: Any = root
            root_any.chart_label = chart_label

            status_frame = tk.Frame(root, bg="#0a0a0a")
            status_frame.pack(fill="x", padx=20, pady=10)

            status_dot = tk.Label(status_frame, text="●", font=("Consolas", 22), fg="#00ff88", bg="#0a0a0a")
            status_dot.pack(side="left")
            root_any.status_dot = status_dot

            status_text = tk.Label(
                status_frame,
                text="AI Decision & Chart updated",
                font=("Consolas", 14),
                fg="#00ff88",
                bg="#0a0a0a",
            )
            status_text.pack(side="left", padx=12)
            root_any.status_text = status_text

            last_update = tk.Label(
                status_frame,
                text="Laatste update: —",
                font=("Consolas", 11),
                fg="#888888",
                bg="#0a0a0a",
            )
            last_update.pack(side="right")
            root_any.last_update = last_update

            def pump_chart_updates() -> None:
                had_work = False
                try:
                    while True:
                        try:
                            item = self._tk_chart_queue.get_nowait()
                        except queue.Empty:
                            break
                        had_work = True
                        if not item or item[0] != "frame" or len(item) < 3:
                            continue
                        _, chart_b64, smsg = item[0], item[1], item[2]
                        try:
                            app.logger.info(
                                "LIVE_FEED_TK_STEP,stage=decode_resize_apply,b64_chars=%s",
                                len(chart_b64),
                            )
                            img_data = base64.b64decode(chart_b64)
                            pil_img = Image.open(BytesIO(img_data)).resize(
                                (1400, 800), Image.Resampling.LANCZOS
                            )
                            with self.chart_update_lock:
                                photo = self._create_photo_image(pil_img)
                                self.latest_chart_image = photo
                                setattr(app, "latest_chart_image", photo)
                                chart_label.config(image=photo)
                                chart_label.image = photo
                                status_dot.config(fg="#00ff88")
                                status_text.config(text=smsg, fg="#00ff88")
                                last_update.config(
                                    text=f"Laatste update: {datetime.now().strftime('%H:%M:%S')}"
                                )
                            app.logger.info("LIVE_FEED_TK_OK,stage=label_updated")
                        except Exception as exc:
                            app.logger.error("LIVE_FEED_TK_ABORT,stage=apply_image,reason=%s", exc)
                            app.logger.error("Screen-share update error: %s", exc)
                            try:
                                status_dot.config(fg="#ff4444")
                                status_text.config(text="ERROR – zie log", fg="#ff4444")
                            except Exception:
                                pass
                finally:
                    try:
                        root.after(50 if had_work else 150, pump_chart_updates)
                    except Exception:
                        pass

            self.live_chart_window = root
            setattr(app, "live_chart_window", root)
            app.logger.info(
                "LIVE_FEED_BOOT_OK,component=tk_screen_share,stage=window_ready,title=%s",
                root.title(),
            )
            app.logger.info(
                "[%s] Clean readable screen-share opened",
                datetime.now().strftime("%H:%M:%S"),
            )
            root.after(50, pump_chart_updates)
            root.mainloop()

        threading.Thread(target=create_window, daemon=True).start()
    def update_live_chart(self, chart_base64: str, status_msg: str = "AI Decision & Chart updated") -> None:
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
