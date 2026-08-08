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
    # Execution Fabric extensions (PR-E)
    safe_mode: str = "UNKNOWN"
    fabric_target: str = ""
    gateway: str = ""
    last_state_hash: str = ""
    recent_alerts: int = 0
    metrics: dict[str, object] | None = None

    @property
    def is_connected(self) -> bool:
        return self.state == "connected"

    @property
    def is_fabric_safe_mode(self) -> bool:
        """True when Fabric reports SAFE / FULL_SAFE (no new places)."""
        sm = str(self.safe_mode or "UNKNOWN").strip().upper()
        return sm in {"SAFE", "FULL_SAFE", "SAFE_MODE"}

    @property
    def allows_new_orders(self) -> bool:
        # Connected AND not in Fabric SAFE_MODE (cancel/flatten still separate).
        return self.state == "connected" and not self.is_fabric_safe_mode

    def to_telemetry_dict(self) -> dict[str, object]:
        return {
            "connected": self.is_connected,
            "account": self.account_name,
            "last_bar_ts": self.last_bar_ts,
            "state": self.state,
            "safe_mode": self.safe_mode,
            "fabric_safe_mode": self.is_fabric_safe_mode,
            "fabric_target": self.fabric_target,
            "gateway": self.gateway,
            "session_id": self.session_id or "",
            "last_state_hash": self.last_state_hash,
            "recent_alerts": int(self.recent_alerts),
            "metrics": dict(self.metrics) if self.metrics else {},
        }
