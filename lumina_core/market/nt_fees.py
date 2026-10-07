"""NinjaTrader all-in execution fees. One card for every phase.

Source: https://ninjatrader.com/pricing/commissions/
Card date: 2026-08-14. The page says the schedule is updated quarterly.
Point values: https://ninjatrader.com/futures/futures-contracts/micro-vs-mini-futures-comparison/
published 2026-09-29.

Per-side all-in = exchange+NFA + clearing + the plan commission.
NFA is already inside the exchange column. A second NFA line would double-count.
The fee is per contract per side. A round trip is two sides.
The fee does not depend on price. Slippage is not in this card. Fill prices
already contain the slippage that was received, so callers must not add a tick.

No paid plan is recorded for this desk. The unstated plan is Free, the
highest all-in on the card. ``config.yaml`` ``risk_controller.nt_account_plan``
may select ``free``, ``monthly``, or ``lifetime``. Any other value is refused.
A dollar amount in config cannot replace the card.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

CARD_AS_OF = "2026-08-14"
CARD_URL = "https://ninjatrader.com/pricing/commissions/"
POINT_VALUE_URL = "https://ninjatrader.com/futures/futures-contracts/micro-vs-mini-futures-comparison/"
PLANS = ("free", "monthly", "lifetime")
UNSTATED_PLAN = "free"

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


class CostCardError(ValueError):
    """The root, the quantity, or the plan is not on the published card."""


@dataclass(frozen=True, slots=True)
class ContractSpec:
    """One root on the NinjaTrader card. Dollars are per contract per side."""

    root: str
    exchange_nfa: float
    clearing: float
    commission_by_plan: dict[str, float]
    point_value_usd: float
    tick_size: float

    def commission(self, plan: str) -> float:
        key = _plan(plan)
        return float(self.commission_by_plan[key])

    def all_in_per_side(self, plan: str) -> float:
        return float(self.exchange_nfa + self.clearing + self.commission(plan))


def _spec(
    root: str,
    exchange_nfa: float,
    clearing: float,
    lifetime: float,
    monthly: float,
    free: float,
    point_value_usd: float,
    tick_size: float,
) -> ContractSpec:
    return ContractSpec(
        root=root,
        exchange_nfa=exchange_nfa,
        clearing=clearing,
        commission_by_plan={"lifetime": lifetime, "monthly": monthly, "free": free},
        point_value_usd=point_value_usd,
        tick_size=tick_size,
    )


# Itemized columns, in card order: exchange+NFA, clearing, lifetime, monthly, free.
# All-in is the sum. It is not stored a second time.
_CARD: dict[str, ContractSpec] = {
    spec.root: spec
    for spec in (
        _spec("MES", 0.36, 0.19, 0.09, 0.29, 0.39, 5.0, 0.25),
        _spec("MNQ", 0.36, 0.19, 0.09, 0.29, 0.39, 2.0, 0.25),
        _spec("MYM", 0.36, 0.19, 0.09, 0.29, 0.39, 0.50, 1.0),
        _spec("M2K", 0.36, 0.19, 0.09, 0.29, 0.39, 5.0, 0.10),
        _spec("ES", 1.39, 0.19, 0.59, 0.99, 1.29, 50.0, 0.25),
        _spec("NQ", 1.39, 0.19, 0.59, 0.99, 1.29, 20.0, 0.25),
        _spec("YM", 1.39, 0.19, 0.59, 0.99, 1.29, 5.0, 1.0),
        _spec("RTY", 1.39, 0.19, 0.59, 0.99, 1.29, 50.0, 0.10),
    )
}


def _plan(plan: str | None) -> str:
    if plan is None or str(plan).strip() == "":
        return active_plan()
    text = str(plan).strip().lower()
    if text not in PLANS:
        raise CostCardError(f"plan_not_on_card:{text}")
    return text


def contract_root(symbol: str) -> str:
    """First token of a listing, when that token is on the card. No MES fallback."""
    token = str(symbol or "").strip().upper().split()
    if not token:
        raise CostCardError("instrument_missing")
    root = token[0]
    if root not in _CARD:
        raise CostCardError(f"root_not_on_card:{root}")
    return root


def spec_for(symbol: str) -> ContractSpec:
    return _CARD[contract_root(symbol)]


def active_plan(config: Any | None = None) -> str:
    """Plan on file. Missing plan is Free. An unknown plan is refused."""
    raw = _plan_value(config) if config is not None else _plan_from_file()
    if raw is None or str(raw).strip() == "":
        return UNSTATED_PLAN
    return _plan(str(raw))


def fee_components(symbol: str, *, plan: str | None = None) -> tuple[float, float, float, float]:
    """Commission, exchange+NFA, clearing, and a zero NFA column. Per contract per side."""
    quote = spec_for(symbol)
    return (quote.commission(plan), float(quote.exchange_nfa), float(quote.clearing), 0.0)


def all_in_per_side_usd(symbol: str, *, plan: str | None = None, qty: int = 1) -> float:
    contracts = _contracts(qty)
    return float(spec_for(symbol).all_in_per_side(_plan(plan)) * contracts)


def round_turn_fee_usd(symbol: str, qty: int = 1, *, plan: str | None = None) -> float:
    """Entry plus exit. ``qty`` is contracts, not a price."""
    return float(all_in_per_side_usd(symbol, plan=plan, qty=qty) * 2.0)


def point_value_usd(symbol: str) -> float:
    return float(spec_for(symbol).point_value_usd)


def gross_close_usd(row: dict[str, Any]) -> float | None:
    """Dollar result before the fee.

    A real entry and a different exit win over a stored ``pnl``.
    A stored ``pnl`` is gross dollars. It is not already net of this card.
    """
    prices = _round_trip_prices(row)
    if prices is not None:
        entry, exit_px, side = prices
        if entry != exit_px:
            qty = _contracts(row.get("qty"))
            root_value = point_value_usd(str(row.get("instrument") or ""))
            return float((exit_px - entry) * float(side) * float(qty) * root_value)
    raw = row.get("pnl")
    if raw not in (None, ""):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    if prices is not None:
        return 0.0
    return None


def net_close_usd(row: dict[str, Any], *, plan: str | None = None) -> float | None:
    """Gross minus the round-trip card fee. None when the root or the qty is not on the card."""
    try:
        gross = gross_close_usd(row)
        if gross is None:
            return None
        return float(gross - round_turn_fee_usd(str(row.get("instrument") or ""), _contracts(row.get("qty")), plan=plan))
    except (CostCardError, TypeError, ValueError):
        return None


def _contracts(qty: Any) -> int:
    if qty in (None, ""):
        raise CostCardError("qty_missing")
    try:
        contracts = int(qty)
    except (TypeError, ValueError) as exc:
        raise CostCardError("qty_invalid") from exc
    if contracts <= 0:
        raise CostCardError("qty_invalid")
    return contracts


def _round_trip_prices(row: dict[str, Any]) -> tuple[float, float, int] | None:
    try:
        entry = float(row.get("entry_px"))
        exit_raw = row.get("exit_px")
        if exit_raw in (None, ""):
            exit_raw = row.get("fill_px")
        exit_px = float(exit_raw)
        side = int(row.get("side") or 0)
    except (TypeError, ValueError):
        return None
    if entry <= 0.0 or exit_px <= 0.0 or side == 0:
        return None
    return entry, exit_px, side


def _plan_value(config: Any) -> Any:
    if isinstance(config, dict):
        section = config.get("risk_controller", {})
    else:
        section = getattr(config, "risk_controller", {})
    if isinstance(section, dict):
        return section.get("nt_account_plan")
    return getattr(section, "nt_account_plan", None)


def _plan_from_file() -> Any:
    if not _CONFIG_PATH.is_file():
        return None
    try:
        import yaml
    except ImportError:
        return None
    try:
        loaded = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(loaded, dict):
        return None
    section = loaded.get("risk_controller")
    if not isinstance(section, dict):
        return None
    return section.get("nt_account_plan")
