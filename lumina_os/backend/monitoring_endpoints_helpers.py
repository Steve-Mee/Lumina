"""Monitoring endpoint helpers (global residual)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

try:
    from backend.adaptive_intelligence_snapshot import (
        build_adaptive_transition_summary,
        load_adaptive_history_rows,
    )
except ImportError:  # pragma: no cover
    from lumina_os.backend.adaptive_intelligence_snapshot import (
        build_adaptive_transition_summary,
        load_adaptive_history_rows,
    )

_obs_service: Any = None
_ADAPTIVE_INTELLIGENCE_HISTORY = Path(
    os.getenv("ADAPTIVE_INTELLIGENCE_HISTORY_PATH", "state/adaptive_intelligence_events.jsonl")
)


def set_observability_service(service: Any) -> None:
    """Inject the ObservabilityService so all routes share the same instance."""
    global _obs_service
    _obs_service = service


def _require_service() -> Any:
    if _obs_service is None:
        raise HTTPException(
            status_code=503,
            detail="Observability service not yet initialised",
        )
    return _obs_service


def _load_adaptive_history_rows(*, limit: int = 100) -> list[dict[str, Any]]:
    return load_adaptive_history_rows(history_path=_ADAPTIVE_INTELLIGENCE_HISTORY, limit=limit)


def _build_adaptive_transition_summary(
    *,
    latest_record: dict[str, Any],
    previous_record: dict[str, Any] | None,
) -> dict[str, Any]:
    return build_adaptive_transition_summary(
        latest_record=latest_record,
        previous_record=previous_record,
    )


def _check_api_key(x_api_key: Optional[str]) -> None:
    """Lightweight API-key guard for monitoring endpoints."""
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="API key required")
