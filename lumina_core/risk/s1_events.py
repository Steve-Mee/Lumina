"""S1 ConstitutionViolation-equivalent structured reject events.

Risk Core does not publish ``safety.constitution.violation`` onto the Event
Bus. Fail-closed admission cannot depend on bus availability, and Risk vs
Agent Orchestration stay separate bounded contexts (constitution.md #4).

The payload is a ConstitutionViolation shape (``principle_name``,
``severity``, ``description``, ``detail``, ``mode``) plus ``agent_id``,
``account``, ``approved_by``, and ``timestamp``. Tests validate it with
``ConstitutionViolation.model_validate``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def s1_reject_event_data(
    *,
    event: str,
    reason: str,
    agent_id: str = "",
    mode: str = "",
    account: str = "",
    approved_by: str = "",
    extra: list[str] | None = None,
) -> dict[str, Any]:
    """Structured reject fields. Never used to allow an order."""
    payload: dict[str, Any] = {
        "event": str(event),
        "reason": str(reason),
        "principle_name": str(reason),
        "severity": "error",
        "description": str(event),
        "detail": str(reason),
        "mode": str(mode),
        "account": str(account),
        "agent_id": str(agent_id),
        "approved_by": str(approved_by),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra is not None:
        payload["extra"] = list(extra)
    return payload


__all__ = ["s1_reject_event_data"]
