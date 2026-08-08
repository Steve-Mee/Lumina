"""Pure/static helpers for historical bar fetch (M5 extract)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


class MarketDataHistoryHelpersMixin:
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

    @staticmethod
    def _is_historical_date_format_error(response_text: str) -> bool:
        """Detect NT8/CrossTrade date parse failures (often DD/MM/YYYY echo in error body)."""
        text = (response_text or "").lower()
        return (
            "date format" in text
            or "invalid 'from'" in text
            or "invalid 'to'" in text
        )

    @staticmethod
    def _sanitize_historical_payload_dates(payload: dict[str, Any]) -> dict[str, Any]:
        """Ensure from/to are strict ISO-8601 UTC (never locale DD/MM/YYYY)."""
        out = dict(payload)
        for key in ("from", "to"):
            raw = out.get(key)
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            if "T" in text and text.endswith("Z"):
                out[key] = text
                continue
            try:
                parsed = pd.to_datetime(text, utc=True)
                out[key] = MarketDataHistoryHelpersMixin._utc_iso_z(parsed.to_pydatetime())
            except Exception:
                out[key] = text
        return out

    @staticmethod
    def _utc_day_floor(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _merge_bars_into(
        merged: list[dict[str, Any]],
        bars: list[dict[str, Any]],
        *,
        seen_epoch: set[int],
        seen_time: set[str],
        target_cap: int | None,
    ) -> None:
        for bar in bars:
            if target_cap is not None and len(merged) >= target_cap:
                return
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

    @staticmethod
    def _sort_and_cap_bars(bars: list[dict[str, Any]], target_cap: int | None) -> list[dict[str, Any]]:
        if not bars:
            return []

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

        sorted_bars = sorted(bars, key=_bar_sort_key)
        if target_cap is not None:
            return sorted_bars[:target_cap]
        return sorted_bars

