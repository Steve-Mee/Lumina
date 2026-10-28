"""Hexagonal port for KEEP consumption of research PromotionCandidates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    # Runtime import of FillEvent loads trade_reconciler.__init__ → LuminaEngine
    # and closes a circular import through ports/__init__.py. Annotations are
    # deferred (from __future__ import annotations).
    from lumina_core.agent_orchestration.schemas_research import PromotionCandidate
    from lumina_core.agent_orchestration.schemas_research_execution import SignalIntent
    from lumina_core.engine.trade_reconciler.schemas import FillEvent


@runtime_checkable
class ResearchExecutionPort(Protocol):
    """S0: log SignalIntent + hypothetical FillEvent. Never PlaceOrderCommand."""

    def on_candidate(self, candidate: PromotionCandidate) -> SignalIntent | None: ...

    def shadow_fill(self, intent: SignalIntent) -> FillEvent | None: ...

    def assert_no_broker_submit(self) -> None: ...
