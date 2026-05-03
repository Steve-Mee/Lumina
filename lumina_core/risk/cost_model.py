"""TradeExecutionCostModel — complete execution cost breakdown for Lumina.

Canonical location: ``lumina_core.risk.cost_model``

Covers all costs incurred when opening and closing a futures position:

Fee components (per side unless noted)
---------------------------------------
- Slippage    : ATR-based half-spread + Almgren-Chriss market impact
- Commission  : Broker commission (round-trip by default)
- Exchange fee: CME Group fee
- Clearing fee: NFA clearing charge
- NFA fee     : Regulatory fee per contract

Round-trip total = 2 × (slippage + commission + exchange + clearing + nfa)

Usage
-----
    model = TradeExecutionCostModel.from_config(cfg)
    cost  = model.cost_for_trade(
        price=5020.0, quantity=1.0, atr=8.0,
        avg_volume=5000.0, time_period="midday",
    )
    print(cost.total_round_trip_usd)   # e.g. "$6.28"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CostBreakdown:
    """Detailed round-trip cost for a single trade.

    All values are in USD.  Per-side means one leg (entry OR exit).
    """

    # --- Slippage ---
    half_spread_ticks: float  # ATR-based half bid-ask spread (ticks)
    market_impact_ticks: float  # Almgren-Chriss market impact (ticks)
    total_slippage_ticks: float  # half_spread + market_impact
    slippage_usd_per_side: float  # ticks × tick_value
    slippage_usd_round_trip: float  # 2 × per-side

    # --- Fees (per side) ---
    commission_usd_per_side: float
    exchange_fee_usd_per_side: float
    clearing_fee_usd_per_side: float
    nfa_fee_usd_per_side: float
    total_fees_usd_per_side: float

    # --- Totals ---
    total_per_side_usd: float  # slippage + fees (one leg)
    total_round_trip_usd: float  # full round-trip cost

    # --- Meta ---
    quantity: float
    price: float
    atr: float
    time_period: str
    instrument: str

    @property
    def breakeven_move_ticks(self) -> float:
        """Minimum price move (ticks) needed to cover round-trip costs."""
        if self.quantity <= 0:
            return 0.0
        total_fees_one_side = self.total_fees_usd_per_side
        slippage_one_side = self.slippage_usd_per_side
        total_per_side = total_fees_one_side + slippage_one_side
        # Convert USD → ticks  (tick_value = slippage_usd_per_side / slippage_ticks if >0)
        if self.total_slippage_ticks > 0 and self.slippage_usd_per_side > 0:
            tick_value = self.slippage_usd_per_side / self.total_slippage_ticks
        else:
            tick_value = 1.0
        return (total_per_side * 2) / (tick_value * self.quantity) if tick_value > 0 else 0.0


# ---------------------------------------------------------------------------
# Main model
# ---------------------------------------------------------------------------


@dataclass
class TradeExecutionCostModel:
    """Complete cost model for futures execution.

    Parameters
    ----------
    tick_size:
        Minimum price increment (e.g. 0.25 for MES/ES).
    tick_value:
        USD value per tick per contract (e.g. $1.25 for MES).
    commission_per_side_usd:
        Broker commission per contract per side.
    exchange_fee_per_side_usd:
        CME Group fee per contract per side.
    clearing_fee_per_side_usd:
        NFA clearing fee per contract per side.
    nfa_fee_per_side_usd:
        Regulatory NFA fee per contract per side.
    slippage_base_ticks:
        Base half-spread in ticks (minimum slippage floor).
    slippage_atr_ratio:
        Fraction of ATR used as half-spread (e.g. 0.10 = 10 % of ATR).
    slippage_sigma:
        Std-dev multiplier for random slippage noise (0 = deterministic).
    spread_multipliers:
        Dict mapping time period → spread multiplier.
        Keys: "open", "midday", "close".
    market_impact_alpha:
        Almgren-Chriss linear impact coefficient.
    market_impact_beta:
        Almgren-Chriss power-law exponent (0.5–0.7 typical).
    instrument:
        Label for logging (e.g. "MES").
    """

    tick_size: float = 0.25
    tick_value: float = 1.25  # MES: $1.25/tick
    commission_per_side_usd: float = 1.29
    exchange_fee_per_side_usd: float = 0.35
    clearing_fee_per_side_usd: float = 0.10
    nfa_fee_per_side_usd: float = 0.02
    slippage_base_ticks: float = 0.5  # floor: half a tick
    slippage_atr_ratio: float = 0.10  # 10 % of ATR as half-spread
    slippage_sigma: float = 0.0  # deterministic by default
    spread_multipliers: dict[str, float] = field(default_factory=lambda: {"open": 2.5, "midday": 1.0, "close": 2.0})
    market_impact_alpha: float = 0.5
    market_impact_beta: float = 0.6
    instrument: str = "MES"
    calibration_bias_ticks: float = 0.0

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: Any, instrument: str = "MES") -> "TradeExecutionCostModel":
        """Build from a lumina config object or dict.

        Reads ``risk_controller`` section for fee/slippage params.
        Falls back to dataclass defaults for any missing key.
        """

        def _get(section: Any, key: str, default: Any) -> Any:
            if isinstance(section, dict):
                return section.get(key, default)
            return getattr(section, key, default)

        rc: Any
        if isinstance(config, dict):
            rc = config.get("risk_controller", {})
        else:
            rc = getattr(config, "risk_controller", {})

        # Instrument tick params (ValuationEngine values for MES/ES/NQ/YM)
        _tick_size, _tick_value = _instrument_tick_params(instrument)

        spread_mults = _get(
            rc,
            "order_book_spread_multipliers",
            {"open": 2.5, "midday": 1.0, "close": 2.0},
        )
        if not isinstance(spread_mults, dict):
            spread_mults = {"open": 2.5, "midday": 1.0, "close": 2.0}

        return cls(
            tick_size=_tick_size,
            tick_value=_tick_value,
            commission_per_side_usd=float(_get(rc, "commission_per_side_usd", 1.29)),
            exchange_fee_per_side_usd=float(_get(rc, "exchange_fee_per_side_usd", 0.35)),
            clearing_fee_per_side_usd=float(_get(rc, "clearing_fee_per_side_usd", 0.10)),
            nfa_fee_per_side_usd=float(_get(rc, "nfa_fee_per_side_usd", 0.02)),
            slippage_base_ticks=float(_get(rc, "slippage_base_points", 0.5)),
            slippage_atr_ratio=float(_get(rc, "order_book_spread_atr_ratio", 0.10)),
            slippage_sigma=float(_get(rc, "slippage_sigma", 0.0)),
            spread_multipliers=dict(spread_mults),
            market_impact_alpha=float(_get(rc, "market_impact_alpha", 0.5)),
            market_impact_beta=float(_get(rc, "market_impact_beta", 0.6)),
            instrument=instrument,
        )

    # ------------------------------------------------------------------
    # Slippage components
    # ------------------------------------------------------------------

    def _spread_ticks(self, atr: float, time_period: str = "midday") -> float:
        """ATR-based half-spread with time-of-day multiplier."""
        multiplier = self.spread_multipliers.get(str(time_period).lower(), 1.0)
        atr_ticks = atr / self.tick_size if self.tick_size > 0 else 0.0
        atr_based = atr_ticks * self.slippage_atr_ratio * multiplier
        return float(max(self.slippage_base_ticks, atr_based))

    def _market_impact_ticks(self, quantity: float, avg_volume: float) -> float:
        """Almgren-Chriss simplified market impact.

        impact = alpha × (quantity / avg_volume)^beta
        """
        if avg_volume <= 0.0 or quantity <= 0.0:
            return 0.0
        ratio = quantity / avg_volume
        return float(self.market_impact_alpha * (ratio**self.market_impact_beta))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def slippage_ticks(
        self,
        atr: float,
        quantity: float = 1.0,
        avg_volume: float = 1000.0,
        time_period: str = "midday",
    ) -> float:
        """Total slippage in ticks (spread + market impact)."""
        spread = self._spread_ticks(atr, time_period)
        impact = self._market_impact_ticks(quantity, avg_volume)
        return max(0.0, spread + impact + self.calibration_bias_ticks)

    def apply_calibration(
        self,
        *,
        bias_slippage_ticks: float = 0.0,
        slippage_sigma: float | None = None,
    ) -> None:
        """Apply calibration output to the live cost model.

        Parameters
        ----------
        bias_slippage_ticks:
            Mean slippage deviation in ticks added to model slippage.
        slippage_sigma:
            Optional dynamic sigma override derived from recent deviation std-dev.
        """
        self.calibration_bias_ticks = float(bias_slippage_ticks)
        if slippage_sigma is not None:
            self.slippage_sigma = max(0.0, float(slippage_sigma))

    def fees_usd_per_side(self) -> float:
        """Total explicit fees (USD) per contract per side."""
        return (
            self.commission_per_side_usd
            + self.exchange_fee_per_side_usd
            + self.clearing_fee_per_side_usd
            + self.nfa_fee_per_side_usd
        )

    def cost_for_trade(
        self,
        price: float,
        quantity: float = 1.0,
        atr: float = 0.0,
        avg_volume: float = 1000.0,
        time_period: str = "midday",
    ) -> CostBreakdown:
        """Compute the full execution cost for a round-trip trade.

        Parameters
        ----------
        price:
            Entry price (used for context/logging only).
        quantity:
            Number of contracts.
        atr:
            Current ATR value (same units as price).
        avg_volume:
            Average volume for market impact calculation.
        time_period:
            "open" | "midday" | "close" — affects spread multiplier.
        """
        quantity = max(1.0, float(quantity))

        # --- Slippage ---
        spread_ticks = self._spread_ticks(atr, time_period)
        impact_ticks = self._market_impact_ticks(quantity, avg_volume)
        total_slip_ticks = max(0.0, spread_ticks + impact_ticks + self.calibration_bias_ticks)
        slip_usd_per_side = total_slip_ticks * self.tick_value * quantity
        slip_usd_rt = slip_usd_per_side * 2.0

        # --- Fees ---
        comm = self.commission_per_side_usd * quantity
        exch = self.exchange_fee_per_side_usd * quantity
        clea = self.clearing_fee_per_side_usd * quantity
        nfa = self.nfa_fee_per_side_usd * quantity
        total_fees_per_side = comm + exch + clea + nfa

        # --- Totals ---
        total_per_side = slip_usd_per_side + total_fees_per_side
        total_rt = total_per_side * 2.0

        return CostBreakdown(
            half_spread_ticks=spread_ticks,
            market_impact_ticks=impact_ticks,
            total_slippage_ticks=total_slip_ticks,
            slippage_usd_per_side=slip_usd_per_side,
            slippage_usd_round_trip=slip_usd_rt,
            commission_usd_per_side=comm,
            exchange_fee_usd_per_side=exch,
            clearing_fee_usd_per_side=clea,
            nfa_fee_usd_per_side=nfa,
            total_fees_usd_per_side=total_fees_per_side,
            total_per_side_usd=total_per_side,
            total_round_trip_usd=total_rt,
            quantity=quantity,
            price=price,
            atr=atr,
            time_period=time_period,
            instrument=self.instrument,
        )

    def net_pnl(self, gross_pnl_usd: float, quantity: float = 1.0, atr: float = 0.0) -> float:
        """Deduct round-trip costs from a gross PnL figure."""
        cost = self.cost_for_trade(price=0.0, quantity=quantity, atr=atr)
        return gross_pnl_usd - cost.total_round_trip_usd


# ---------------------------------------------------------------------------
# Instrument registry
# ---------------------------------------------------------------------------

_INSTRUMENT_TICK_PARAMS: dict[str, tuple[float, float]] = {
    # (tick_size, tick_value_usd)
    "MES": (0.25, 1.25),
    "ES": (0.25, 12.50),
    "MNQ": (0.25, 0.50),
    "NQ": (0.25, 5.00),
    "MYM": (1.00, 0.50),
    "YM": (1.00, 5.00),
    "M2K": (0.10, 0.50),
    "RTY": (0.10, 5.00),
    "MCL": (0.01, 1.00),
    "CL": (0.01, 10.00),
    "MGC": (0.10, 1.00),
    "GC": (0.10, 10.00),
}


def _instrument_tick_params(instrument: str) -> tuple[float, float]:
    """Return (tick_size, tick_value_usd) for a given instrument symbol.

    Strips expiry suffixes (e.g. "MES JUN26" → "MES").
    Falls back to MES defaults.
    """
    sym = str(instrument).strip().upper().split()[0]
    return _INSTRUMENT_TICK_PARAMS.get(sym, (0.25, 1.25))
