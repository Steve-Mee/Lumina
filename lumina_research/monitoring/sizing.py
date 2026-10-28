"""Size paper/shadow orders through research Risk Core. Monitoring may only reduce."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from lumina_research.evolution.regime import RegimeAction
from lumina_research.monitoring.registry import LiveSignalRegistry
from lumina_research.monitoring.types import ContinuityRefused, LiveSignal
from lumina_research.risk_core.engine import RiskCore
from lumina_research.risk_core.types import Decision, DecisionKind, OrderProposal, cluster_for

MONITOR_SIZER_ID = "live_monitor_agent"


class ContinuitySizer:
    """Applies weight × capacity × regime (all ≤ 1) then ``RiskCore.propose_order``."""

    def __init_subclass__(cls) -> None:
        raise TypeError("ContinuitySizer cannot be subclassed")

    def __init__(self, *, core: RiskCore, registry: LiveSignalRegistry) -> None:
        self._core = core
        self._registry = registry

    def increase_quantity(self, signal_id: str, quantity: float) -> None:
        del signal_id, quantity
        raise ContinuityRefused("monitoring cannot increase exposure")

    def propose(
        self,
        signal_id: str,
        *,
        quantity: float,
        price: float,
        at: datetime | None = None,
        regime: RegimeAction | None = None,
    ) -> Decision:
        signal = self._registry.require(signal_id)
        if not self._registry.verify(signal):
            raise ContinuityRefused("signal_tampered")
        if signal.weight <= 0.0 or signal.stage in {"suspended", "retired"}:
            return _blocked(signal)
        if not _finite_positive(quantity) or not _finite_positive(price):
            raise ContinuityRefused("quantity and price must be finite and positive")
        multiplier = float(signal.weight) * float(signal.capacity_scale)
        if regime is not None:
            if regime.size_multiplier <= 0.0 or regime.size_multiplier > 1.0:
                raise ContinuityRefused("regime multiplier must be in (0, 1]")
            multiplier *= float(regime.size_multiplier)
        if multiplier > 1.0 + 1e-12:
            raise ContinuityRefused("monitoring cannot increase exposure")
        qty = float(quantity) * multiplier
        notional = qty * float(price)
        if qty <= 0.0 or notional <= 0.0:
            return _blocked(signal)
        now = at if at is not None else datetime.now(timezone.utc)
        self._core.heartbeat(now)
        proposal = OrderProposal(
            agent_id=MONITOR_SIZER_ID,
            instrument=signal.instrument,
            side="buy",
            quantity=qty,
            price=float(price),
            notional=notional,
            cluster_id=cluster_for(signal.instrument),
            submitted_at_utc=now,
        )
        decision = self._core.propose_order(proposal)
        if decision.kind is DecisionKind.APPROVED and decision.quantity > qty + 1e-9:
            raise ContinuityRefused("Risk Core increased a monitoring reduction")
        if decision.kind is DecisionKind.SCALED and decision.quantity > qty + 1e-9:
            raise ContinuityRefused("Risk Core increased a monitoring reduction")
        return decision


def _blocked(signal: LiveSignal) -> Decision:
    now = datetime.now(timezone.utc)
    dummy = OrderProposal(
        agent_id=MONITOR_SIZER_ID,
        instrument=signal.instrument,
        side="buy",
        quantity=1.0,
        price=max(signal.base_price, 1e-9),
        notional=max(signal.base_price, 1e-9),
        cluster_id=cluster_for(signal.instrument),
        submitted_at_utc=now,
    )
    return Decision.rejected(dummy, "monitoring_zero_weight")


def _finite_positive(value: float) -> bool:
    number = float(value)
    return math.isfinite(number) and number > 0.0
