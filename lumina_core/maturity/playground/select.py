"""Load Awakening child identity. No learn(). Frozen Birth π* is not the crawler."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.birth_exit_policy_export import file_sha256, resolve_pi_star_path
from lumina_core.maturity.birth_exit import is_birth_exit_sufficient
from lumina_core.maturity.phase_runners.awakening_shot import live_child_zip


def load_policy_identities(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root)
    child = live_child_zip(root)
    birth = resolve_pi_star_path(root)
    child_sha = file_sha256(child) if child.is_file() and child.stat().st_size > 0 else ""
    birth_sha = file_sha256(birth) if birth.is_file() and birth.stat().st_size > 0 else ""
    try:
        freeze_ok = bool(is_birth_exit_sufficient(root))
    except Exception:
        freeze_ok = False
    return {
        "child_sha": child_sha,
        "awakening_child_sha": child_sha,
        "birth_sha": birth_sha,
        "freeze_ok": freeze_ok,
        "child_zip": str(child) if child.is_file() else "",
        "birth_zip": str(birth) if birth.is_file() else "",
        "child_missing": not bool(child_sha),
    }
