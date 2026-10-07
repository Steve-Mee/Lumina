"""Market-data history façade — load/expand/gap-recovery (Wave B3 PR-D0).

Fetch/post helpers live in ``market_data_history_fetch``. Public mixin path and
MDS monkeypatch hooks (``_mds`` late-bind) remain stable.
"""

from __future__ import annotations

import time
import traceback
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from .errors import ErrorSeverity, LuminaError, log_structured
from .market_data_history_fetch import MarketDataHistoryFetchMixin, _mds

__all__ = ["MarketDataHistoryMixin", "MarketDataHistoryFetchMixin", "_mds"]


class MarketDataHistoryMixin(MarketDataHistoryFetchMixin):
    """Historical OHLC fetch/expand helpers mixed into MarketDataIngestService."""

    __slots__ = ()

    def load_historical_ohlc(
        self, days_back: int = 3, limit: int = 5000, *, now: datetime | None = None
    ) -> bool:
        instrument = self._normalize_symbol(getattr(self._app(), "INSTRUMENT", self.engine.config.instrument))
        closed, forming = self._fetch_closed_and_forming(
            instrument=instrument, days_back=days_back, limit=limit, now=now
        )
        if closed.empty and forming is None:
            return False

        md = self.engine.market_data
        if not closed.empty:
            md.append_ohlc_rows(closed, now=now)
        if forming is not None:
            md.apply_nt_bar(forming, now=now)
        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message=(
                    f"Loaded {len(closed)} closed historical 1-min candles"
                    f"{' + forming current_candle' if forming is not None else ''}"
                    f" -> ohlc_1min now {len(md.ohlc_1min)} rows"
                ),
                context={
                    "closed": int(len(closed)),
                    "forming": forming is not None,
                },
            )
        )
        return True

    def load_historical_ohlc_for_symbol(
        self,
        instrument: str,
        days_back: int = 3,
        limit: int = 5000,
        *,
        now: datetime | None = None,
    ) -> pd.DataFrame:
        """Closed NT 1m bars only. A still-forming last bar is not historical."""
        closed, _forming = self._fetch_closed_and_forming(
            instrument=instrument, days_back=days_back, limit=limit, now=now
        )
        return closed

    def _fetch_closed_and_forming(
        self,
        instrument: str,
        days_back: int,
        limit: int,
        *,
        now: datetime | None = None,
    ) -> tuple[pd.DataFrame, dict[str, Any] | None]:
        from lumina_core.engine.market_data_manager import partition_closed_and_forming
        from lumina_core.engine.nt_bar_ssot import accept_source_bars, skip_ratio_fail

        empty = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        bars = self._fetch_historical_bars(instrument=instrument, days_back=days_back, limit=limit)
        rows, rejected = accept_source_bars(bars)
        if skip_ratio_fail(len(rows), rejected):
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                    code="MDS_HIST_SKIP_RATIO",
                    message="historical 1m load rejected: too many dishonest NT bars",
                    context={"accepted": len(rows), "rejected": rejected, "instrument": instrument},
                )
            )
            return empty, None
        if not rows:
            return empty, None
        return partition_closed_and_forming(pd.DataFrame(rows), now=now)

    def load_historical_ohlc_extended(
        self,
        days_back: int = 30,
        limit: int | None = 120000,
        ticks_per_bar: int = 4,
        on_chunk: Callable[..., None] | None = None,
        prefer_daysback_only: bool = False,
        instrument: str | None = None,
        *,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Load closed historical bars and expand each into pseudo ticks.

        A still-forming last NT bar is not a closed minute and is not expanded.
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

            from lumina_core.engine.nt_bar_ssot import accept_source_bars, is_forming_bar, skip_ratio_fail

            honest, rejected = accept_source_bars(bars)
            if skip_ratio_fail(len(honest), rejected):
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                        code="MDS_HIST_SKIP_RATIO",
                        message="historical 1m expand rejected: too many dishonest NT bars",
                        context={"accepted": len(honest), "rejected": rejected, "instrument": instrument},
                    )
                )
                return []

            closed = [bar for bar in honest if not is_forming_bar(bar["timestamp"], now)]
            if not closed:
                return []

            ticks: list[dict[str, Any]] = []
            total_bars = len(closed)
            expand_batch = 500
            for bar_index, bar in enumerate(closed):
                bar_ts = bar["timestamp"]
                o = float(bar["open"])
                h = float(bar["high"])
                low_price = float(bar["low"])
                c = float(bar["close"])
                v = max(1, int(bar.get("volume") or 1))

                # Price path with directional bias from open->close.
                path = [o, h, low_price, c]
                if c < o:
                    path = [o, low_price, h, c]
                if ticks_per_bar > 4:
                    extra = [c + (h - low_price) * 0.25, c - (h - low_price) * 0.25]
                    path.extend(extra[: max(0, ticks_per_bar - 4)])

                per_tick_vol = max(1, int(v / max(1, len(path))))
                cum_vol = 0
                walk = str(bar.get("history_walk") or "")
                for idx, px in enumerate(path):
                    cum_vol += per_tick_vol
                    spread = max(0.25, abs(h - low_price) * 0.02)
                    tick = {
                        "timestamp": (bar_ts + pd.Timedelta(seconds=idx * (60 / max(1, len(path))))).isoformat(),
                        "last": float(px),
                        "bid": float(px - spread / 2.0),
                        "ask": float(px + spread / 2.0),
                        "volume": int(cum_vol),
                    }
                    if walk:
                        tick["history_walk"] = walk
                    ticks.append(tick)
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
            time.sleep(30)
            try:
                from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
                    get_fabric_link_supervisor,
                )

                app = self._app()
                client = get_fabric_link_supervisor().get_client()
                instrument = str(
                    getattr(app, "INSTRUMENT", None)
                    or getattr(getattr(self.engine, "config", None), "instrument", "")
                    or ""
                ).strip()
                reconcile = getattr(self, "_reconcile_nt_book", None)
                if client is None or not instrument or reconcile is None:
                    continue
                reconcile(app, client, instrument)
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                    code="MDS_GAP_RECOVERY_007",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                self._app().logger.error(f"Gap recovery error: {exc}")
