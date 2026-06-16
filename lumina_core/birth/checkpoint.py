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
) -> None:
    manifest = dict(data_manifest or {})
    metrics = dict(stage_metrics or {})
    if stages_passed and "stages_passed" not in metrics:
        metrics["stages_passed"] = list(stages_passed)
    quality = quality_score_from_manifest(manifest, metrics)
    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": CHECKPOINT_VERSION,
        "cumulative_trades": int(cumulative_trades),
        "ppo_steps": int(ppo_steps),
        "training_mode": str(training_mode).strip().lower(),
        "stages_passed": list(stages_passed),
        "curriculum_stage": str(curriculum_stage or ""),
        "policy_path": str(policy_path or ""),
        "buffer_path": str(buffer_path or ""),
        "stage_metrics": metrics,
        "data_manifest": manifest,
        "quality_score": quality,
        "phase": str(phase or ""),
        "remediation_attempt": int(remediation_attempt),
    }
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
        "curriculum_stage": str(payload.get("curriculum_stage", "") or ""),
        "training_mode": str(payload.get("training_mode", "") or ""),
        "policy_path": str(payload.get("policy_path", "") or ""),
        "buffer_path": str(payload.get("buffer_path", "") or ""),
        "stage_metrics": stage_metrics if isinstance(stage_metrics, dict) else {},
        "data_manifest": data_manifest if isinstance(data_manifest, dict) else {},
        "quality_score": float(payload.get("quality_score", 0.0) or 0.0),
        "phase": str(payload.get("phase", "") or ""),
        "remediation_attempt": max(0, int(payload.get("remediation_attempt", 0) or 0)),
    }


def clear_checkpoint(workspace_root: Path | str) -> None:
    for path in checkpoint_paths(workspace_root):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("birth.checkpoint.clear_failed path=%s", path, exc_info=True)
