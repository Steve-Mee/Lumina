"""Tk screen-share window. Not always-on-top so other windows can come forward."""
from __future__ import annotations

import base64
import queue
import threading
from datetime import datetime
from io import BytesIO
from typing import Any

from PIL import Image

SCREEN_SHARE_TITLE = "LUMINA Live Trader Screen Share – Clean Professional View"


def spawn_screen_share_window(host: Any) -> None:
    app = host._app()
    if not bool(getattr(app, "SCREEN_SHARE_ENABLED", host.engine.config.screen_share_enabled)):
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
        root.title(SCREEN_SHARE_TITLE)
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

        chart_label = tk.Label(
            root,
            text="Wachten op de eerste NT-grafiek",
            font=("Consolas", 16),
            fg="#c8c8c8",
            bg="#0a0a0a",
        )
        chart_label.pack(padx=20, pady=10, fill="both", expand=True)
        root_any: Any = root
        root_any.chart_label = chart_label

        status_frame = tk.Frame(root, bg="#0a0a0a")
        status_frame.pack(fill="x", padx=20, pady=10)

        status_dot = tk.Label(status_frame, text="●", font=("Consolas", 22), fg="#ffcc66", bg="#0a0a0a")
        status_dot.pack(side="left")
        root_any.status_dot = status_dot

        status_text = tk.Label(
            status_frame,
            text="Nog geen grafiek",
            font=("Consolas", 14),
            fg="#ffcc66",
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
                        item = host._tk_chart_queue.get_nowait()
                    except queue.Empty:
                        break
                    had_work = True
                    if not item:
                        continue
                    if item[0] == "status" and len(item) >= 2:
                        message = str(item[1])
                        status_dot.config(fg="#ffcc66")
                        status_text.config(text=message, fg="#ffcc66")
                        chart_label.config(text=message)
                        continue
                    if item[0] != "frame" or len(item) < 3:
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
                        with host.chart_update_lock:
                            photo = host._create_photo_image(pil_img)
                            host.latest_chart_image = photo
                            setattr(app, "latest_chart_image", photo)
                            chart_label.config(image=photo, text="")
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

        host.live_chart_window = root
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
