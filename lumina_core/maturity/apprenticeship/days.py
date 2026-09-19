"""Session-day ledger derived from the apprenticeship tape. Never invents dates or Sharpe."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, stdev
from typing import Any

from lumina_core.birth.foundation_metrics import S5_DD_EQUITY_USD
from lumina_core.birth.notional_cap import clip_birth_exam_pnl
from lumina_core.maturity.apprenticeship.tape import load_tape_rows

DAYS_REL = Path("state") / "lumina_apprenticeship_days.jsonl"
N_D_MIN = 5
SHARPE_DAYS_MIN = 5


@dataclass(frozen=True, slots=True)
class DaySummary:
    session_date: date
    n_closes: int
    pnl: float
    expectancy: float | None
    green: bool
    constitution_hit: bool


def days_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / DAYS_REL


def row_session_date(row: dict[str, Any]) -> date | None:
    explicit = str(row.get("session_date") or "").strip()
    if len(explicit) >= 10:
        try:
            return date.fromisoformat(explicit[:10])
        except ValueError:
            pass
    ts = str(row.get("ts") or "").strip()
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        from zoneinfo import ZoneInfo

        local = parsed.astimezone(ZoneInfo("America/Chicago"))
    except Exception:
        local = parsed.astimezone(timezone.utc)
    if local.hour >= 17:
        return (local + timedelta(days=1)).date()
    return local.date()


def _clip_pnl(row: dict[str, Any]) -> float | None:
    raw = row.get("pnl")
    if raw is None or raw == "":
        return None
    try:
        pnl = float(raw)
    except (TypeError, ValueError):
        return None
    px = row.get("fill_px") or row.get("entry_px")
    try:
        entry = float(px) if px not in (None, "") else 0.0
    except (TypeError, ValueError):
        entry = 0.0
    qty = int(row.get("qty") or 1)
    if entry > 0.0:
        return clip_birth_exam_pnl(pnl, entry_price=entry, qty=max(1, qty), equity=S5_DD_EQUITY_USD)
    return pnl


def _is_policy_close(row: dict[str, Any]) -> bool:
    return str(row.get("kind") or "") == "close" and bool(row.get("policy"))


def build_day_summaries(workspace_root: Path | str) -> list[DaySummary]:
    by_day: dict[date, dict[str, Any]] = {}
    for row in load_tape_rows(workspace_root):
        if not _is_policy_close(row):
            continue
        day = row_session_date(row)
        if day is None:
            continue
        slot = by_day.setdefault(
            day,
            {"n": 0, "pnl": 0.0, "has_pnl": False, "constitution": False},
        )
        slot["n"] += 1
        pnl = _clip_pnl(row)
        if pnl is not None:
            slot["pnl"] += pnl
            slot["has_pnl"] = True
        if row.get("risk_event") or row.get("var_breach") or row.get("daily_kill"):
            slot["constitution"] = True
    out: list[DaySummary] = []
    for day in sorted(by_day):
        slot = by_day[day]
        n = int(slot["n"])
        pnl = float(slot["pnl"]) if slot["has_pnl"] else 0.0
        expectancy = (pnl / float(n)) if n > 0 and slot["has_pnl"] else None
        constitution = bool(slot["constitution"])
        green = bool(
            n >= 1
            and expectancy is not None
            and float(expectancy) > 0.0
            and not constitution
        )
        out.append(
            DaySummary(
                session_date=day,
                n_closes=n,
                pnl=pnl,
                expectancy=expectancy,
                green=green,
                constitution_hit=constitution,
            )
        )
    return out


def previous_weekday(day: date) -> date:
    cursor = day - timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def consecutive_green_streak(days: list[DaySummary]) -> int:
    if not days:
        return 0
    by = {d.session_date: d for d in days}
    cursor = max(by)
    streak = 0
    while True:
        slot = by.get(cursor)
        if slot is None or not slot.green:
            break
        streak += 1
        cursor = previous_weekday(cursor)
    return streak


def daily_returns(days: list[DaySummary]) -> list[float]:
    equity = float(S5_DD_EQUITY_USD)
    return [float(d.pnl) / equity for d in days]


def annualized_sharpe(days: list[DaySummary]) -> float | None:
    if len(days) < SHARPE_DAYS_MIN:
        return None
    rets = daily_returns(days)
    if len(rets) < 2:
        return None
    sd = float(stdev(rets))
    if sd <= 1e-12:
        return None
    return float(mean(rets) / sd) * math.sqrt(252.0)


def max_dd_pct(workspace_root: Path | str) -> float | None:
    pnls: list[float] = []
    for row in load_tape_rows(workspace_root):
        if not _is_policy_close(row):
            continue
        pnl = _clip_pnl(row)
        if pnl is None:
            continue
        pnls.append(pnl)
    if not pnls:
        return None
    equity = float(S5_DD_EQUITY_USD)
    peak = equity
    eq = equity
    worst = 0.0
    for pnl in pnls:
        eq += pnl
        if eq > peak:
            peak = eq
        dd = (peak - eq) / equity * 100.0
        if dd > worst:
            worst = dd
    return worst


def persist_day_ledger(workspace_root: Path | str, days: list[DaySummary]) -> None:
    from lumina_core.io.atomic_fs import atomic_write_text

    path = days_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "session_date": d.session_date.isoformat(),
                "n_closes": d.n_closes,
                "pnl": d.pnl,
                "expectancy": d.expectancy,
                "green": d.green,
                "constitution_hit": d.constitution_hit,
                "source": "apprenticeship_tape",
            },
            ensure_ascii=True,
        )
        for d in days
    ]
    atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def tape_day_metrics(workspace_root: Path | str) -> dict[str, Any]:
    days = build_day_summaries(workspace_root)
    persist_day_ledger(workspace_root, days)
    streak = consecutive_green_streak(days)
    return {
        "n_d": streak,
        "session_days": len(days),
        "sharpe": annualized_sharpe(days),
        "dd_pct": max_dd_pct(workspace_root),
        "days": [
            {
                "session_date": d.session_date.isoformat(),
                "n_closes": d.n_closes,
                "pnl": d.pnl,
                "expectancy": d.expectancy,
                "green": d.green,
            }
            for d in days
        ],
    }
