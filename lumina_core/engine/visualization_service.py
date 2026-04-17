from __future__ import annotations

import base64
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any, Callable

from PIL import Image, ImageTk
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class VisualizationService:
    """Owns live screen-share state and compatibility dashboard launching."""

    engine: LuminaEngine
    dashboard_launcher: Callable[[], None] | None = None
    live_chart_window: Any = None
    latest_chart_image: Any = None
    chart_update_lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("VisualizationService requires a LuminaEngine")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def start_dashboard(self) -> None:
        if self.dashboard_launcher is None:
            raise RuntimeError("VisualizationService.dashboard_launcher is not configured")
        self.dashboard_launcher()

    def generate_multi_tf_chart(self, ai_fibs: dict | None = None) -> str | None:
        app = self._app()
        start_time = time.perf_counter()

        with self.engine.live_data_lock:
            if len(self.engine.ohlc_1min) < 200:
                app.logger.info("CHART_GEN_SKIPPED,reason=insufficient_data")
                return None
            df = self.engine.ohlc_1min.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)

        tfs = [("1min", "1min"), ("5min", "5min"), ("15min", "15min"), ("30min", "30min"), ("60min", "60min"), ("240min", "240min")]
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
                    if ratio in ["0.382", "0.618", "0.786"]:
                        fig.add_hline(y=float(price), line_dash="dash", line_color="#ffff00", annotation_text=f"Bot Fib {ratio}", row=subplot_row, col=subplot_col)

            if ai_fibs and tf_name in ["1min", "15min"]:
                for ratio, price in ai_fibs.items():
                    fig.add_hline(y=float(price), line_dash="solid", line_color="#00ff00", annotation_text=f"AI Fib {ratio}", row=subplot_row, col=subplot_col)

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
                fig.add_hline(y=swing_high, line_color="#ff00ff", line_width=2, annotation_text="CHOCH", row=subplot_row, col=subplot_col)

            order_blocks = structure.get("order_blocks", [])
            if len(order_blocks) >= 2:
                fig.add_hline(y=order_blocks[0]["price"], line_color="#ff8800", line_dash="dot", annotation_text="Bull OB", row=subplot_row, col=subplot_col)
                fig.add_hline(y=order_blocks[1]["price"], line_color="#ff8800", line_dash="dot", annotation_text="Bear OB", row=subplot_row, col=subplot_col)

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
        try:
            fig.write_image(img_bytes, format="png", scale=2)
        except Exception as exc:
            app.logger.warning(f"CHART_GEN_EXPORT_SKIPPED,reason={exc}")
            return None
        img_bytes.seek(0)
        base64_img = base64.b64encode(img_bytes.read()).decode("utf-8")

        if bool(getattr(app, "SCREEN_SHARE_ENABLED", self.engine.config.screen_share_enabled)):
            self.update_live_chart(base64_img)

        duration_ms = (time.perf_counter() - start_time) * 1000
        app.logger.info(
            f"CHART_GEN_COMPLETE,duration_ms={duration_ms:.0f},base64_kb={len(base64_img)//1000},screen_share_updated=YES"
        )
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🖼️ v28 Chart gegenereerd + screen-share geupdatet")
        return base64_img

    def start_screen_share_window(self) -> None:
        app = self._app()
        if not bool(getattr(app, "SCREEN_SHARE_ENABLED", self.engine.config.screen_share_enabled)):
            return

        def create_window() -> None:
            root = app.tk.Tk()
            root.title("LUMINA Live Trader Screen Share – Clean Professional View")
            root.attributes("-topmost", True)
            root.geometry("1480x920")
            root.configure(bg="#0a0a0a")

            title = app.tk.Label(
                root,
                text="LUMINA Live Trader Screen Share",
                font=("Consolas", 18, "bold"),
                fg="#00ff88",
                bg="#0a0a0a",
            )
            title.pack(pady=8)

            chart_label = app.tk.Label(root, bg="#0a0a0a")
            chart_label.pack(padx=20, pady=10, fill="both", expand=True)
            root_any: Any = root
            root_any.chart_label = chart_label

            status_frame = app.tk.Frame(root, bg="#0a0a0a")
            status_frame.pack(fill="x", padx=20, pady=10)

            status_dot = app.tk.Label(status_frame, text="●", font=("Consolas", 22), fg="#00ff88", bg="#0a0a0a")
            status_dot.pack(side="left")
            root_any.status_dot = status_dot

            status_text = app.tk.Label(
                status_frame,
                text="AI Decision & Chart updated",
                font=("Consolas", 14),
                fg="#00ff88",
                bg="#0a0a0a",
            )
            status_text.pack(side="left", padx=12)
            root_any.status_text = status_text

            last_update = app.tk.Label(
                status_frame,
                text="Laatste update: —",
                font=("Consolas", 11),
                fg="#888888",
                bg="#0a0a0a",
            )
            last_update.pack(side="right")
            root_any.last_update = last_update

            self.live_chart_window = root
            setattr(app, "live_chart_window", root)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🖥️ Schone & goed leesbare screen-share geopend")
            root.mainloop()

        threading.Thread(target=create_window, daemon=True).start()

    def update_live_chart(self, chart_base64: str, status_msg: str = "AI Decision & Chart updated") -> None:
        app = self._app()
        if not bool(getattr(app, "SCREEN_SHARE_ENABLED", self.engine.config.screen_share_enabled)) or not self.live_chart_window:
            return

        try:
            img_data = base64.b64decode(chart_base64)
            pil_img = Image.open(BytesIO(img_data)).resize((1400, 800), Image.Resampling.LANCZOS)
            with self.chart_update_lock:
                win: Any = self.live_chart_window
                self.latest_chart_image = ImageTk.PhotoImage(pil_img)
                setattr(app, "latest_chart_image", self.latest_chart_image)
                win.chart_label.config(image=self.latest_chart_image)
                win.chart_label.image = self.latest_chart_image
                win.status_dot.config(fg="#00ff88")
                win.status_text.config(text=status_msg, fg="#00ff88")
                win.last_update.config(text=f"Laatste update: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as exc:
            app.logger.error(f"Screen-share update error: {exc}")
            if self.live_chart_window:
                win = self.live_chart_window
                win.status_dot.config(fg="#ff4444")
                win.status_text.config(text="ERROR – zie log", fg="#ff4444")
