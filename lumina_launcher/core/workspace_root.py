"""Workspace root resolution for launcher (SSOT, no service imports)."""

from __future__ import annotations

import os
from pathlib import Path

# lumina_launcher/core/workspace_root.py -> repo root
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_birth_workspace_root(explicit: Path | str | None = None) -> Path:
    """Resolve SSOT workspace root (never rely on process cwd)."""
    if explicit is not None and str(explicit).strip():
        return Path(explicit).expanduser().resolve()
    override = os.getenv("LUMINA_WORKSPACE_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _DEFAULT_REPO_ROOT.resolve()
