"""Golden ledger: broker-confirmed fills → costs → realized PnL (single formula)."""

from __future__ import annotations

from dataclasses import dataclass

from lumina_core.engine.valuation_engine import ValuationEngine


@dataclass(frozen=True, slots=True)
class CloseLegLedgerResult:
    """Economic outcome of closing a position leg using broker-confirmed exit fill."""

    gross_pnl: float
    exit_commission: float
    realized_net: float
    slippage_points_vs_reference: float


def realized_close_from_broker_fill(
    *,
    valuation_engine: ValuationEngine,
    symbol: str,
    entry_price: float,
    exit_fill_price: float,
    position_signal: str,
    quantity: int,
    exit_commission: float,
    reference_price_for_slippage_ticks: float | None = None,
) -> CloseLegLedgerResult:
    """Compute realized PnL from entry and **exit fill** prices plus exit commission.

    ``position_signal`` is the opening direction: ``BUY`` (long) or ``SELL`` (short).
    ``reference_price_for_slippage_ticks`` is optional (e.g. chart snapshot) for observability only;
    slippage_points are vs exit fill when reference is omitted.
    """
    sig = str(position_signal).upper().strip()
    signed_side = 1 if sig == "BUY" else -1
    qty = max(0, int(quantity))
    gross = valuation_engine.pnl_dollars(
        symbol=str(symbol),
        entry_price=float(entry_price),
        exit_price=float(exit_fill_price),
        side=signed_side,
        quantity=qty,
    )
    ec = float(exit_commission)
    realized = float(gross) - ec
    tick = max(valuation_engine.tick_size(str(symbol)), 1e-9)
    ref = float(exit_fill_price) if reference_price_for_slippage_ticks is None else float(reference_price_for_slippage_ticks)
    slip_pts = (float(exit_fill_price) - ref) / tick
    return CloseLegLedgerResult(
        gross_pnl=float(gross),
        exit_commission=ec,
        realized_net=float(realized),
        slippage_points_vs_reference=float(slip_pts),
    )


def round_turn_realized_from_two_fills(
    *,
    valuation_engine: ValuationEngine,
    symbol: str,
    entry_fill_price: float,
    exit_fill_price: float,
    open_side: str,
    quantity: int,
    entry_commission: float,
    exit_commission: float,
) -> float:
    """Full round-turn net PnL from open and close fill prices and both commissions."""
    leg = realized_close_from_broker_fill(
        valuation_engine=valuation_engine,
        symbol=symbol,
        entry_price=entry_fill_price,
        exit_fill_price=exit_fill_price,
        position_signal=open_side,
        quantity=quantity,
        exit_commission=float(exit_commission),
        reference_price_for_slippage_ticks=None,
    )
    return float(leg.gross_pnl) - float(entry_commission) - float(leg.exit_commission)
