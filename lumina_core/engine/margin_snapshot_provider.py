from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MarginSnapshot:
    margins: dict[str, float]
    as_of: datetime
    source: str
    confidence: float
    stale_after_hours: int

    @property
    def age_hours(self) -> float:
        return max(0.0, (_utcnow() - self.as_of).total_seconds() / 3600.0)

    @property
    def stale(self) -> bool:
        return self.age_hours > float(max(1, self.stale_after_hours))


class MarginSnapshotProvider:
    """Provides margin requirements and metadata for stale-data governance."""

    DEFAULT_MARGINS: dict[str, float] = {
        "MES": 8400.0,
        "MNQ": 10500.0,
        "MYM": 7000.0,
        "RTY": 5500.0,
        "ZB": 3300.0,
        "ZN": 2600.0,
        "YM": 21000.0,
        "ES": 20000.0,
        "NQ": 32000.0,
    }

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> MarginSnapshot:
        cfg = config if isinstance(config, dict) else {}
        raw_map = cfg.get("margin_requirements", {})
        margins: dict[str, float] = {}
        if isinstance(raw_map, dict):
            for symbol, value in raw_map.items():
                try:
                    margins[str(symbol).strip().upper()] = float(value)
                except (TypeError, ValueError):
                    continue
        if not margins:
            margins = dict(cls.DEFAULT_MARGINS)

        as_of_raw = cfg.get("margin_as_of", "")
        as_of = _utcnow()
        if isinstance(as_of_raw, str) and as_of_raw.strip():
            text = as_of_raw.strip().replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(text)
                as_of = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                as_of = _utcnow()

        source = str(cfg.get("margin_source", "config_snapshot") or "config_snapshot")
        confidence_raw = cfg.get("margin_confidence", 0.8)
        stale_after_raw = cfg.get("margin_stale_after_hours", 168)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.8
        try:
            stale_after = int(stale_after_raw)
        except (TypeError, ValueError):
            stale_after = 168

        return MarginSnapshot(
            margins=margins,
            as_of=as_of,
            source=source,
            confidence=max(0.0, min(1.0, confidence)),
            stale_after_hours=max(1, stale_after),
        )
