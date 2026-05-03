from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable

from lumina_core.engine.margin_snapshot_provider import MarginSnapshotProvider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_margin_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return ""
    return text.split(" ")[0]


@dataclass(slots=True)
class EquitySnapshot:
    equity_usd: float
    available_margin_usd: float
    used_margin_usd: float
    as_of_utc: datetime
    source: str
    ok: bool
    reason_code: str
    ttl_seconds: float
    from_cache: bool = False

    @property
    def age_seconds(self) -> float:
        return max(0.0, (_utcnow() - self.as_of_utc).total_seconds())

    @property
    def is_fresh(self) -> bool:
        return self.age_seconds <= self.ttl_seconds


@dataclass(slots=True)
class EquitySnapshotProvider:
    get_broker: Callable[[], Any | None]
    ttl_seconds: float = 30.0
    _last_success: EquitySnapshot | None = None
    _lock: Lock = Lock()

    def get_snapshot(self, *, force_refresh: bool = False) -> EquitySnapshot:
        now = _utcnow()
        with self._lock:
            if (
                not force_refresh
                and self._last_success is not None
                and self._last_success.age_seconds <= self.ttl_seconds
            ):
                cached = self._last_success
                return EquitySnapshot(
                    equity_usd=float(cached.equity_usd),
                    available_margin_usd=float(cached.available_margin_usd),
                    used_margin_usd=float(cached.used_margin_usd),
                    as_of_utc=cached.as_of_utc,
                    source=cached.source,
                    ok=True,
                    reason_code="ok_cached",
                    ttl_seconds=float(self.ttl_seconds),
                    from_cache=True,
                )

            fresh = self._fetch_live_snapshot(now=now)
            if fresh.ok:
                self._last_success = fresh
            return fresh

    def _fetch_live_snapshot(self, *, now: datetime) -> EquitySnapshot:
        broker = self.get_broker()
        if broker is None:
            return self._failure_snapshot(now=now, reason_code="broker_unavailable")

        get_account_info = getattr(broker, "get_account_info", None)
        if not callable(get_account_info):
            return self._failure_snapshot(now=now, reason_code="broker_missing_account_info")

        try:
            account = get_account_info()
        except Exception:
            return self._failure_snapshot(now=now, reason_code="broker_account_fetch_failed")

        source = type(broker).__name__
        equity = float(getattr(account, "equity", 0.0) or 0.0)
        if equity <= 0.0:
            return self._failure_snapshot(now=now, reason_code="equity_unavailable", source=source)

        available_margin = getattr(account, "available_margin", None)
        if available_margin is None:
            available_margin, used_margin = self._estimate_margins(broker=broker, equity=equity)
        else:
            available_margin = float(available_margin or 0.0)
            used_margin = max(0.0, equity - available_margin)

        if available_margin <= 0.0:
            return self._failure_snapshot(now=now, reason_code="available_margin_unavailable", source=source)

        return EquitySnapshot(
            equity_usd=equity,
            available_margin_usd=available_margin,
            used_margin_usd=max(0.0, used_margin),
            as_of_utc=now,
            source=source,
            ok=True,
            reason_code="ok_live",
            ttl_seconds=float(self.ttl_seconds),
            from_cache=False,
        )

    def _estimate_margins(self, *, broker: Any, equity: float) -> tuple[float, float]:
        get_positions = getattr(broker, "get_positions", None)
        if not callable(get_positions):
            return 0.0, 0.0

        try:
            positions = list(get_positions() or [])
        except Exception:
            return 0.0, 0.0

        default_margins = MarginSnapshotProvider.DEFAULT_MARGINS
        used_margin = 0.0
        for position in positions:
            quantity = abs(int(getattr(position, "quantity", 0) or 0))
            if quantity <= 0:
                continue
            symbol = _normalize_margin_symbol(str(getattr(position, "symbol", "") or ""))
            if not symbol:
                continue
            requirement = float(default_margins.get(symbol, equity * 0.03))
            used_margin += requirement * quantity
        available_margin = max(0.0, equity - used_margin)
        return available_margin, used_margin

    def _failure_snapshot(self, *, now: datetime, reason_code: str, source: str = "unknown") -> EquitySnapshot:
        return EquitySnapshot(
            equity_usd=0.0,
            available_margin_usd=0.0,
            used_margin_usd=0.0,
            as_of_utc=now,
            source=source,
            ok=False,
            reason_code=reason_code,
            ttl_seconds=float(self.ttl_seconds),
            from_cache=False,
        )
