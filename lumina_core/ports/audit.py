from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuditPort(Protocol):
    """Contract for append-only audit decision logging."""

    def log_decision(self, payload: dict[str, Any], *, is_real_mode: bool = False) -> bool: ...
