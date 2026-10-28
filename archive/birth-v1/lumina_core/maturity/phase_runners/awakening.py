"""Awakening runner façade — living clock lives in maturity.awakening.runner."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _maturity_stop() -> bool:
    try:
        from lumina_core.maturity.maturity_service import MaturityService

        return MaturityService.instance()._stop_requested.is_set()
    except Exception:
        return False


def run_awakening(workspace_root: Path | str, **kwargs: Any) -> dict[str, Any]:
    from lumina_core.maturity.awakening.runner import run_awakening_live

    kwargs.setdefault("should_stop", _maturity_stop)
    return run_awakening_live(workspace_root, **kwargs)
