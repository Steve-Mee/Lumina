"""Abstract broker bridge protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Order, OrderResult, Position

class BrokerBridge(ABC):
    @abstractmethod
    def connect(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def submit_order(self, order: Order) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[Position]:
        raise NotImplementedError

    @abstractmethod
    def get_fills(self) -> list[Fill]:
        raise NotImplementedError

    @abstractmethod
    def cancel_all_orders(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def subscribe_to_websocket(self) -> None:
        raise NotImplementedError

