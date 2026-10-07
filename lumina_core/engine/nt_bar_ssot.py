"""NinjaTrader Last bars are the only decision OHLC (ADR-0053 / ADR-0054)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.engine.nt_bar_periods import canonicalize_period
from lumina_core.engine.ohlc_clock import utc_from_any

_REQUIRED = ("open", "high", "low", "close")


class BarRejected(ValueError):
    """Fail-closed: this row is not a usable NT bar."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


def _px(raw: Any, *, field: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise BarRejected("ohlc_nan", f"{field} is not a number") from exc
    if value != value or value in (float("inf"), float("-inf")):
        raise BarRejected("ohlc_nan", f"{field} is not finite")
    return value


def validate_nt_bar(raw: dict[str, Any]) -> dict[str, Any]:
    """Canonical NT Last bar. Missing high/low is a reject, never last-fill."""
    if not isinstance(raw, dict):
        raise BarRejected("not_a_bar", "bar is not a dict")
    period = canonicalize_period(raw.get("bar_period") or "1m")
    if period is None:
        raise BarRejected("bar_period_unsupported", "unsupported bar_period")
    ts = utc_from_any(raw.get("timestamp") or raw.get("time") or raw.get("timestamp_unix_ms"))
    if ts is None:
        raise BarRejected("timestamp_missing", "bar timestamp missing")

    missing = [name for name in _REQUIRED if name not in raw or raw.get(name) is None]
    if missing:
        raise BarRejected("ohlc_missing", f"missing {','.join(missing)}")

    opened = _px(raw.get("open"), field="open")
    high = _px(raw.get("high"), field="high")
    low = _px(raw.get("low"), field="low")
    close = _px(raw.get("close"), field="close")
    if close <= 0.0 or opened <= 0.0 or high <= 0.0 or low <= 0.0:
        raise BarRejected("ohlc_non_positive", "OHLC must be > 0")
    if high < max(opened, close) or low > min(opened, close) or high < low:
        raise BarRejected("ohlc_inconsistent", "high/low does not contain open/close")
    try:
        volume = float(raw.get("volume") or 0.0)
    except (TypeError, ValueError) as exc:
        raise BarRejected("volume_nan", "volume is not a number") from exc
    if volume < 0.0 or volume != volume:
        raise BarRejected("volume_nan", "volume must be >= 0")

    return {
        "timestamp": ts,
        "open": opened,
        "high": high,
        "low": low,
        "close": close,
        "volume": int(volume),
        "bar_period": period,
    }


def skip_ratio_fail(accepted: int, rejected: int, *, max_ratio: float = 0.05) -> bool:
    """True when too many source rows were not honest NT bars."""
    total = int(accepted) + int(rejected)
    if total <= 0:
        return True
    if int(accepted) <= 0:
        return True
    return (int(rejected) / float(total)) > float(max_ratio)


def accept_source_bars(bars: list[Any] | tuple[Any, ...] | None) -> tuple[list[dict[str, Any]], int]:
    """Validate every source row. Rejects are counted; last-fill never happens here."""
    accepted: list[dict[str, Any]] = []
    rejected = 0
    for raw in bars or []:
        if not isinstance(raw, dict):
            rejected += 1
            continue
        try:
            accepted.append(validate_nt_bar(raw))
        except BarRejected:
            rejected += 1
    return accepted, rejected


def is_forming_bar(ts: Any, now: datetime | None = None) -> bool:
    """NT stamps the close time. A timestamp still in the future is forming, not closed."""
    parsed = utc_from_any(ts)
    if parsed is None:
        return True
    if now is None:
        now_utc = datetime.now(timezone.utc)
    else:
        now_utc = utc_from_any(now)
        if now_utc is None:
            return True
    return parsed > now_utc


def is_recent_closed_bar(
    ts: Any,
    *,
    now: datetime | None = None,
    max_age_sec: float = 120.0,
) -> bool:
    """True when a closed NT bar is live enough for Playground (not hydrate replay)."""
    parsed = utc_from_any(ts)
    if parsed is None:
        return False
    if now is None:
        now_utc = datetime.now(timezone.utc)
    else:
        now_utc = utc_from_any(now)
        if now_utc is None:
            return False
    if is_forming_bar(parsed, now_utc):
        return False
    age = (now_utc - parsed).total_seconds()
    return -5.0 <= age <= float(max_age_sec)
