"""Fill SSOT for decay monitoring and cost calibration. Fabric is typed, not wired."""

from __future__ import annotations

from typing import assert_never

from lumina_core.agent_orchestration.schemas_research import ResearchFillEvent
from lumina_research.agents.frozen import Frozen


class PortRefused(ValueError):
    """Research port refused an order, fabric fill, or NT8 coupling attempt."""


class FillSink(Frozen):
    """One source of truth for fills. Phase 5 accepts cost_model hypotheticals only."""

    _fills: list[ResearchFillEvent]

    def __init_subclass__(cls) -> None:
        raise TypeError("FillSink cannot be subclassed")

    def __init__(self) -> None:
        self._fills = []
        self._freeze()

    def ingest(self, fill: ResearchFillEvent) -> ResearchFillEvent:
        if fill.source == "fabric":
            raise PortRefused("NT8 coupling is not implemented in this PR")
        if fill.source == "cost_model":
            self._fills.append(fill)
            return fill
        assert_never(fill.source)

    def fills(self) -> tuple[ResearchFillEvent, ...]:
        return tuple(self._fills)

    def connect_fabric(self) -> None:
        raise PortRefused("NT8 coupling is not implemented in this PR")
