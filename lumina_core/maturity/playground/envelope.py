"""Playground envelope pass — fail-closed. Missing file is unsealed."""
from __future__ import annotations

import json
from pathlib import Path

SEAL_REL = Path("state") / "lumina_sim_envelope_sealed.json"


def envelope_seal_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / SEAL_REL


def envelope_sealed_for_pass(workspace_root: Path | str) -> bool:
    """Operator sealed the SIM envelope. Legacy missing-file-as-sealed is not a pass."""
    path = envelope_seal_path(workspace_root)
    if not path.is_file():
        return False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(raw, dict):
        return False
    return raw.get("sealed") is True
