"""Progress event emission for smart setup."""

from __future__ import annotations

from typing import Any

from lumina_launcher.services.setup_schemas import (
    PROGRESS_PERCENT,
    SetupProgressCallback,
    SetupProgressEvent,
)


def emit_progress(
    callback: SetupProgressCallback | None,
    *,
    phase: str,
    message: str,
    level: str = "info",
    detail: dict[str, Any] | None = None,
) -> None:
    if callback is None:
        return
    event = SetupProgressEvent(
        phase=phase,
        message=message,
        percent=PROGRESS_PERCENT.get(phase),
        level=level,  # type: ignore[arg-type]
        detail=detail or {},
    )
    callback(event)
