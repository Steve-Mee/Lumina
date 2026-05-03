"""Reality gap tracker between paper/backtest baselines and live fills."""

from __future__ import annotations
import logging

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_LIVE_AUDIT_PATH = Path("logs/trade_fill_audit.jsonl")
DEFAULT_PAPER_METRICS_PATH = Path("state/validation/paper_fill_metrics.json")
DEFAULT_REALITY_GAP_LOG_PATH = Path("logs/reality_gap.jsonl")


@dataclass(slots=True)
class RealityGapThresholds:
    spread_tick_gap_max: float = 0.50
    slippage_tick_gap_max: float = 0.50
    fill_rate_gap_max: float = 0.10


@dataclass(slots=True)
class RealityGapResult:
    date: str
    live_metrics: dict[str, float]
    paper_metrics: dict[str, float] | None
    gaps: dict[str, float | None]
    threshold_breached: bool
    warnings: list[str]
    sample_count: int

    def to_record(self) -> dict[str, Any]:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "date": self.date,
            "sample_count": self.sample_count,
            "live_metrics": self.live_metrics,
            "paper_metrics": self.paper_metrics,
            "gaps": self.gaps,
            "threshold_breached": self.threshold_breached,
            "warnings": self.warnings,
        }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/monitoring/reality_gap_tracker.py:60")
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _extract_baseline_metrics(payload: dict[str, Any]) -> dict[str, float] | None:
    if not payload:
        return None
    if "metrics" in payload and isinstance(payload["metrics"], dict):
        payload = payload["metrics"]

    required_keys = ("spread_ticks_mean", "slippage_ticks_mean", "fill_rate")
    if all(key in payload for key in required_keys):
        return {
            "spread_ticks_mean": _safe_float(payload.get("spread_ticks_mean")),
            "slippage_ticks_mean": _safe_float(payload.get("slippage_ticks_mean")),
            "fill_rate": _safe_float(payload.get("fill_rate")),
        }
    return None


def _build_live_metrics(rows: list[dict[str, Any]]) -> tuple[dict[str, float], int, list[str]]:
    warnings: list[str] = []
    reconciled_rows = [row for row in rows if str(row.get("event", "")).lower() == "reconciled"]
    statuses = [str(row.get("status", "")).lower() for row in reconciled_rows]
    slippage_values = [abs(_safe_float(row.get("slippage_points"), 0.0)) for row in reconciled_rows]

    fill_count = sum(1 for status in statuses if status == "reconciled_fill")
    timeout_count = sum(1 for status in statuses if status == "timeout_snapshot")
    considered = fill_count + timeout_count
    fill_rate = (fill_count / considered) if considered > 0 else 1.0

    if any(status not in {"reconciled_fill", "timeout_snapshot"} for status in statuses):
        warnings.append("Some reconciliation statuses are unknown; fill rate is partial.")

    if not slippage_values:
        warnings.append("No reconciled slippage samples found in live audit.")

    slippage_mean = float(mean(slippage_values)) if slippage_values else 0.0
    spread_proxy_mean = slippage_mean
    warnings.append("Spread metric uses slippage proxy because explicit spread is not logged.")
    return (
        {
            "spread_ticks_mean": spread_proxy_mean,
            "slippage_ticks_mean": slippage_mean,
            "fill_rate": float(fill_rate),
        },
        len(reconciled_rows),
        warnings,
    )


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_daily_reality_gap(
    *,
    live_audit_path: Path = DEFAULT_LIVE_AUDIT_PATH,
    paper_metrics_path: Path = DEFAULT_PAPER_METRICS_PATH,
    output_log_path: Path = DEFAULT_REALITY_GAP_LOG_PATH,
    thresholds: RealityGapThresholds | None = None,
) -> RealityGapResult:
    limits = thresholds or RealityGapThresholds()
    rows = _read_jsonl(live_audit_path)
    live_metrics, sample_count, warnings = _build_live_metrics(rows)
    baseline_payload = _read_json(paper_metrics_path)
    paper_metrics = _extract_baseline_metrics(baseline_payload or {})

    gaps: dict[str, float | None] = {
        "spread_tick_gap": None,
        "slippage_tick_gap": None,
        "fill_rate_gap": None,
    }
    threshold_breached = False

    if paper_metrics is None:
        warnings.append("Paper/backtest baseline metrics unavailable; gap values are null.")
    else:
        gaps["spread_tick_gap"] = live_metrics["spread_ticks_mean"] - paper_metrics["spread_ticks_mean"]
        gaps["slippage_tick_gap"] = live_metrics["slippage_ticks_mean"] - paper_metrics["slippage_ticks_mean"]
        gaps["fill_rate_gap"] = live_metrics["fill_rate"] - paper_metrics["fill_rate"]
        threshold_breached = bool(
            abs(float(gaps["spread_tick_gap"])) > limits.spread_tick_gap_max
            or abs(float(gaps["slippage_tick_gap"])) > limits.slippage_tick_gap_max
            or abs(float(gaps["fill_rate_gap"])) > limits.fill_rate_gap_max
        )

    result = RealityGapResult(
        date=datetime.now(timezone.utc).date().isoformat(),
        live_metrics=live_metrics,
        paper_metrics=paper_metrics,
        gaps=gaps,
        threshold_breached=threshold_breached,
        warnings=warnings,
        sample_count=sample_count,
    )
    _append_jsonl(output_log_path, result.to_record())
    return result
