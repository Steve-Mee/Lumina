"""Canonical NinjaTrader minute periods Lumina is allowed to subscribe (ADR-0054)."""

from __future__ import annotations

# Native NT Minute values with instrument TradingHours + IsResetOnNewTradingDay.
# pandas resample("240min") is a different series and is not a substitute.
CANONICAL_LIVE: tuple[str, ...] = ("1m", "5m", "15m", "30m", "60m", "240m")

_ALIASES: dict[str, str] = {
    "": "1m",
    "1": "1m",
    "1m": "1m",
    "1min": "1m",
    "minute": "1m",
    "5": "5m",
    "5m": "5m",
    "5min": "5m",
    "15": "15m",
    "15m": "15m",
    "15min": "15m",
    "30": "30m",
    "30m": "30m",
    "30min": "30m",
    "60": "60m",
    "60m": "60m",
    "60min": "60m",
    "1h": "60m",
    "240": "240m",
    "240m": "240m",
    "240min": "240m",
    "4h": "240m",
}

# NT BarsRequest LiveBarsBack — smaller on higher TF so we do not storm HDS.
LIVE_BARS_BACK: dict[str, int] = {
    "1m": 2000,
    "5m": 1500,
    "15m": 1000,
    "30m": 800,
    "60m": 500,
    "240m": 400,
}

PERIOD_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "60m": 3600,
    "240m": 14400,
}

CHART_PANEL_NAMES: tuple[tuple[str, str], ...] = (
    ("1min", "1m"),
    ("5min", "5m"),
    ("15min", "15m"),
    ("30min", "30m"),
    ("60min", "60m"),
    ("240min", "240m"),
)


def canonicalize_period(raw: str | None) -> str | None:
    """Return canonical ``1m``/``5m``/… or None when the period is unsupported."""
    token = str(raw or "").strip().lower().replace(" ", "")
    return _ALIASES.get(token)


def require_period(raw: str | None) -> str:
    canonical = canonicalize_period(raw)
    if canonical is None:
        raise ValueError(f"unsupported bar_period {raw!r}")
    return canonical


def minute_value(period: str) -> int:
    canonical = require_period(period)
    return PERIOD_SECONDS[canonical] // 60


def live_bars_back(period: str) -> int:
    return int(LIVE_BARS_BACK[require_period(period)])


def timeframe_to_period(tf_name: str, seconds: int | None = None) -> str | None:
    """Map engine_config timeframe names (``5min``) onto a native NT period."""
    name = str(tf_name or "").strip().lower()
    if name.endswith("min"):
        try:
            minutes = int(name[:-3] or "0")
        except ValueError:
            minutes = 0
        return canonicalize_period(f"{minutes}m") if minutes else None
    if seconds is not None:
        return canonicalize_period(f"{int(seconds) // 60}m")
    return canonicalize_period(name)
