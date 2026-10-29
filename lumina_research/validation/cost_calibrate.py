"""Research CostModel calibrates *to* ADR-0055. Never undercuts the card. Never writes live state.

KEEP FillEvent / live ``state/cost_model_calibration.json`` stay execution-side.
This file writes ``state/research_cost_calibration.json`` only. Coefficients
may tighten; they never cheapen. Research still does not import the NT broker.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from lumina_core.market.nt_fees import CostCardError, all_in_per_side_usd, contract_root
from lumina_research.validation.contracts import spec_for as research_spec_for
from lumina_research.validation.cost_model import CostModel, MarketSnapshot

LIVE_CALIBRATION_FILENAME: str = "cost_model_calibration.json"
RESEARCH_CALIBRATION_FILENAME: str = "research_cost_calibration.json"
EPS: float = 1e-12


class CostCalibrateRefused(ValueError):
    """Research calibration refused. Doubt = reject. Card is never undercut."""


@dataclass(frozen=True, slots=True)
class RootCalibration:
    root: str
    sample_count: int
    execution_commission_usd: float
    research_commission_usd: float
    execution_slippage_usd: float
    research_total_usd: float
    execution_total_usd: float
    discrepancy: bool
    slippage_coefficient: float
    impact_coefficient: float


def card_commission_usd(root: str, qty: int = 1) -> float:
    if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise CostCalibrateRefused("qty_invalid")
    try:
        return float(all_in_per_side_usd(root, plan="free", qty=qty))
    except CostCardError as exc:
        raise CostCalibrateRefused(f"root_not_on_card:{root}") from exc


def research_commission_usd(root: str, qty: int = 1) -> float:
    if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise CostCalibrateRefused("qty_invalid")
    spec = research_spec_for(root)
    return float(spec.commission_usd_per_side) * float(qty)


def assert_does_not_undercut_card(root: str, research_commission: float, qty: int = 1) -> None:
    card = card_commission_usd(root, qty)
    if not math.isfinite(float(research_commission)):
        raise CostCalibrateRefused("research_commission_non_finite")
    if float(research_commission) + EPS < card:
        raise CostCalibrateRefused("research_commission_undercuts_card")


def execution_wins(research_total_usd: float, execution_total_usd: float) -> tuple[float, bool]:
    if not math.isfinite(float(research_total_usd)) or not math.isfinite(float(execution_total_usd)):
        raise CostCalibrateRefused("total_non_finite")
    discrepancy = abs(float(research_total_usd) - float(execution_total_usd)) > EPS
    return float(execution_total_usd), discrepancy


def tighten_only(old: float, new: float) -> float:
    if not math.isfinite(float(old)) or float(old) < 0.0:
        raise CostCalibrateRefused("coefficient_invalid")
    if not math.isfinite(float(new)) or float(new) < 0.0:
        raise CostCalibrateRefused("coefficient_invalid")
    if float(new) < float(old):
        return float(old)
    return float(new)


def research_four_leg_usd(root: str, qty: int, model: CostModel | None = None) -> float:
    spec = research_spec_for(root)
    engine = model if model is not None else CostModel()
    market = MarketSnapshot(volume=1_000.0, average_volume=1_000.0, volatility_price=spec.tick_size * 4.0)
    return float(engine.ticks_for_fill(spec=spec, quantity=float(qty), market=market).total_usd)


def calibrate_root(
    *,
    root: str,
    execution_commission_usd: float,
    execution_slippage_usd: float,
    qty: int = 1,
    model: CostModel | None = None,
    sample_count: int = 1,
) -> RootCalibration:
    token = _root(root)
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 1:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise CostCalibrateRefused("sample_count_invalid")
    card = card_commission_usd(token, qty)
    if abs(float(execution_commission_usd) - card) > EPS:
        execution_commission_usd = card
    assert_does_not_undercut_card(token, research_commission_usd(token, qty), qty)
    engine = model if model is not None else CostModel()
    research_total = research_four_leg_usd(token, qty, engine)
    execution_total = float(execution_commission_usd) + float(execution_slippage_usd)
    ssot, discrepancy = execution_wins(research_total, execution_total)
    slip = float(engine.slippage_coefficient)
    impact = float(engine.impact_coefficient)
    if research_total + EPS < execution_total and research_total > 0.0:
        scale = execution_total / research_total
        slip = tighten_only(slip, slip * scale)
        impact = tighten_only(impact, impact * scale)
    return RootCalibration(
        root=token,
        sample_count=int(sample_count),
        execution_commission_usd=float(card),
        research_commission_usd=research_commission_usd(token, qty),
        execution_slippage_usd=float(execution_slippage_usd),
        research_total_usd=float(research_total),
        execution_total_usd=float(ssot),
        discrepancy=bool(discrepancy),
        slippage_coefficient=float(slip),
        impact_coefficient=float(impact),
    )


def write_research_calibration(path: Path, payload: Mapping[str, Any]) -> None:
    name = path.name
    if name == LIVE_CALIBRATION_FILENAME:
        raise CostCalibrateRefused("research_calibration_cannot_write_live_state")
    if name != RESEARCH_CALIBRATION_FILENAME and not str(name).endswith(RESEARCH_CALIBRATION_FILENAME):
        if "cost_model_calibration" in name:
            raise CostCalibrateRefused("research_calibration_cannot_write_live_state")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(payload), indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def calibrate_fills(
    fills: Sequence[Mapping[str, Any]],
    *,
    output: Path,
    model: CostModel | None = None,
) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in fills:
        source = str(row.get("source") or "").strip().lower()
        if source == "hypothetical_adr0055":
            continue
        try:
            root = _root(str(row.get("root") or row.get("symbol") or row.get("instrument") or ""))
        except CostCalibrateRefused:
            continue
        grouped.setdefault(root, []).append(row)
    by_root: dict[str, dict[str, Any]] = {}
    engine = model if model is not None else CostModel()
    for root, rows in grouped.items():
        qty = max(1, _safe_int(rows[0].get("qty", rows[0].get("quantity")), 1))
        exec_comm = card_commission_usd(root, qty)
        slip_values = [_safe_float(item.get("slippage_usd"), 0.0) for item in rows]
        mean_slip = sum(slip_values) / float(len(slip_values))
        result = calibrate_root(
            root=root,
            execution_commission_usd=exec_comm,
            execution_slippage_usd=mean_slip,
            qty=qty,
            model=engine,
            sample_count=len(rows),
        )
        by_root[root] = {
            "sample_count": result.sample_count,
            "execution_commission_usd": result.execution_commission_usd,
            "research_commission_usd": result.research_commission_usd,
            "execution_slippage_usd": result.execution_slippage_usd,
            "research_total_usd": result.research_total_usd,
            "execution_total_usd": result.execution_total_usd,
            "discrepancy": result.discrepancy,
            "slippage_coefficient": result.slippage_coefficient,
            "impact_coefficient": result.impact_coefficient,
        }
    payload: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "winner": "execution_side",
        "by_root": by_root,
    }
    write_research_calibration(output, payload)
    return payload


def _root(symbol: str) -> str:
    try:
        token = contract_root(symbol)
    except CostCardError as exc:
        raise CostCalibrateRefused(f"root_not_on_card:{symbol}") from exc
    return str(token)


def _safe_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return default
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _safe_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return default
    else:
        return default
    if not math.isfinite(number):
        return default
    return number
