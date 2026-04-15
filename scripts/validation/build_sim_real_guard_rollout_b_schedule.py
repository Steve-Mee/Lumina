from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

WINDOW_SPECS: tuple[tuple[str, time, str], ...] = (
    ("09:30-10:00", time(hour=9, minute=30), "30m"),
    ("12:00-12:30", time(hour=12, minute=0), "30m"),
    ("15:20-15:55", time(hour=15, minute=20), "35m"),
)


@dataclass(frozen=True, slots=True)
class RolloutWindow:
    trading_day_index: int
    trading_date: str
    window_label: str
    start_local: str
    duration: str
    task_name_suffix: str


def _parse_start_date(raw: str | None) -> date:
    if raw:
        return date.fromisoformat(raw)
    return datetime.now().date()


def _next_business_days(start: date, count: int) -> list[date]:
    result: list[date] = []
    cursor = start
    while len(result) < count:
        if cursor.weekday() < 5:
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def build_schedule(*, start_date: str | None = None, trading_days: int = 5) -> list[RolloutWindow]:
    base = _parse_start_date(start_date)
    days = _next_business_days(base, trading_days)
    windows: list[RolloutWindow] = []
    for day_index, trading_day in enumerate(days, start=1):
        for label, start_at, duration in WINDOW_SPECS:
            dt = datetime.combine(trading_day, start_at)
            windows.append(
                RolloutWindow(
                    trading_day_index=day_index,
                    trading_date=trading_day.isoformat(),
                    window_label=f"D{day_index}_{label.replace(':', '-')}".replace(" ", "_"),
                    start_local=dt.isoformat(timespec="minutes"),
                    duration=duration,
                    task_name_suffix=f"D{day_index}_{start_at.strftime('%H%M')}",
                )
            )
    return windows


def _to_payload(windows: list[RolloutWindow]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window_count": len(windows),
        "windows": [asdict(item) for item in windows],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 15-window Rollout B schedule plan.")
    parser.add_argument("--start-date", default=None, help="ISO date, e.g. 2026-04-16")
    parser.add_argument("--trading-days", type=int, default=5)
    parser.add_argument("--output", default="state/validation/sim_real_guard_rollout_b/schedule_plan.json")
    args = parser.parse_args()

    windows = build_schedule(start_date=args.start_date, trading_days=args.trading_days)
    payload = _to_payload(windows)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output_path), "window_count": len(windows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
