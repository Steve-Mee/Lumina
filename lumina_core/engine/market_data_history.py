"""Market-data history façade — load/expand/gap-recovery (Wave B3 PR-D0).

Fetch/post helpers live in ``market_data_history_fetch``. Public mixin path and
MDS monkeypatch hooks (``_mds`` late-bind) remain stable.
"""

from __future__ import annotations

import time
import traceback
from typing import Any, Callable

import pandas as pd

from .errors import ErrorSeverity, LuminaError, log_structured
from .market_data_history_fetch import MarketDataHistoryFetchMixin, _mds

__all__ = ["MarketDataHistoryMixin", "MarketDataHistoryFetchMixin", "_mds"]


class MarketDataHistoryMixin(MarketDataHistoryFetchMixin):
    """Historical OHLC fetch/expand helpers mixed into MarketDataIngestService."""

    __slots__ = ()

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
        prefer_daysback_only: bool = False,
        instrument: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load historical bars and expand each bar into pseudo ticks.

        Crosstrade historical endpoint is bar-based; this creates a deterministic
        tick stream (open/high/low/close path) for simulation workloads.
        Optional ``instrument`` fetches a specific listing (Birth stitch); default
        remains the engine front month. Stitch orchestration lives in Birth, not here.
        """
        app = self._app()
        requested = str(instrument or "").strip()
        instrument = self._normalize_symbol(
            requested or getattr(app, "INSTRUMENT", self.engine.config.instrument)
        )
        try:
            bars = self._fetch_historical_bars(
                instrument=instrument,
                days_back=days_back,
                limit=limit,
                on_chunk=on_chunk,
                prefer_daysback_only=prefer_daysback_only,
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
