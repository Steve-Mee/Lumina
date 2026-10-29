"""Daily calibration pipeline for TradeExecutionCostModel.

Compares model-estimated exit-leg execution cost against reconciled real fills
and persists rolling bias statistics for downstream cost model correction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from lumina_core.market.nt_fees import CostCardError, contract_root
from lumina_core.risk.cost_model import TradeExecutionCostModel, _instrument_tick_params


DEFAULT_CALIBRATION_AUDIT_LOG = Path("logs/trade_fill_audit.jsonl")
DEFAULT_CALIBRATION_STATE_FILE = Path("state/cost_model_calibration.json")
DEFAULT_ATR_FALLBACK = 8.0
DEFAULT_TIME_PERIOD = "midday"


@dataclass(slots=True)
class DailyCalibrationSummary:
    day: str
    sample_count: int
    real_fill_cost_usd_avg: float
    model_cost_usd_avg: float
    mean_bias_usd: float
    stdev_bias_usd: float
    mean_bias_ticks: float
    stdev_bias_ticks: float


@dataclass(slots=True)
class CalibrationResult:
    instrument: str
    sample_count: int
    mean_bias_usd: float
    stdev_bias_usd: float
    mean_bias_ticks: float
    stdev_bias_ticks: float
    recommended_slippage_sigma: float
    atr_fallback: float
    audit_path: str
    state_path: str
    daily: list[DailyCalibrationSummary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "instrument": self.instrument,
            "source_audit_log": self.audit_path,
            "atr_fallback": self.atr_fallback,
            "rolling": {
                "sample_count": self.sample_count,
                "mean_bias_usd": self.mean_bias_usd,
                "stdev_bias_usd": self.stdev_bias_usd,
                "mean_bias_ticks": self.mean_bias_ticks,
                "stdev_bias_ticks": self.stdev_bias_ticks,
                "recommended_slippage_sigma": self.recommended_slippage_sigma,
            },
            "daily": [
                {
                    "day": item.day,
                    "sample_count": item.sample_count,
                    "real_fill_cost_usd_avg": item.real_fill_cost_usd_avg,
                    "model_cost_usd_avg": item.model_cost_usd_avg,
                    "mean_bias_usd": item.mean_bias_usd,
                    "stdev_bias_usd": item.stdev_bias_usd,
                    "mean_bias_ticks": item.mean_bias_ticks,
                    "stdev_bias_ticks": item.stdev_bias_ticks,
                }
                for item in self.daily
            ],
        }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_symbol(value: str | None, fallback: str) -> str:
    raw = str(value or fallback).strip().upper()
    return raw.split()[0] if raw else fallback.split()[0]


def _parse_day(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return None


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(pstdev(values))


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


def _is_live_broker_source(value: object) -> bool:
    """Broker JSONL only. Hypothetical and unknown sources never enter live calibration.

    Kept local so this module does not import ``research_bridge`` (Event Bus cycle).
    """
    text = str(value or "").strip().lower()
    if text == "hypothetical_adr0055":
        return False
    return text in {"", "broker"}


def load_reconciled_rows(audit_path: Path, *, since_day: date | None = None) -> list[dict[str, Any]]:
    rows = _read_jsonl(audit_path)
    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("event", "")).lower() != "reconciled":
            continue
        if not _is_live_broker_source(row.get("source", "")):
            continue
        if since_day is not None:
            day = _parse_day(row.get("ts"))
            if day is None:
                continue
            if day < since_day.isoformat():
                continue
        out.append(row)
    return out


def row_instrument_root(row: dict[str, Any], *, fallback: str = "MES") -> str | None:
    raw = str(row.get("root") or row.get("symbol") or row.get("instrument") or fallback)
    try:
        return contract_root(raw)
    except CostCardError:
        return None


def compute_exit_leg_costs(
    row: dict[str, Any],
    model: TradeExecutionCostModel,
    *,
    atr: float = DEFAULT_ATR_FALLBACK,
    time_period: str = DEFAULT_TIME_PERIOD,
) -> tuple[float, float, float]:
    symbol = _normalize_symbol(str(row.get("symbol", model.instrument)), model.instrument)
    _, tick_value = _instrument_tick_params(symbol)
    quantity = max(1, _safe_int(row.get("qty", row.get("quantity")), 1))
    commission = max(0.0, _safe_float(row.get("commission"), 0.0))
    entry_price = _safe_float(row.get("fill_price", row.get("entry_price")), 0.0)
    if "slippage_usd" in row:
        slip_usd = abs(_safe_float(row.get("slippage_usd"), 0.0))
    elif "slippage_ticks" in row:
        slip_usd = abs(_safe_float(row.get("slippage_ticks"), 0.0)) * tick_value * quantity
    else:
        slippage_points = abs(_safe_float(row.get("slippage_points"), 0.0))
        slip_usd = slippage_points * tick_value * quantity
    real_fill_cost_usd = commission + slip_usd
    model_cost = model.cost_for_trade(
        price=entry_price,
        quantity=float(quantity),
        atr=float(max(0.0, atr)),
        avg_volume=max(1000.0, float(quantity)),
        time_period=time_period,
    )
    model_exit_leg_usd = model_cost.total_round_trip_usd * 0.5
    return float(real_fill_cost_usd), float(model_exit_leg_usd), float(tick_value)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def load_calibration_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def apply_calibration_from_state(
    model: TradeExecutionCostModel,
    *,
    state_path: Path = DEFAULT_CALIBRATION_STATE_FILE,
    sigma_fallback: float = 0.0,
) -> tuple[float, float]:
    payload = load_calibration_state(state_path)
    rolling = payload.get("rolling", {}) if isinstance(payload, dict) else {}
    if not isinstance(rolling, dict):
        rolling = {}
    bias_ticks = _safe_float(rolling.get("mean_bias_ticks"), 0.0)
    recommended_sigma = _safe_float(
        rolling.get("recommended_slippage_sigma"),
        _safe_float(rolling.get("stdev_bias_ticks"), sigma_fallback),
    )
    sigma = max(0.0, float(recommended_sigma))
    model.apply_calibration(bias_slippage_ticks=bias_ticks, slippage_sigma=sigma)
    return float(bias_ticks), sigma


def run_daily_calibration(
    *,
    audit_path: Path = DEFAULT_CALIBRATION_AUDIT_LOG,
    state_path: Path = DEFAULT_CALIBRATION_STATE_FILE,
    instrument: str = "MES",
    atr_fallback: float = DEFAULT_ATR_FALLBACK,
    time_period: str = DEFAULT_TIME_PERIOD,
    since_day: date | None = None,
    sigma_multiplier: float = 1.0,
    sigma_floor: float = 0.0,
) -> CalibrationResult:
    try:
        want_root = contract_root(instrument)
    except CostCardError:
        want_root = _normalize_symbol(instrument, "MES")
    model = TradeExecutionCostModel.from_config({}, instrument=want_root)
    rows = load_reconciled_rows(audit_path, since_day=since_day)

    grouped: dict[str, list[tuple[float, float, float]]] = {}
    biases_usd: list[float] = []
    biases_ticks: list[float] = []
    by_root_costs: dict[str, list[float]] = {}
    root_models: dict[str, TradeExecutionCostModel] = {want_root: model}

    for row in rows:
        day = _parse_day(row.get("ts"))
        if day is None:
            continue
        root = row_instrument_root(row, fallback=want_root)
        if root is None:
            continue
        if root not in root_models:
            root_models[root] = TradeExecutionCostModel.from_config({}, instrument=root)
        real_usd, model_usd, tick_value = compute_exit_leg_costs(
            row,
            root_models[root],
            atr=float(atr_fallback),
            time_period=time_period,
        )
        by_root_costs.setdefault(root, []).append(real_usd)
        if root != want_root:
            continue
        deviation_usd = real_usd - model_usd
        quantity = max(1, _safe_int(row.get("qty", row.get("quantity")), 1))
        tick_denom = max(1e-9, tick_value * quantity)
        deviation_ticks = deviation_usd / tick_denom
        biases_usd.append(deviation_usd)
        biases_ticks.append(deviation_ticks)
        grouped.setdefault(day, []).append((real_usd, model_usd, deviation_ticks))

    daily: list[DailyCalibrationSummary] = []
    for day in sorted(grouped.keys()):
        values = grouped[day]
        real_values = [item[0] for item in values]
        model_values = [item[1] for item in values]
        day_biases_usd = [real_values[idx] - model_values[idx] for idx in range(len(values))]
        day_tick_values = [item[2] for item in values]
        daily.append(
            DailyCalibrationSummary(
                day=day,
                sample_count=len(values),
                real_fill_cost_usd_avg=float(mean(real_values)),
                model_cost_usd_avg=float(mean(model_values)),
                mean_bias_usd=float(mean(day_biases_usd)),
                stdev_bias_usd=_std(day_biases_usd),
                mean_bias_ticks=float(mean(day_tick_values)) if day_tick_values else 0.0,
                stdev_bias_ticks=_std(day_tick_values),
            )
        )

    result = CalibrationResult(
        instrument=instrument,
        sample_count=len(biases_usd),
        mean_bias_usd=float(mean(biases_usd)) if biases_usd else 0.0,
        stdev_bias_usd=_std(biases_usd),
        mean_bias_ticks=float(mean(biases_ticks)) if biases_ticks else 0.0,
        stdev_bias_ticks=_std(biases_ticks),
        recommended_slippage_sigma=max(
            0.0,
            max(float(sigma_floor), _std(biases_ticks) * max(0.0, float(sigma_multiplier))),
        ),
        atr_fallback=float(atr_fallback),
        audit_path=str(audit_path),
        state_path=str(state_path),
        daily=daily,
    )
    payload = result.to_dict()
    payload["by_root"] = {
        root: {
            "sample_count": len(values),
            "real_fill_cost_usd_avg": float(mean(values)),
        }
        for root, values in by_root_costs.items()
    }
    _atomic_write_json(state_path, payload)
    return result
