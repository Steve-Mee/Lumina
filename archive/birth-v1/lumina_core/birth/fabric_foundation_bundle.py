"""ADR-0040 Fabric foundation evidence bundle (Phase 2 / Perfect Birth auto-declare)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BUNDLE_REL = Path("state") / "fabric_foundation_bundle.json"

# Perfect Birth marker is the *output* of declare — not a pre-condition for auto-declare.
PRE_DECLARE_KEYS: tuple[str, ...] = (
    "fabric_only_sim101",
    "native_order_lifecycle",
    "heartbeat_safe_mode_flatten",
    "no_non_loopback_bind",
    "sentinel_zero_critical",
    "human_promotion_marker",
)


def fabric_foundation_bundle_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / BUNDLE_REL


def evaluate_fabric_foundation_bundle(workspace_root: Path | str) -> dict[str, Any]:
    """Fail-closed: missing or incomplete sidecar is not a green Fabric campaign."""
    path = fabric_foundation_bundle_path(workspace_root)
    if not path.is_file():
        return {
            "ok": False,
            "reason": "bundle_missing",
            "path": str(path),
            "missing": list(PRE_DECLARE_KEYS),
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "ok": False,
            "reason": "bundle_unreadable",
            "path": str(path),
            "missing": list(PRE_DECLARE_KEYS),
        }
    if not isinstance(raw, dict):
        return {
            "ok": False,
            "reason": "bundle_invalid",
            "path": str(path),
            "missing": list(PRE_DECLARE_KEYS),
        }
    missing = [key for key in PRE_DECLARE_KEYS if not bool(raw.get(key))]
    return {
        "ok": len(missing) == 0,
        "reason": "ok" if not missing else "bundle_incomplete",
        "path": str(path),
        "missing": missing,
        "keys": {key: bool(raw.get(key)) for key in PRE_DECLARE_KEYS},
    }
