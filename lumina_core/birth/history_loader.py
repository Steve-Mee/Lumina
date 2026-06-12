"""Load real historical bars/ticks for Birth Phase v2."""

from __future__ import annotations

from typing import Any, Callable

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.history")


def normalize_tick_rows(rows: list[dict[str, Any]], *, source_label: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            price = float(
                row.get("last")
                or row.get("close")
                or row.get("price")
                or row.get("ask")
                or 0.0
            )
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        normalized.append(
            {
                "timestamp": str(row.get("timestamp", "")),
                "last": price,
                "close": price,
                "bid": float(row.get("bid", price - 0.125) or price - 0.125),
                "ask": float(row.get("ask", price + 0.125) or price + 0.125),
                "volume": int(row.get("volume", 1) or 1),
                "regime": str(row.get("regime", "NEUTRAL")),
                "imbalance": float(row.get("imbalance", 1.0) or 1.0),
                "source": source_label,
            }
        )
    return normalized


def load_historical_ticks(
    *,
    market_data_service: Any,
    runtime: Any,
    days_back: int,
    limit: int | None,
    on_chunk: Callable[..., None] | None = None,
) -> list[dict[str, Any]]:
    source = market_data_service
    if source is not None and hasattr(source, "load_historical_ohlc_extended"):
        try:
            rows = source.load_historical_ohlc_extended(
                days_back=days_back,
                limit=limit,
                ticks_per_bar=4,
                on_chunk=on_chunk,
            )
            if isinstance(rows, list):
                return normalize_tick_rows(rows, source_label="real_historical")
        except Exception as exc:
            logger.warning("birth.history.load_extended_failed detail=%s", exc, exc_info=True)

    ohlc = getattr(runtime, "ohlc_1min", None)
    if ohlc is None:
        return []
    try:
        tail_limit = limit if limit is not None else len(ohlc)
        records = ohlc.tail(tail_limit).to_dict("records")
    except Exception:
        return []
    return normalize_tick_rows(records, source_label="real_runtime")
