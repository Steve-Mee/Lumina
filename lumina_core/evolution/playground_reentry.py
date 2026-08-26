"""Playground re-entry after policy_incompatible — never Birth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.evolution.challenger_venue.dna_namespace import challenger_state_root
from lumina_core.evolution.invalidation import POLICY_INCOMPATIBLE


def reentry_path(workspace: Path | str) -> Path:
    root = challenger_state_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    return root / "playground_reentry.json"


def request_playground_reentry(
    workspace: Path | str,
    *,
    invalidation: str,
    steve_approved: bool = False,
) -> dict[str, Any]:
    if str(invalidation) != POLICY_INCOMPATIBLE:
        return {"ok": False, "starts_birth": False, "reason": "not_policy_incompatible"}
    payload = {
        "phase": "playground",
        "skip_birth": True,
        "invalidation": POLICY_INCOMPATIBLE,
        "steve_approved": bool(steve_approved),
    }
    path = reentry_path(workspace)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"ok": True, "starts_birth": False, "path": str(path), "steve_approved": bool(steve_approved)}


def playground_reentry_may_start(workspace: Path | str) -> tuple[bool, str]:
    path = reentry_path(workspace)
    if not path.is_file():
        return False, "no_request"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "corrupt_request"
    if not isinstance(raw, dict):
        return False, "corrupt_request"
    if raw.get("skip_birth") is not True:
        return False, "birth_not_skipped"
    if not bool(raw.get("steve_approved")):
        return False, "awaiting_steve"
    from lumina_core.maturity.phase_specs import can_start_phase

    return can_start_phase(workspace, "playground")
