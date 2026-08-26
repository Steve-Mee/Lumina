"""Make-before-break challenger health — heartbeat, overlay, schema, violations."""

from __future__ import annotations

from typing import Any


def evaluate_challenger_health(
    *,
    heartbeat_alive: bool,
    overlay_loaded: bool,
    schema_match: bool,
    open_crit_violations: int,
    fabric_ok: bool = True,
) -> dict[str, Any]:
    if not heartbeat_alive:
        return {"green": False, "reason": "heartbeat"}
    if not overlay_loaded:
        return {"green": False, "reason": "overlay"}
    if not schema_match:
        return {"green": False, "reason": "schema"}
    if int(open_crit_violations) > 0:
        return {"green": False, "reason": "violations"}
    if not fabric_ok:
        return {"green": False, "reason": "fabric"}
    return {"green": True, "reason": "ok"}
