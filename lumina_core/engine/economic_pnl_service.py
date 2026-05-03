"""Central broker-confirmed economic PnL; rejects RL / training metrics."""

from __future__ import annotations

from typing import Any, Mapping

from lumina_core.engine.golden_ledger import (
    CloseLegLedgerResult,
    realized_close_from_broker_fill,
    round_turn_realized_from_two_fills,
)
from lumina_core.engine.valuation_engine import ValuationEngine

_FORBIDDEN_ECONOMIC_KEYS = frozenset({"training_reward"})


def reject_if_training_metrics(payload: Mapping[str, Any]) -> None:
    """Raise if a payload meant for economic ingestion contains RL-only keys."""
    for key in _FORBIDDEN_ECONOMIC_KEYS:
        if key in payload:
            msg = f"Economic PnL path rejects key {key!r} (training-layer only)"
            raise ValueError(msg)


class EconomicPnLService:
    """Broker-fill → costs → realized PnL; delegates to golden ledger formulas."""

    __slots__ = ("_valuation_engine",)

    def __init__(self, valuation_engine: ValuationEngine | None = None) -> None:
        self._valuation_engine = valuation_engine or ValuationEngine()

    @property
    def valuation_engine(self) -> ValuationEngine:
        return self._valuation_engine

    def round_turn_realized_usd_from_broker_fills(
        self,
        *,
        symbol: str,
        entry_fill_price: float,
        exit_fill_price: float,
        open_side: str,
        quantity: int,
        entry_commission: float,
        exit_commission: float,
    ) -> float:
        return round_turn_realized_from_two_fills(
            valuation_engine=self._valuation_engine,
            symbol=str(symbol),
            entry_fill_price=float(entry_fill_price),
            exit_fill_price=float(exit_fill_price),
            open_side=str(open_side),
            quantity=int(quantity),
            entry_commission=float(entry_commission),
            exit_commission=float(exit_commission),
        )

    def realized_close_from_broker_fill(
        self,
        *,
        symbol: str,
        entry_price: float,
        exit_fill_price: float,
        position_signal: str,
        quantity: int,
        exit_commission: float,
        reference_price_for_slippage_ticks: float | None = None,
    ) -> CloseLegLedgerResult:
        return realized_close_from_broker_fill(
            valuation_engine=self._valuation_engine,
            symbol=str(symbol),
            entry_price=float(entry_price),
            exit_fill_price=float(exit_fill_price),
            position_signal=str(position_signal),
            quantity=int(quantity),
            exit_commission=float(exit_commission),
            reference_price_for_slippage_ticks=reference_price_for_slippage_ticks,
        )

    def economic_pnl_from_reconciled_payload(self, payload: Mapping[str, Any]) -> float:
        """Parse a minimal broker-close dict; rejects ``training_reward``."""
        reject_if_training_metrics(payload)
        return float(payload["economic_pnl_usd"])
