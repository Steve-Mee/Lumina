"""Native NT OHLC frames for charts and MTF snapshots. No pandas resample SSOT."""

from __future__ import annotations

from typing import Any

import pandas as pd

from lumina_core.engine.nt_bar_periods import CHART_PANEL_NAMES, timeframe_to_period

_COLS = ["timestamp", "open", "high", "low", "close", "volume"]


def empty_ohlc() -> pd.DataFrame:
    return pd.DataFrame(columns=_COLS)


def operator_listing(app: Any, engine: Any | None = None) -> str:
    """Open-chart INSTRUMENT first, then config. Blank is named, never a silent MES prefix."""
    raw = getattr(app, "INSTRUMENT", None)
    if not raw and engine is not None:
        raw = getattr(getattr(engine, "config", None), "instrument", "")
    text = str(raw or "").strip()
    return text or "listing onbekend"


def concat_forming(closed: pd.DataFrame, forming: dict[str, Any] | None) -> pd.DataFrame:
    """Closed bars plus the live forming candle when its timestamp is new."""
    if forming is None:
        return closed.copy() if closed is not None else empty_ohlc()
    ts = forming.get("timestamp")
    if ts is None:
        return closed.copy() if closed is not None else empty_ohlc()
    row = {
        "timestamp": ts,
        "open": forming.get("open"),
        "high": forming.get("high"),
        "low": forming.get("low"),
        "close": forming.get("close"),
        "volume": forming.get("volume", 0),
    }
    if closed is None or closed.empty:
        out = pd.DataFrame([row], columns=_COLS)
    else:
        existing = closed.copy()
        if "timestamp" in existing.columns and (existing["timestamp"] == ts).any():
            existing = existing.loc[existing["timestamp"] != ts]
        out = pd.concat([existing, pd.DataFrame([row], columns=_COLS)], ignore_index=True)
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    return out.sort_values("timestamp").reset_index(drop=True)


def chart_frames(market_data: Any) -> dict[str, pd.DataFrame]:
    """Panel name → indexed native NT frame. Missing TF is omitted, never resampled."""
    copy_period = getattr(market_data, "copy_ohlc_period", None)
    frames: dict[str, pd.DataFrame] = {}
    for panel, period in CHART_PANEL_NAMES:
        if copy_period is None:
            break
        frame = copy_period(period, forming=True)
        if frame is None or frame.empty:
            continue
        indexed = frame.copy()
        indexed["timestamp"] = pd.to_datetime(indexed["timestamp"], utc=True)
        frames[panel] = indexed.set_index("timestamp")
    return frames


def snapshot_native(market_data: Any, timeframes: dict[str, int]) -> dict[str, dict[str, Any]]:
    """Last native bar per configured TF. Unsupported/missing TFs are honest zeros."""
    from lumina_core.engine.nt_bar_ssot import is_forming_bar

    copy_period = getattr(market_data, "copy_ohlc_period", None)
    out: dict[str, dict[str, Any]] = {}
    for tf_name, seconds in (timeframes or {}).items():
        period = timeframe_to_period(str(tf_name), int(seconds))
        zeros = {
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "volume": 0,
            "source": "missing",
            "forming": False,
        }
        if period is None or copy_period is None:
            out[tf_name] = zeros
            continue
        frame = copy_period(period, forming=True)
        if frame is None or frame.empty:
            out[tf_name] = zeros
            continue
        row = frame.iloc[-1]
        out[tf_name] = {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]),
            "source": f"nt:{period}",
            "forming": bool(is_forming_bar(row["timestamp"])),
        }
    return out
