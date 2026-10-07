"""Field helpers for the Dutch Eerste-stappen brief. Measurement only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.maturity.playground.sense_candles import EXCHANGE_TZ, parse_utc


def bar_book_operator_alert(root: Path) -> str:
    payload = read_json(root / "state" / "lumina_bar_integrity.json")
    if payload.get("lock_new_entries") is not True:
        return ""
    missing = payload.get("missing_count")
    try:
        missing_n = int(missing or 0)
    except (TypeError, ValueError):
        missing_n = 0
    extra = f" {missing_n} ontbrekende NT 1m-bars." if missing_n > 0 else ""
    reason = str(payload.get("reason") or "").strip()
    reason_bit = f" ({reason})" if reason else ""
    return f"Barboek onvolledig: nieuwe entries staan dicht.{extra}{reason_bit}"


def gap_line(closes: list[dict[str, Any]]) -> str:
    worst = 0
    left: datetime | None = None
    right: datetime | None = None
    previous: datetime | None = None
    for row in closes:
        current = parse_utc(str(row.get("ts") or ""))
        if current is None:
            continue
        if previous is not None:
            delta = int((current - previous).total_seconds())
            if delta > worst:
                worst = delta
                left = previous
                right = current
        previous = current
    if worst < 120 or left is None or right is None:
        return ""
    minutes = max(1, round(worst / 60))
    return (
        f"Gat van {minutes} minuten tussen {hhmm(left)} en {hhmm(right)} Chicago. "
        "In dat gat kwam geen minuut binnen. Daarna keek zij weer."
    )


def frozen_minutes(closes: list[dict[str, Any]]) -> int:
    prices: list[float] = []
    for row in reversed(closes):
        try:
            px = float(row.get("px") or 0.0)
        except (TypeError, ValueError):
            break
        if px <= 0.0:
            break
        if prices and abs(px - prices[-1]) > 1e-9:
            break
        prices.append(px)
    return len(prices)


def last_moment(closes: list[dict[str, Any]], progress: dict[str, Any]) -> datetime | None:
    if closes:
        parsed = parse_utc(str(closes[-1].get("ts") or ""))
        if parsed is not None:
            return parsed
    at = progress.get("last_px_at")
    try:
        if at is not None and at != "":
            return datetime.fromtimestamp(float(at), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    return None


def listing(progress: dict[str, Any]) -> str:
    text = str(progress.get("chart_listing") or "").strip()
    if text:
        return text
    charts = progress.get("open_charts")
    if isinstance(charts, list):
        for item in charts:
            name = str(item or "").strip()
            if name:
                return name
    return ""


def price(
    closes: list[dict[str, Any]],
    progress: dict[str, Any],
    crawl: dict[str, Any],
) -> float | None:
    sources: list[tuple[dict[str, Any], tuple[str, ...]]] = []
    if closes:
        sources.append((closes[-1], ("px",)))
    sources.append((progress, ("last_px",)))
    sources.append((crawl, ("live_px",)))
    for source, keys in sources:
        for key in keys:
            raw = source.get(key)
            try:
                px = float(raw) if raw is not None and raw != "" else 0.0
            except (TypeError, ValueError):
                continue
            if px > 0.0:
                return px
    return None


def n_p(progress: dict[str, Any]) -> int:
    try:
        return max(0, int(progress.get("n_p") or 0))
    except (TypeError, ValueError):
        return 0


def occupancy(progress: dict[str, Any], path: Path) -> float | None:
    raw = progress.get("occupancy")
    try:
        if raw is not None and raw != "":
            return float(raw)
    except (TypeError, ValueError):
        pass
    payload = read_json(path)
    try:
        if int(payload.get("total_bars") or 0) <= 0:
            return None
        return float(payload["occupancy"])
    except (TypeError, ValueError, KeyError):
        return None


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def chicago(moment: datetime) -> str:
    return f"Chicago {moment.astimezone(EXCHANGE_TZ).strftime('%H:%M')}"


def hhmm(moment: datetime) -> str:
    return moment.astimezone(EXCHANGE_TZ).strftime("%H:%M")


def age_words(age: int) -> str:
    if age < 90:
        return f"Laatste minuut {age}s geleden"
    minutes = max(1, age // 60)
    return f"Laatste minuut {minutes} min geleden"


def action(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
