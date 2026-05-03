from __future__ import annotations

from typing import Protocol, runtime_checkable

from lumina_core.broker.broker_bridge import AccountInfo, Fill, Order, OrderResult, Position


@runtime_checkable
class BrokerPort(Protocol):
    """Contract for broker execution and account state access."""

    def connect(self) -> bool: ...

    def disconnect(self) -> None: ...

    # Optional broker capabilities used in execution pathways.
    def submit_order(self, order: Order) -> OrderResult: ...

    def get_account_info(self) -> AccountInfo: ...

    def get_positions(self) -> list[Position]: ...

    def get_fills(self) -> list[Fill]: ...
