"""Load real historical bars/ticks for Birth Phase v2."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Callable

from lumina_core.birth.data_source_honesty import resolved_tick_source
from lumina_core.logging_utils import get_logger

FABRIC_SOURCE_LABEL = "real"

logger = get_logger("lumina.birth.history")


def _parse_tick_timestamp(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def actual_calendar_days_from_ticks(ticks: Sequence[dict[str, Any]] | None) -> int:
    """Calendar span (UTC days) covered by tick timestamps — authoritative loaded depth."""
    if not ticks:
        return 0
    stamps: list[datetime] = []
    for row in ticks:
        if not isinstance(row, dict):
            continue
        parsed = _parse_tick_timestamp(row.get("timestamp"))
        if parsed is not None:
            stamps.append(parsed)
    if len(stamps) < 2:
        return 1 if stamps else 0
    span_sec = max(0.0, (max(stamps) - min(stamps)).total_seconds())
    return max(1, int(span_sec // 86_400) + 1)


def resolve_unique_calendar_days(
    cached: int = 0,
    *,
    manifest: Mapping[str, Any] | None = None,
    ticks: Sequence[dict[str, Any]] | None = None,
    progress: Mapping[str, Any] | None = None,
) -> int:
    """SSOT unique days for Foundation replay-cap. Never treat 0 as a cached hit."""
    candidates: list[Any] = [
        cached,
        (manifest or {}).get("actual_calendar_days") if manifest is not None else None,
        (progress or {}).get("foundation_unique_calendar_days") if progress is not None else None,
        (progress or {}).get("actual_calendar_days") if progress is not None else None,
    ]
    for raw in candidates:
        try:
            days = int(raw or 0)
        except (TypeError, ValueError):
            days = 0
        if days > 0:
            return days
    return actual_calendar_days_from_ticks(ticks)


def session_unique_calendar_days(
    *,
    cached: int,
    host: Any,
    ticks: Sequence[dict[str, Any]] | None,
) -> int:
    """Resolve unique days for a live stage-loop session. Does not copy ticks unless needed."""
    raw_manifest = getattr(host, "_data_manifest", None)
    manifest = raw_manifest if isinstance(raw_manifest, Mapping) else None
    days = resolve_unique_calendar_days(int(cached or 0), manifest=manifest)
    if days > 0:
        return days
    progress: Mapping[str, Any] | None = None
    try:
        from lumina_core.birth.progress import read_birth_progress

        root = getattr(host, "workspace_root", None)
        if root is not None:
            loaded = read_birth_progress(root)
            if isinstance(loaded, dict):
                progress = loaded
    except Exception:
        progress = None
    return resolve_unique_calendar_days(0, manifest=manifest, ticks=ticks, progress=progress)


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
                "source": resolved_tick_source(row, default_if_empty=source_label),
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
    instrument: str | None = None,
) -> list[dict[str, Any]]:
    source = market_data_service
    if source is not None and hasattr(source, "load_historical_ohlc_extended"):
        try:
            # Short windows can use a single daysBack call; longer birth loads must
            # paginate past the ~8k bar early-return (prefer_daysback_only=True).
            days_back_i = max(1, int(days_back))
            prefer_daysback_only = days_back_i <= 14
            fetch_kwargs: dict[str, Any] = {
                "days_back": days_back_i,
                "limit": limit,
                "ticks_per_bar": 4,
                "on_chunk": on_chunk,
                "prefer_daysback_only": prefer_daysback_only,
            }
            symbol = str(instrument or "").strip()
            if symbol:
                fetch_kwargs["instrument"] = symbol
            rows = source.load_historical_ohlc_extended(**fetch_kwargs)
            if isinstance(rows, list):
                return normalize_tick_rows(rows, source_label=FABRIC_SOURCE_LABEL)
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
    return normalize_tick_rows(records, source_label=FABRIC_SOURCE_LABEL)
