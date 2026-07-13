"""Connection state for the NinjaTrader bridge session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ConnectionStateLiteral = Literal[
    "disconnected",
    "authenticating",
    "connected",
    "reconnecting",
    "degraded",
    "error",
]


@dataclass(slots=True)
class NinjaTraderConnectionState:
    state: ConnectionStateLiteral = "disconnected"
    account_name: str = ""
    connection_name: str = ""
    ninjatrader_version: str = ""
    last_bar_ts: str | None = None
    session_id: str | None = None
    client_name: str = ""
    client_version: str = ""

    @property
    def is_connected(self) -> bool:
        return self.state == "connected"

    @property
    def allows_new_orders(self) -> bool:
        return self.state == "connected"

    def to_telemetry_dict(self) -> dict[str, object]:
        return {
            "connected": self.is_connected,
            "account": self.account_name,
            "last_bar_ts": self.last_bar_ts,
            "state": self.state,
        }
