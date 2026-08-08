"""Bootstrap OHLC validation helpers."""
from __future__ import annotations

from typing import Any

from lumina_core.container import ApplicationContainer

def _validate_bootstrapped_ohlc(container: ApplicationContainer) -> None:
    """Log structured quality checks on primary ``ohlc_1min`` after historical bootstrap."""
    import pandas as pd

    logger = container.logger
    df = getattr(container.engine, "ohlc_1min", None)
    rows = len(df) if df is not None else 0
    issues: list[str] = []
    span_h = 0.0
    t_first = ""
    t_last = ""

    if df is None or rows == 0:
        issues.append("primary_ohlc_empty")
    else:
        if rows < 120:
            issues.append(f"primary_rows_low:{rows}")
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], errors="coerce").dropna()
            if len(ts) >= 2:
                span_h = float((ts.max() - ts.min()).total_seconds() / 3600.0)
                t_first = str(ts.iloc[0])
                t_last = str(ts.iloc[-1])
                if span_h < 2.0:
                    issues.append(f"span_hours_low:{span_h:.2f}")
                if not bool(ts.is_monotonic_increasing):
                    issues.append("timestamps_not_sorted")
                dup = int(ts.duplicated().sum())
                if dup > 0:
                    issues.append(f"duplicate_timestamps:{dup}")
            elif len(ts) < 2:
                issues.append("timestamps_insufficient")
        for col in ("open", "high", "low", "close"):
            if col in df.columns and bool(df[col].isna().any()):
                issues.append(f"nan_{col}")
        if "high" in df.columns and "low" in df.columns:
            try:
                if bool((df["high"] < df["low"]).any()):
                    issues.append("high_lt_low_rows")
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/bootstrap.py:66")
                issues.append("ohlc_compare_failed")
        if "volume" in df.columns:
            try:
                if bool((df["volume"] < 0).any()):
                    issues.append("negative_volume")
            except Exception:
                logger.exception("Bootstrap OHLC quality check failed during negative volume validation")

    status = "ok"
    if issues:
        status = "fail" if "primary_ohlc_empty" in issues else "degraded"

    logger.info(
        "BOOTSTRAP_OHLC_QUALITY,status=%s,primary_rows=%d,span_hours=%.2f,t_first=%s,t_last=%s,issues=%s",
        status,
        rows,
        span_h,
        (t_first[:28] if t_first else ""),
        (t_last[:28] if t_last else ""),
        ";".join(issues) if issues else "none",
    )
    if status == "fail":
        logger.error(
            "BOOTSTRAP_OHLC_QUALITY | Geen historische 1m-bars voor primair instrument — "
            "controleer CROSSTRADE_TOKEN, instrument en netwerk."
        )
    elif status == "degraded":
        logger.warning(
            "BOOTSTRAP_OHLC_QUALITY | Data geladen maar kwaliteit kan onvoldoende zijn voor RL/neuro (zie issues). "
            "Overweeg echte simulator-data, meer historie, of symbolavailability."
        )


