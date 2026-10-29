"""Fail-closed execution decisions. Research never sends flatten/orders itself."""

from __future__ import annotations

from dataclasses import dataclass

from lumina_core.agent_orchestration.schemas_research import AlertAction, AlertKind


@dataclass(frozen=True, slots=True)
class FailClosedDecision:
    allow_new_orders: bool
    action: AlertAction
    kind: AlertKind
    flatten_recommended: bool
    reason: str


def decide_failure(
    *,
    stale_data: bool,
    lost_connection: bool,
    monitor_alarm: bool,
    open_position: bool,
    risk_core_limit: bool,
) -> FailClosedDecision:
    """Stale/lost → no new orders. Monitor alarm → de-weight. Hard close only on Risk Core."""
    if stale_data:
        if open_position:
            return FailClosedDecision(
                allow_new_orders=False,
                action="broker_protect",
                kind="stale_data",
                flatten_recommended=False,
                reason="stale data: no new orders; broker is source of truth; server-side stops",
            )
        return FailClosedDecision(
            allow_new_orders=False,
            action="refuse_new_orders",
            kind="stale_data",
            flatten_recommended=False,
            reason="stale data: no new orders",
        )
    if lost_connection:
        if open_position:
            return FailClosedDecision(
                allow_new_orders=False,
                action="broker_protect",
                kind="lost_connection",
                flatten_recommended=False,
                reason="lost connection: no new orders; reconcile on reconnect; broker is SoT",
            )
        return FailClosedDecision(
            allow_new_orders=False,
            action="refuse_new_orders",
            kind="lost_connection",
            flatten_recommended=False,
            reason="lost connection: no new orders",
        )
    if risk_core_limit:
        return FailClosedDecision(
            allow_new_orders=False,
            action="flatten_hard_limit",
            kind="risk_core_limit",
            flatten_recommended=True,
            reason="hard Risk Core limit: full close is a broker-side recommendation only",
        )
    if monitor_alarm and open_position:
        return FailClosedDecision(
            allow_new_orders=False,
            action="deweight_reduce",
            kind="monitor_alarm",
            flatten_recommended=False,
            reason="monitor alarm with open position: de-weight/reduce; no full close",
        )
    if monitor_alarm:
        return FailClosedDecision(
            allow_new_orders=False,
            action="refuse_new_orders",
            kind="monitor_alarm",
            flatten_recommended=False,
            reason="monitor alarm: no new orders",
        )
    return FailClosedDecision(
        allow_new_orders=True,
        action="refuse_new_orders",
        kind="monitor_alarm",
        flatten_recommended=False,
        reason="healthy link; Phase 5 still does not place orders",
    )
