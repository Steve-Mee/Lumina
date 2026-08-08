"""RegimeCalendarMixin (M5 extract)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from lumina_core.risk.regime_types import AdaptiveRegimePolicy, RegimeSnapshot


class RegimeCalendarMixin:
    def _spread_proxy_ticks(self, rows: pd.DataFrame, instrument: str) -> float:
        tick_size = 0.25
        if self.valuation_engine is not None:
            try:
                tick_size = float(self.valuation_engine.tick_size(instrument))
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/regime_detector.py:378")
                tick_size = 0.25

        last = rows.iloc[-1]
        explicit_spread = None
        for key in ("spread", "bid_ask_spread", "spread_points"):
            if key in rows.columns:
                try:
                    explicit_spread = float(last.get(key, 0.0) or 0.0)
                    break
                except Exception:
                    logging.exception("Unhandled broad exception fallback in lumina_core/engine/regime_detector.py:388")
                    explicit_spread = None
        if explicit_spread is None:
            explicit_spread = float((last.get("high", 0.0) - last.get("low", 0.0)) * 0.18)
        return explicit_spread / max(tick_size, 1e-9)

    @staticmethod
    def _slope_strength(series: pd.Series) -> float:
        if len(series) < 5:
            return 0.0
        values = [float(v) for v in series.tolist()]
        mean_x = (len(values) - 1) / 2.0
        mean_y = sum(values) / len(values)
        num = sum((idx - mean_x) * (val - mean_y) for idx, val in enumerate(values))
        den = sum((idx - mean_x) ** 2 for idx in range(len(values)))
        if den <= 0:
            return 0.0
        slope = num / den
        norm = abs(slope) / max(abs(mean_y), 1e-9) * len(values) * 12.0
        return max(0.0, min(1.0, norm))

    @staticmethod
    def _resolve_timestamp(rows: pd.DataFrame, now: datetime | None) -> datetime:
        if now is not None:
            return now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        if "timestamp" in rows.columns:
            raw = rows["timestamp"].iloc[-1]
            try:
                ts = pd.to_datetime(raw, utc=True)
                if pd.isna(ts):
                    raise ValueError(f"timestamp is NaT: {raw!r}")
                return ts.to_pydatetime()
            except Exception:
                logger.debug(
                    "RegimeDetector could not parse timestamp %r; using current UTC",
                    raw,
                )
        return datetime.now(timezone.utc)

    @staticmethod
    def _is_regular_session(now: datetime) -> bool:
        hour = now.astimezone(timezone.utc).hour
        minute = now.astimezone(timezone.utc).minute
        session_minutes = hour * 60 + minute
        return 13 * 60 + 30 <= session_minutes <= 20 * 60 + 15

    def _rollover_score(self, instrument: str, now: datetime) -> float:
        month, year = self._parse_contract_month(instrument)
        if month is None or year is None:
            return 0.0
        expiry = self._third_friday(year, month)
        days = abs((expiry.date() - now.date()).days)
        if days <= 3:
            return 1.0
        if days <= 7:
            return 0.85
        if days <= 10:
            return 0.65
        return 0.0

    def _parse_contract_month(self, instrument: str) -> tuple[int | None, int | None]:
        text = str(instrument).upper().replace("-", " ")
        parts = [part for part in text.split() if part]
        for part in parts:
            if len(part) >= 5 and part[:3] in _MONTH_NAMES and part[-2:].isdigit():
                month = _MONTH_NAMES[part[:3]]
                year = 2000 + int(part[-2:])
                return month, year
            if len(part) >= 3 and part[0] in _CONTRACT_MONTHS and part[-2:].isdigit():
                month = _CONTRACT_MONTHS[part[0]]
                year = 2000 + int(part[-2:])
                return month, year
        return None, None

    @staticmethod
    def _third_friday(year: int, month: int) -> datetime:
        dt = datetime(year, month, 15, tzinfo=timezone.utc)
        while dt.weekday() != 4:
            dt += timedelta(days=1)
        return dt

    @staticmethod
    def _float_map(raw: Any, defaults: dict[str, float]) -> dict[str, float]:
        payload = dict(defaults)
        if isinstance(raw, dict):
            for key, value in raw.items():
                try:
                    payload[str(key).upper()] = float(value)
                except (TypeError, ValueError):
                    continue
        return payload

    @staticmethod
    def _int_map(raw: Any, defaults: dict[str, int]) -> dict[str, int]:
        payload = dict(defaults)
        if isinstance(raw, dict):
            for key, value in raw.items():
                try:
                    payload[str(key).upper()] = int(value)
                except (TypeError, ValueError):
                    continue
        return payload

    @staticmethod
    def _route_map(raw: Any, defaults: dict[str, list[str]]) -> dict[str, list[str]]:
        payload = {str(key).upper(): list(value) for key, value in defaults.items()}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, (list, tuple)):
                    payload[str(key).upper()] = [str(item) for item in value if str(item).strip()]
        return payload


