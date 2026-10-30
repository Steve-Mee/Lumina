"""Research-run lock: no strategy cycle while the null FPR is above 4/32."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from lumina_research.cycles.null_model import NULL_BUILDER, classify_null_a2

NULL_ONLY_JSON = "phase5_p2_null_only_validation.json"
NULL_LEAK_REASON = (
    "research-run refused while the null leaks or has no passing null-only "
    "validation (strict 7/8 FPR must be <=3/32 on ES and synthetic)"
)


class NullLeaks(RuntimeError):
    """Strategy research ran before the null FPR lock cleared."""


def assert_research_allowed(report_dir: Path) -> None:
    path = report_dir / NULL_ONLY_JSON
    if not path.is_file():
        raise NullLeaks(NULL_LEAK_REASON)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise NullLeaks(NULL_LEAK_REASON) from exc
    if not isinstance(payload, dict):
        raise NullLeaks(NULL_LEAK_REASON)
    if payload.get("strict_gate_pass") is not True:
        raise NullLeaks(NULL_LEAK_REASON)
    if payload.get("builder_after") != NULL_BUILDER:
        raise NullLeaks(NULL_LEAK_REASON)
    n_seeds = _as_int(payload.get("n_seeds"), default=32)
    _require_reliable_edge(payload.get("es_after"), n_seeds=n_seeds)
    _require_reliable_edge(payload.get("synthetic_after"), n_seeds=n_seeds)


def _require_reliable_edge(block: object, *, n_seeds: int) -> None:
    if not isinstance(block, dict):
        raise NullLeaks(NULL_LEAK_REASON)
    mapping: Mapping[str, object] = block
    n_edge = _as_int(mapping.get("n_edge"), default=32)
    try:
        classified = classify_null_a2(n_edge, n_seeds)
    except ValueError as exc:
        raise NullLeaks(NULL_LEAK_REASON) from exc
    if not classified.reliable:
        raise NullLeaks(NULL_LEAK_REASON)


def _as_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise NullLeaks(NULL_LEAK_REASON)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise NullLeaks(NULL_LEAK_REASON) from exc
    raise NullLeaks(NULL_LEAK_REASON)
