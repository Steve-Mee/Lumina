"""Resolve monkeypatchable twin symbols via approval_twin_agent façade."""
from __future__ import annotations

from typing import Any, Callable


def twin_attr(name: str, fallback: Callable[..., Any]) -> Callable[..., Any]:
    from lumina_core.evolution import approval_twin_agent as mod

    return getattr(mod, name, fallback)
