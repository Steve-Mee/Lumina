"""Shared birth config coercion helpers."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("lumina.birth.config")

def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_wall_behavior(raw: Any) -> str:
    value = str(raw or "adaptive").strip().lower()
    if value in ("adaptive", "strict"):
        return value
    logger.warning("birth_v2.invalid_wall_behavior value=%s fallback=strict", raw)
    return "strict"


def _parse_expansion_steps(raw: Any) -> tuple[int, ...]:
    if isinstance(raw, list):
        out: list[int] = []
        for item in raw:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        if out:
            return tuple(out)
    return (90, 180, 365, 730)


