"""Resolve monkeypatchable symbols via certificate_pipeline façade."""
from __future__ import annotations

from typing import Any, Callable


def cp_attr(name: str, fallback: Callable[..., Any]) -> Callable[..., Any]:
    """Prefer ``certificate_pipeline.<name>`` so tests can monkeypatch the façade."""
    from lumina_core.birth import certificate_pipeline as cp

    return getattr(cp, name, fallback)
