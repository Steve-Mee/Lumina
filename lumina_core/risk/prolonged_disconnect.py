"""PROPOSAL — ADR-0064 items 7–8 Accepted (research team 23:09 sha cc904288).

Research team, not Steve. Live stays closed. Cap values unchanged.

Flatten-grace is a hard 5s (no open-ended). Prolonged-disconnect flatten is
pre-registered at 30000 ms (approved band 30–60s; lower bound, fail-closed).
Risk Core *apply* of the disconnect flatten still needs signed human review;
this module is the testable proposal, not a silent live-path change.

Research team decision (relayed by Steve 2026-10-29).
"""

from __future__ import annotations

from typing import Any, Mapping

SOURCE_LABEL = "research team decision (relayed by Steve 2026-10-29)"
FOLLOWUP_SOURCE = "research team 2026-10-29 23:09 sha cc904288 (not Steve)"

FLATTEN_GRACE_HARD_MS = 5000
PROLONGED_DISCONNECT_MS = 30_000
PROLONGED_DISCONNECT_MIN_MS = 30_000
PROLONGED_DISCONNECT_MAX_MS = 60_000


def pin_flatten_grace_ms(raw: object) -> int:
    """Hard explicit 5s. Caller values (0, 15s, 30–60s) are ignored."""
    del raw
    return int(FLATTEN_GRACE_HARD_MS)


def registered_prolonged_disconnect_ms(raw: object | None = None) -> int:
    """Pre-registered 30s. Config may only document that value; drift pins back."""
    del raw
    return int(PROLONGED_DISCONNECT_MS)


def is_prolonged_disconnect(
    disconnected_ms: object,
    *,
    registered_ms: int = PROLONGED_DISCONNECT_MS,
) -> bool:
    try:
        elapsed = int(disconnected_ms)
    except (TypeError, ValueError):
        return True
    if elapsed < 0:
        return True
    return elapsed >= int(registered_ms)


def should_flatten_unprotected(
    *,
    disconnected_ms: object,
    has_confirmed_server_stop: bool | None,
    registered_ms: int = PROLONGED_DISCONNECT_MS,
) -> bool:
    """Flatten when disconnect is prolonged and no confirmed server-side stop.

    Unknown stop status fail-closes to flatten. Confirmed ATM/C skip flatten.
    """
    if is_prolonged_disconnect(disconnected_ms, registered_ms=registered_ms) is not True:
        return False
    if has_confirmed_server_stop is True:
        return False
    return True


def from_mapping(raw: Mapping[str, Any] | None) -> tuple[int, int]:
    blob: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    fabric = blob.get("fabric") if isinstance(blob.get("fabric"), Mapping) else blob
    if not isinstance(fabric, Mapping):
        fabric = {}
    return (
        pin_flatten_grace_ms(fabric.get("flatten_grace_ms")),
        registered_prolonged_disconnect_ms(fabric.get("prolonged_disconnect_ms")),
    )
