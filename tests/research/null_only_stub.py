"""Passing null-only JSON for CLI tests that must reach a strategy cycle."""

from __future__ import annotations

import json
from pathlib import Path

from lumina_research.cycles.null_lock import NULL_ONLY_JSON
from lumina_research.cycles.null_model import NULL_BUILDER


def write_passing_null_only_json(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / NULL_ONLY_JSON
    payload = {
        "strict_gate_pass": True,
        "n_seeds": 32,
        "builder_after": NULL_BUILDER,
        "es_after": {"n_edge": 0, "n_a2": 0, "strict_pass": True},
        "synthetic_after": {"n_edge": 0, "n_a2": 0, "strict_pass": True},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
