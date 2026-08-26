"""Honest birth residual cleanup after fixed hard errors (fail-closed).

Demotes known-fixed hard residuals (e.g. UnboundLocalError write_birth_progress)
to a retryable attention state without wiping data_manifest / checkpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.progress import read_birth_progress, write_birth_progress

# Residuals that are code bugs (now fixed) rather than market/capital faults.
_FIXED_HARD_ERROR_MARKERS: tuple[str, ...] = (
    "UnboundLocalError: cannot access local variable 'write_birth_progress'",
    "cannot access local variable 'write_birth_progress'",
)


def is_fixed_write_birth_progress_residual(progress: dict[str, Any] | None) -> bool:
    if not isinstance(progress, dict):
        return False
    stage = str(progress.get("stage") or "").strip().lower()
    phase = str(progress.get("phase") or "").strip().lower()
    if stage != "error" and phase != "error":
        return False
    blob = " ".join(
        str(progress.get(k) or "")
        for k in ("message", "last_error", "attention_summary")
    )
    return any(m in blob for m in _FIXED_HARD_ERROR_MARKERS)


def demote_fixed_birth_residuals(workspace_root: Path | str) -> dict[str, Any]:
    """If residual is a known-fixed UnboundLocal progress bug, mark honest resume.

    Preserves data_manifest / ticks cache. Does not auto-start birth.
    """
    root = Path(workspace_root)
    prev = read_birth_progress(root) or {}
    if not is_fixed_write_birth_progress_residual(prev):
        return {"changed": False, "reason": "not_fixed_residual"}

    has_manifest = isinstance(prev.get("data_manifest"), dict) and bool(
        prev.get("data_manifest")
    )
    message = (
        "Fixed residual: birth progress write bug is resolved. "
        "Data was already loaded — use Resume / Start Birth to continue (no wipe required)."
        if has_manifest
        else (
            "Fixed residual: birth progress write bug is resolved. "
            "Start Birth again (Fabric + historical_bars must be GREEN)."
        )
    )
    write_birth_progress(
        root,
        stage="paused",
        phase="residual_cleared_ready",
        message=message,
        progress_pct=float(prev.get("progress_pct", 26.0) or 26.0),
        cumulative_trades=int(
            prev.get("cumulative_trades", prev.get("trades_done", 0)) or 0
        ),
        target_trades=int(prev.get("target_trades", 0) or 0),
        ppo_steps=int(prev.get("ppo_steps", 0) or 0),
        birth_start_time=float(prev.get("birth_start_time", 0) or 0),
        needs_attention=True,
        retryable=True,
        last_error="",
        attention_reason_code="residual_cleared_code_fix",
        attention_summary=message,
        attention_recommended_actions=[
            "resume_from_checkpoint" if has_manifest else "retry_birth",
            "check_fabric_nt8",
            "test_connection",
        ],
        residual_failure=False,
        prior_stage=str(prev.get("prior_stage") or prev.get("stage") or ""),
        prior_phase=str(prev.get("prior_phase") or prev.get("phase") or ""),
        # Preserve curriculum/data honesty.
        data_manifest=prev.get("data_manifest"),
        curriculum_stage=str(prev.get("curriculum_stage") or ""),
    )
    return {
        "changed": True,
        "reason": "demoted_write_birth_progress_unboundlocal",
        "has_manifest": has_manifest,
    }


__all__ = [
    "is_fixed_write_birth_progress_residual",
    "demote_fixed_birth_residuals",
]
