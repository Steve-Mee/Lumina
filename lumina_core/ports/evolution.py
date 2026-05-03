from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EvolutionPort(Protocol):
    """Contract for evolution decision flows (proposal/evaluation/promotion)."""

    def run_nightly_cycle(self, *args: Any, **kwargs: Any) -> Any: ...
