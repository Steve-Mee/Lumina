"""Birth Phase v2 checkpoint persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.checkpoint")


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
) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": 2,
        "cumulative_trades": int(cumulative_trades),
        "ppo_steps": int(ppo_steps),
        "training_mode": str(training_mode).strip().lower(),
        "stages_passed": list(stages_passed),
        "curriculum_stage": str(curriculum_stage or ""),
        "policy_path": str(policy_path or ""),
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
    return {
        "cumulative_trades": max(0, int(payload.get("cumulative_trades", 0) or 0)),
        "ppo_steps": max(0, int(payload.get("ppo_steps", 0) or 0)),
        "stages_passed": list(payload.get("stages_passed") or []),
        "curriculum_stage": str(payload.get("curriculum_stage", "") or ""),
        "training_mode": str(payload.get("training_mode", "") or ""),
        "policy_path": str(payload.get("policy_path", "") or ""),
    }


def clear_checkpoint(workspace_root: Path | str) -> None:
    for path in checkpoint_paths(workspace_root):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("birth.checkpoint.clear_failed path=%s", path, exc_info=True)
