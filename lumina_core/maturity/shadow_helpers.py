"""Shared promotion / shadow audit helpers for proving ground + autopilot."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.maturity.shadow")


def audit_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "promotion_gate_audit.jsonl"


def shadow_gate_passed_from_audit(workspace_root: Path | str) -> tuple[bool, dict[str, Any]]:
    path = audit_path(workspace_root)
    if not path.is_file():
        return False, {}
    try:
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for line in reversed(lines[-50:]):
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            promoted = bool(row.get("promoted") or row.get("passed") or row.get("shadow_passed"))
            if promoted:
                return True, row
    except Exception as exc:
        logger.debug("maturity.shadow.audit_read_failed: %s", exc)
    return False, {}


def append_audit_row(workspace_root: Path | str, row: dict[str, Any]) -> None:
    path = audit_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True) + "\n")


def run_shadow_promotion_gate(workspace_root: Path | str) -> bool:
    """If audit already has a pass, record promotion milestone. Never fabricates pass."""
    try:
        passed, metadata = shadow_gate_passed_from_audit(workspace_root)
        if passed:
            from lumina_core.maturity.milestone_hooks import (
                hook_promotion_gate_passed,
                hook_shadow_validation_passed,
            )

            hook_promotion_gate_passed(
                workspace_root,
                mode=str(metadata.get("mode", "") or ""),
                dna_hash=str(metadata.get("dna_hash", "") or ""),
            )
            hook_shadow_validation_passed(
                workspace_root,
                shadow_status=str(metadata.get("shadow_status", "passed") or "passed"),
                dna_hash=str(metadata.get("dna_hash", "") or ""),
            )
        return passed
    except Exception as exc:
        logger.debug("maturity.shadow.run_failed: %s", exc)
        return False


def record_insufficient_shadow_evidence(workspace_root: Path | str, *, reason: str) -> None:
    """Honest fail row — never sets passed=true."""
    append_audit_row(
        workspace_root,
        {
            "passed": False,
            "promoted": False,
            "shadow_passed": False,
            "reason": reason or "insufficient_shadow_evidence",
            "source": "proving_ground_runner",
        },
    )
