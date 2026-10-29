"""Fail-closed market / connection snapshot for the research SHADOW bridge."""

from __future__ import annotations

import math
from dataclasses import dataclass

STALE_OR_MISSING = "stale_or_missing_market"
LOST_CONNECTION = "lost_connection"
FRESH_BAR_MAX_AGE_SEC = 120.0


@dataclass(frozen=True, slots=True)
class MarketHealth:
    """Closed-bar + connection snapshot. Missing data is stale, not healthy."""

    connection_alive: bool
    forming_only: bool
    last_closed_close: float | None
    last_closed_age_sec: float | None
    max_age_sec: float = FRESH_BAR_MAX_AGE_SEC

    def allow_new_intents(self) -> tuple[bool, str]:
        if not self.connection_alive:
            return False, LOST_CONNECTION
        if self.forming_only:
            return False, STALE_OR_MISSING
        if self.last_closed_close is None:
            return False, STALE_OR_MISSING
        close = float(self.last_closed_close)
        if not math.isfinite(close) or close <= 0.0:
            return False, STALE_OR_MISSING
        age = self.last_closed_age_sec
        if age is None:
            return False, STALE_OR_MISSING
        age_sec = float(age)
        if not math.isfinite(age_sec) or age_sec < 0.0 or age_sec > float(self.max_age_sec):
            return False, STALE_OR_MISSING
        return True, "ok"

    def reference_price(self) -> float | None:
        allowed, _reason = self.allow_new_intents()
        if not allowed:
            return None
        return float(self.last_closed_close) if self.last_closed_close is not None else None


def unhealthy_market() -> MarketHealth:
    """Fail-closed default: no connection, forming-only book, no closed bar."""
    return MarketHealth(
        connection_alive=False,
        forming_only=True,
        last_closed_close=None,
        last_closed_age_sec=None,
    )


def healthy_closed_bar(*, close: float, age_sec: float = 1.0) -> MarketHealth:
    return MarketHealth(
        connection_alive=True,
        forming_only=False,
        last_closed_close=float(close),
        last_closed_age_sec=float(age_sec),
    )
