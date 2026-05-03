from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DreamStatePort(Protocol):
    """Contract for dream-state read/write operations."""

    def get_current_dream_snapshot(self) -> dict[str, Any]: ...

    def set_current_dream_fields(self, updates: dict[str, Any]) -> None: ...
