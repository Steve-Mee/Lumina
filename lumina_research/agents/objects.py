"""Narrow untyped mappings (JSON / HMAC payloads) to ``dict[str, object]``."""

from __future__ import annotations

from typing import Mapping, cast


def as_object_dict(value: object) -> dict[str, object] | None:
    """Narrow a JSON object to ``dict[str, object]``. Lists and scalars return None."""
    if not isinstance(value, dict):
        return None
    typed = cast(dict[object, object], value)
    return {str(key): item for key, item in typed.items()}


def as_object_list(value: object) -> list[object] | None:
    """Narrow a JSON array to ``list[object]``. Dicts and scalars return None."""
    if isinstance(value, list):
        return list(cast(list[object], value))
    if isinstance(value, tuple):
        return list(cast(tuple[object, ...], value))
    return None


def mapping_get(mapping: Mapping[str, object], key: str) -> object:
    """Return ``mapping[key]`` or ``None`` when the key is absent (no default other than None)."""
    if key not in mapping:
        return None
    return mapping[key]
