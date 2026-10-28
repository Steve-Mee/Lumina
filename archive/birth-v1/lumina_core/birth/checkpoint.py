"""Birth Phase v2 checkpoint persistence (v3 — buffer + stage metrics + data manifest)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.quality_score import quality_score_from_manifest
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.checkpoint")

CHECKPOINT_VERSION = 3


def checkpoint_paths(workspace_root: Path | str) -> tuple[Path, Path]:
    root = Path(workspace_root)
    return (
        root / "state" / "lumina_birth_checkpoint.json",
        root / "state" / "first_boot_checkpoint.json",
    )


def read_checkpoint_payload(workspace_root: Path | str) -> dict[str, Any] | None:
    candidates = [p for p in checkpoint_paths(workspace_root) if p.exists()]
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def can_resume_checkpoint(
    workspace_root: Path | str,
    *,
    training_mode: str,
    completion_flag_paths: tuple[Path, Path],
) -> bool:
    if any(p.exists() for p in completion_flag_paths):
        return False
    payload = read_checkpoint_payload(workspace_root)
    if not payload:
        return False
    ckpt_mode = str(payload.get("training_mode", "") or "").strip().lower()
    desired = str(training_mode).strip().lower()
    if ckpt_mode and ckpt_mode != desired:
        return False
    if not ckpt_mode and desired == "certified":
        return False
    return True


def default_completion_flag_paths(workspace_root: Path | str) -> tuple[Path, Path]:
    root = Path(workspace_root)
    return (
        root / "state" / "lumina_birth_completed.flag",
        root / "state" / "first_boot_completed.flag",
    )


def is_checkpoint_resumable(
    workspace_root: Path | str,
    *,
    training_mode: str = "certified",
) -> bool:
    """True when a on-disk checkpoint can resume curriculum (SSOT for UI resume button)."""
    root = Path(workspace_root)
    if not can_resume_checkpoint(
        root,
        training_mode=training_mode,
        completion_flag_paths=default_completion_flag_paths(root),
    ):
        return False
    payload = read_checkpoint_payload(root)
    if not payload:
        return False
    curriculum_stage = str(payload.get("curriculum_stage", "") or "").strip()
    if not curriculum_stage:
        return False
    cumulative = max(0, int(payload.get("cumulative_trades", 0) or 0))
    ppo_steps = max(0, int(payload.get("ppo_steps", 0) or 0))
    if cumulative <= 0 and ppo_steps <= 0:
        return False
    policy_path = str(payload.get("policy_path", "") or "").strip()
    if policy_path and not Path(policy_path).is_file():
        return False
    return True


def save_checkpoint(
    workspace_root: Path | str,
    *,
    cumulative_trades: int,
    ppo_steps: int,
    training_mode: str,
    stages_passed: list[str],
    curriculum_stage: str | None = None,
    policy_path: str | None = None,
    stage_metrics: dict[str, Any] | None = None,
    buffer_path: str | None = None,
    data_manifest: dict[str, Any] | None = None,
    phase: str | None = None,
    remediation_attempt: int = 0,
    stage_pass_receipts: list[dict[str, Any]] | None = None,
    oos_metrics: dict[str, Any] | None = None,
) -> None:
    manifest = dict(data_manifest or {})
    metrics = dict(stage_metrics or {})
    if stages_passed and "stages_passed" not in metrics:
        metrics["stages_passed"] = list(stages_passed)
    quality = quality_score_from_manifest(manifest, metrics)
    existing = read_checkpoint_payload(workspace_root)
    receipts_payload: list[dict[str, Any]] = []
    if stage_pass_receipts is not None:
        receipts_payload = [dict(r) for r in stage_pass_receipts]
    elif isinstance(existing, dict):
        raw_receipts = existing.get("stage_pass_receipts")
        if isinstance(raw_receipts, list):
            receipts_payload = [dict(r) for r in raw_receipts if isinstance(r, dict)]
    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": CHECKPOINT_VERSION,
        "cumulative_trades": int(cumulative_trades),
        "ppo_steps": int(ppo_steps),
        "training_mode": str(training_mode).strip().lower(),
        "stages_passed": list(stages_passed),
        "stage_pass_receipts": receipts_payload,
        "curriculum_stage": str(curriculum_stage or ""),
        "policy_path": str(policy_path or ""),
        "buffer_path": str(buffer_path or ""),
        "stage_metrics": metrics,
        "data_manifest": manifest,
        "quality_score": quality,
        "phase": str(phase or ""),
        "remediation_attempt": int(remediation_attempt),
    }
    if oos_metrics is not None:
        payload["oos_metrics"] = dict(oos_metrics)
    elif isinstance(existing, dict) and isinstance(existing.get("oos_metrics"), dict):
        payload["oos_metrics"] = dict(existing["oos_metrics"])
    encoded = json.dumps(payload, ensure_ascii=True, indent=2)
    for path in checkpoint_paths(workspace_root):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded, encoding="utf-8")
        except OSError:
            logger.warning("birth.checkpoint.write_failed path=%s", path, exc_info=True)


def load_checkpoint_state(workspace_root: Path | str) -> dict[str, Any]:
    payload = read_checkpoint_payload(workspace_root)
    if not payload:
        return {}
    version = int(payload.get("version", 2) or 2)
    stage_metrics = payload.get("stage_metrics")
    data_manifest = payload.get("data_manifest")
    return {
        "version": version,
        "cumulative_trades": max(0, int(payload.get("cumulative_trades", 0) or 0)),
        "ppo_steps": max(0, int(payload.get("ppo_steps", 0) or 0)),
        "stages_passed": list(payload.get("stages_passed") or []),
        "stage_pass_receipts": list(payload.get("stage_pass_receipts") or []),
        "curriculum_stage": str(payload.get("curriculum_stage", "") or ""),
        "training_mode": str(payload.get("training_mode", "") or ""),
        "policy_path": str(payload.get("policy_path", "") or ""),
        "buffer_path": str(payload.get("buffer_path", "") or ""),
        "stage_metrics": stage_metrics if isinstance(stage_metrics, dict) else {},
        "data_manifest": data_manifest if isinstance(data_manifest, dict) else {},
        "quality_score": float(payload.get("quality_score", 0.0) or 0.0),
        "phase": str(payload.get("phase", "") or ""),
        "remediation_attempt": max(0, int(payload.get("remediation_attempt", 0) or 0)),
        "oos_metrics": (
            dict(payload["oos_metrics"])
            if isinstance(payload.get("oos_metrics"), dict)
            else {}
        ),
    }


def clear_checkpoint(workspace_root: Path | str) -> None:
    for path in checkpoint_paths(workspace_root):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("birth.checkpoint.clear_failed path=%s", path, exc_info=True)


def reset_adaptation_budget_in_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Reset per-tier retry window for manual resume from stage_stalled."""
    merged = dict(metrics)
    merged["retries_this_stage"] = 0
    return merged


def write_checkpoint_payload(workspace_root: Path | str, payload: dict[str, Any]) -> None:
    """Persist a full checkpoint JSON blob (merge-safe updates)."""
    existing = [p for p in checkpoint_paths(workspace_root) if p.is_file()]
    target = existing[0] if existing else checkpoint_paths(workspace_root)[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def reset_adaptation_budget_for_manual_resume(workspace_root: Path | str) -> bool:
    """Persist retries_this_stage=0 in checkpoint stage_metrics before resume."""
    from lumina_core.birth.progress import read_birth_progress, write_birth_progress

    payload = read_checkpoint_payload(workspace_root)
    if not payload:
        return False
    metrics = payload.get("stage_metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    payload["stage_metrics"] = reset_adaptation_budget_in_metrics(metrics)
    if str(payload.get("phase", "") or "").strip().lower() == "stage_stalled":
        payload["phase"] = "curriculum_learning"
    write_checkpoint_payload(workspace_root, payload)

    progress = read_birth_progress(workspace_root)
    phase = str(progress.get("phase", "") or "").strip().lower()
    stage = str(progress.get("stage", "") or "").strip().lower()
    if phase == "stage_stalled" or stage == "stage_stalled":
        write_birth_progress(
            workspace_root,
            stage="training_running",
            phase="curriculum_learning",
            message=str(progress.get("message") or "Resuming curriculum stage after stall recovery."),
            progress_pct=float(progress.get("progress_pct", 0) or 0),
            cumulative_trades=int(
                progress.get("cumulative_trades", progress.get("trades_done", 0)) or 0
            ),
            target_trades=int(progress.get("target_trades", 0) or 0),
            ppo_steps=int(progress.get("ppo_steps", 0) or 0),
            birth_start_time=float(progress.get("birth_start_time", 0) or 0),
            curriculum_stage=str(progress.get("curriculum_stage", "") or ""),
            pass_reason=str(progress.get("pass_reason", "") or ""),
            stage_blocker_metric=progress.get("stage_blocker_metric"),
            stage_blocker_value=progress.get("stage_blocker_value"),
            retries_this_stage=0,
            adaptation_tier=metrics.get("adaptation_tier"),
            adaptation_history=metrics.get("adaptation_history"),
        )
    return True


def apply_plateau_quarantine_on_checkpoint_resume(
    *,
    cfg: Any,
    stage_trades: int,
    required: int | None = None,
) -> dict[str, Any]:
    """SSOT entry: grace period after checkpoint resume (delegates to plateau escalator)."""
    from lumina_core.birth.plateau_escalator import apply_plateau_quarantine_on_resume

    return apply_plateau_quarantine_on_resume(
        cfg=cfg,
        stage_trades=stage_trades,
        required=required,
    )
