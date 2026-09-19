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

# Stale PPOEvolutionLogger / pip-install theatre after the physics stack is live.
_FIXED_PHYSICS_ERROR_MARKERS: tuple[str, ...] = (
    "PPOEvolutionLogger",
    "pip install stable-baselines3",
    "stable-baselines3 is required",
    "Leermotor ontbreekt",
    "install_birth_physics_stack",
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


def is_fixed_physics_logger_residual(progress: dict[str, Any] | None) -> bool:
    if not isinstance(progress, dict):
        return False
    stage = str(progress.get("stage") or "").strip().lower()
    phase = str(progress.get("phase") or "").strip().lower()
    code = str(progress.get("attention_reason_code") or "").strip().lower()
    if stage != "error" and phase != "error" and code not in {
        "physics_unavailable",
        "birth_error",
    }:
        return False
    blob = " ".join(
        str(progress.get(k) or "")
        for k in ("message", "last_error", "attention_summary", "attention_reason_code")
    )
    return any(m.lower() in blob.lower() for m in _FIXED_PHYSICS_ERROR_MARKERS)


def _write_cleared_residual(
    root: Path,
    prev: dict[str, Any],
    *,
    message: str,
    reason_code: str,
    actions: list[str],
    needs_attention: bool,
    stage: str = "paused",
) -> None:
    has_manifest = isinstance(prev.get("data_manifest"), dict) and bool(
        prev.get("data_manifest")
    )
    write_birth_progress(
        root,
        stage=stage,
        phase="residual_cleared_ready",
        message=message,
        progress_pct=float(prev.get("progress_pct", 26.0) or 26.0),
        cumulative_trades=int(
            prev.get("cumulative_trades", prev.get("trades_done", 0)) or 0
        ),
        target_trades=int(prev.get("target_trades", 0) or 0),
        ppo_steps=int(prev.get("ppo_steps", 0) or 0),
        birth_start_time=float(prev.get("birth_start_time", 0) or 0),
        needs_attention=needs_attention,
        retryable=True,
        last_error="",
        attention_reason_code=reason_code,
        attention_summary=message if needs_attention else "",
        attention_recommended_actions=actions,
        residual_failure=False,
        prior_stage=str(prev.get("prior_stage") or prev.get("stage") or ""),
        prior_phase=str(prev.get("prior_phase") or prev.get("phase") or ""),
        data_manifest=prev.get("data_manifest") if has_manifest else None,
        curriculum_stage=str(prev.get("curriculum_stage") or ""),
    )


def demote_fixed_birth_residuals(workspace_root: Path | str) -> dict[str, Any]:
    """Demote known-fixed hard residuals without wiping data_manifest / ticks.

    Does not auto-start birth.
    """
    root = Path(workspace_root)
    prev = read_birth_progress(root) or {}
    if is_fixed_write_birth_progress_residual(prev):
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
        _write_cleared_residual(
            root,
            prev,
            message=message,
            reason_code="residual_cleared_code_fix",
            actions=[
                "resume_from_checkpoint" if has_manifest else "retry_birth",
                "check_fabric_nt8",
                "test_connection",
            ],
            needs_attention=True,
        )
        return {
            "changed": True,
            "reason": "demoted_write_birth_progress_unboundlocal",
            "has_manifest": has_manifest,
        }

    if is_fixed_physics_logger_residual(prev):
        from lumina_core.birth.physics_preflight import probe_birth_physics

        probe = probe_birth_physics()
        if not probe.ok:
            return {
                "changed": False,
                "reason": "physics_still_unavailable",
                "missing": list(probe.missing),
                "python": probe.python_exe,
            }
        has_manifest = isinstance(prev.get("data_manifest"), dict) and bool(
            prev.get("data_manifest")
        )
        message = (
            "Leermotor is klaar. Tick-cache blijft geldig — activate Birth (Reuse data). "
            "Niet WIPE_FULL."
            if has_manifest
            else "Leermotor is klaar. Activate Birth. Niet WIPE_FULL."
        )
        _write_cleared_residual(
            root,
            prev,
            message=message,
            reason_code="residual_cleared_physics_ready",
            actions=["retry_birth"],
            needs_attention=False,
            stage="not_started",
        )
        return {
            "changed": True,
            "reason": "demoted_physics_logger_residual",
            "has_manifest": has_manifest,
            "python": probe.python_exe,
        }

    if (
        str(prev.get("phase") or "").strip().lower() == "residual_cleared_ready"
        and str(prev.get("attention_reason_code") or "") == "residual_cleared_physics_ready"
        and str(prev.get("stage") or "").strip().lower() == "paused"
    ):
        _write_cleared_residual(
            root,
            prev,
            message=str(prev.get("message") or "Leermotor is klaar. Activate Birth. Niet WIPE_FULL."),
            reason_code="residual_cleared_physics_ready",
            actions=["retry_birth"],
            needs_attention=False,
            stage="not_started",
        )
        return {"changed": True, "reason": "unpaused_physics_ready_residual"}

    return {"changed": False, "reason": "not_fixed_residual"}


__all__ = [
    "is_fixed_write_birth_progress_residual",
    "is_fixed_physics_logger_residual",
    "demote_fixed_birth_residuals",
]
