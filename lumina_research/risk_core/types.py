"""Research Risk Core types. Frozen. Agents may only propose."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import assert_never


class DecisionKind(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    SCALED = "scaled"


@dataclass(frozen=True, slots=True)
class OrderProposal:
    agent_id: str
    instrument: str
    side: str
    quantity: float
    price: float
    notional: float
    cluster_id: str
    submitted_at_utc: datetime

    def __post_init__(self) -> None:
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if not self.instrument:
            raise ValueError("instrument is required")
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if self.quantity <= 0.0:
            raise ValueError("quantity must be positive")
        if self.price <= 0.0 or self.notional <= 0.0:
            raise ValueError("price and notional must be positive")
        if not self.cluster_id:
            raise ValueError("cluster_id is required")

    def __init_subclass__(cls) -> None:
        raise TypeError("OrderProposal cannot be subclassed")


@dataclass(frozen=True, slots=True)
class Decision:
    kind: DecisionKind
    reason: str
    quantity: float
    notional: float
    agent_id: str

    def __init_subclass__(cls) -> None:
        raise TypeError("Decision cannot be subclassed")

    @staticmethod
    def approved(proposal: OrderProposal) -> Decision:
        return Decision(
            kind=DecisionKind.APPROVED,
            reason="approved",
            quantity=proposal.quantity,
            notional=proposal.notional,
            agent_id=proposal.agent_id,
        )

    @staticmethod
    def rejected(proposal: OrderProposal, reason: str) -> Decision:
        return Decision(
            kind=DecisionKind.REJECTED,
            reason=reason,
            quantity=0.0,
            notional=0.0,
            agent_id=proposal.agent_id,
        )

    @staticmethod
    def scaled(proposal: OrderProposal, *, quantity: float, notional: float, reason: str) -> Decision:
        return Decision(
            kind=DecisionKind.SCALED,
            reason=reason,
            quantity=quantity,
            notional=notional,
            agent_id=proposal.agent_id,
        )


def decision_label(kind: DecisionKind) -> str:
    if kind is DecisionKind.APPROVED:
        return "approved"
    if kind is DecisionKind.REJECTED:
        return "rejected"
    if kind is DecisionKind.SCALED:
        return "scaled"
    assert_never(kind)
