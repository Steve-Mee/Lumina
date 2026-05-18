"""Canonical first-boot progress and target-trade resolvers."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from lumina_core.first_boot_ui import FIRST_BOOT_DEFAULT_TRADES, normalize_first_boot_training_trades

BirthTrainingPulse = Literal["active", "stale", "idle"]

BIRTH_LOADING_DATA_MAX_AGE_SEC = 600.0
BIRTH_LOADING_DATA_MAX_AGE_WITHOUT_LOCK_SEC = 45.0
BIRTH_PROGRESS_DEFAULT_MAX_AGE_SEC = 120.0
BIRTH_RUNNER_LOCK_FILENAME = "birth_runner.json"

_ACTIVE_TRAINING_STAGES = frozenset(
    {
        "detected",
        "loading_data",
        "training_running",
        "pipeline_boot",
        "parallel_simulation",
        "ppo_training",
        "historical_loaded",
        "synthetic_top_up",
    }
)

_STAGE_ALIASES: dict[str, str] = {
    # BIRTH ENGINE 2026-05-17
    "birth_phase": "training_running",
    "birth_running": "training_running",
    "birth_detected": "detected",
    "birth_loading_data": "loading_data",
    "birth_paused": "paused",
    "birth_completed": "completed",
    "birth_completed_waiting_user_action": "completed_waiting_user_action",
}


def resolve_first_boot_completed_trades(progress: Mapping[str, Any] | None) -> int:
    src = progress or {}
    for key in ("trades_done", "trades", "sim_trades", "cumulative_trades", "total_trades", "birth_trades"):
        value = src.get(key)
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count >= 0:
            return count
    return 0


def resolve_first_boot_target_trades(config_payload: Mapping[str, Any] | None) -> int:
    cfg = config_payload or {}
    first_boot = cfg.get("first_boot")
    if not isinstance(first_boot, Mapping):
        return FIRST_BOOT_DEFAULT_TRADES
    return normalize_first_boot_training_trades(first_boot.get("training_trades", FIRST_BOOT_DEFAULT_TRADES))


def resolve_first_boot_target_from_progress(progress: Mapping[str, Any] | None) -> int:
    src = progress or {}
    raw = src.get("target_trades")
    try:
        target = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, target)


def resolve_effective_first_boot_target_trades(
    *,
    progress: Mapping[str, Any] | None,
    config_payload: Mapping[str, Any] | None,
) -> int:
    """Resolve target trades for UI surfaces.

    Rule-set:
    - During active training stages, progress target is authoritative.
    - Otherwise prefer config target so edited/saved settings are visible immediately.
    - Fall back to progress target, then canonical default.
    """
    progress_target = resolve_first_boot_target_from_progress(progress)
    config_target = resolve_first_boot_target_trades(config_payload)
    stage = resolve_first_boot_stage(progress)
    if stage in _ACTIVE_TRAINING_STAGES and progress_target > 0:
        return progress_target
    if config_target > 0:
        return config_target
    if progress_target > 0:
        return progress_target
    return FIRST_BOOT_DEFAULT_TRADES


def resolve_first_boot_target_for_display(
    *,
    progress: Mapping[str, Any] | None,
    config_payload: Mapping[str, Any] | None,
    session_trades: int | None = None,
) -> int:
    """Resolve target for UI display with optional unsaved form draft.

    Priority:
    1) Active training progress target.
    2) Session draft (when user edits form but has not saved yet).
    3) Persisted config target.
    4) Non-active progress target.
    5) Canonical default.
    """
    progress_target = resolve_first_boot_target_from_progress(progress)
    stage = resolve_first_boot_stage(progress)
    if stage in _ACTIVE_TRAINING_STAGES and progress_target > 0:
        return progress_target
    draft_target = None
    if session_trades is not None:
        try:
            draft_target = normalize_first_boot_training_trades(session_trades)
        except (TypeError, ValueError):
            draft_target = None
    if draft_target is not None and draft_target > 0:
        return draft_target
    return resolve_effective_first_boot_target_trades(progress=progress, config_payload=config_payload)


def birth_runner_lock_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root).resolve() / "state" / BIRTH_RUNNER_LOCK_FILENAME


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            return str(pid) in (result.stdout or "")
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_birth_runner_lock(workspace_root: Path | str | None) -> dict[str, Any] | None:
    if workspace_root is None or not str(workspace_root).strip():
        return None
    path = birth_runner_lock_path(workspace_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def birth_runner_lock_exists(workspace_root: Path | str | None) -> bool:
    return read_birth_runner_lock(workspace_root) is not None


def birth_runner_lock_active(workspace_root: Path | str | None) -> bool:
    """True when birth_runner.json exists and its PID (if any) is still alive."""
    payload = read_birth_runner_lock(workspace_root)
    if payload is None:
        return False
    raw_pid = payload.get("pid")
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError):
        return True
    return _pid_alive(pid)


def birth_training_is_live(
    workspace_root: Path | str | None,
    *,
    thread_running: bool = False,
) -> bool:
    """True only when a Birth Phase thread or live runner lock proves training is running."""
    return bool(thread_running) or birth_runner_lock_active(workspace_root)


def resolve_progress_active_max_age_sec(stage: str, *, runner_lock_active: bool = False) -> float:
    """How long a progress timestamp may be old while still considered live."""
    normalized = str(stage or "").strip().lower()
    if normalized == "loading_data":
        if runner_lock_active:
            return BIRTH_LOADING_DATA_MAX_AGE_SEC
        return BIRTH_LOADING_DATA_MAX_AGE_WITHOUT_LOCK_SEC
    if normalized in {"ppo_training", "parallel_simulation"}:
        return BIRTH_PROGRESS_DEFAULT_MAX_AGE_SEC
    return 30.0


def progress_timestamp_age_seconds(progress: Mapping[str, Any] | None) -> float | None:
    raw = str((progress or {}).get("timestamp") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds())
    except ValueError:
        return None


def progress_is_recently_active(
    progress: Mapping[str, Any] | None,
    *,
    stage: str,
    workspace_root: Path | str | None = None,
    thread_running: bool = False,
) -> bool:
    normalized = resolve_first_boot_stage(progress) or str(stage or "").strip().lower()
    if normalized not in _ACTIVE_TRAINING_STAGES:
        return False
    lock_active = birth_runner_lock_active(workspace_root)
    if not birth_training_is_live(workspace_root, thread_running=thread_running) and not lock_active:
        return False
    age = progress_timestamp_age_seconds(progress)
    if age is None:
        return lock_active
    return age < resolve_progress_active_max_age_sec(normalized, runner_lock_active=lock_active)


def resolve_birth_training_pulse(
    progress: Mapping[str, Any] | None,
    *,
    birth_running: bool = False,
    birth_stopping: bool = False,
    process_alive: bool = False,
    debug_proc_running: bool = False,
    workspace_root: Path | str | None = None,
    thread_running: bool = False,
) -> BirthTrainingPulse:
    if birth_running or birth_stopping or process_alive or debug_proc_running:
        return "active"
    live = birth_training_is_live(workspace_root, thread_running=thread_running)
    stage = resolve_first_boot_stage(progress)
    if not progress or stage not in _ACTIVE_TRAINING_STAGES:
        if str(stage or "").strip().lower() == "interrupted":
            return "stale"
        return "idle"
    if not live:
        return "stale"
    if progress_is_recently_active(
        progress,
        stage=stage,
        workspace_root=workspace_root,
        thread_running=thread_running,
    ):
        return "active"
    return "stale"


def format_progress_heartbeat_age(progress: Mapping[str, Any] | None) -> str:
    age = progress_timestamp_age_seconds(progress)
    if age is None:
        return "— ago"
    if age < 120.0:
        return f"{age:.1f}s ago"
    if age < 3600.0:
        return f"{age / 60.0:.1f}m ago"
    return f"{age / 3600.0:.1f}h ago"


def is_active_training_stage(progress: Mapping[str, Any] | None, *, stage: str = "") -> bool:
    normalized = resolve_first_boot_stage(progress) or str(stage or "").strip().lower()
    return normalized in _ACTIVE_TRAINING_STAGES


def resolve_first_boot_stage(progress: Mapping[str, Any] | None) -> str:
    src = progress or {}
    stage = str(src.get("stage", "")).strip().lower()
    if not stage:
        return stage
    return _STAGE_ALIASES.get(stage, stage)


def is_sim_trades_complete(progress: Mapping[str, Any] | None) -> bool:
    src = progress or {}
    if src.get("sim_trades_complete") is True:
        return True
    target = resolve_first_boot_target_from_progress(src)
    if target <= 0:
        return False
    return resolve_first_boot_completed_trades(src) >= target


def resolve_ppo_batch_progress(progress: Mapping[str, Any] | None) -> tuple[int, int, float | None]:
    src = progress or {}
    try:
        batch_steps = max(0, int(src.get("ppo_batch_steps", 0) or 0))
    except (TypeError, ValueError):
        batch_steps = 0
    try:
        batch_total = max(0, int(src.get("ppo_batch_total", 0) or 0))
    except (TypeError, ValueError):
        batch_total = 0
    if batch_total <= 0:
        return batch_steps, 0, None
    raw_pct = src.get("ppo_batch_progress_pct", src.get("ppo_progress_pct"))
    try:
        pct = float(raw_pct)
        if pct < 0 or pct > 100:
            pct = (float(batch_steps) / float(batch_total)) * 100.0
    except (TypeError, ValueError):
        pct = (float(batch_steps) / float(batch_total)) * 100.0
    return batch_steps, batch_total, round(pct, 2)


def resolve_ppo_training_progress(
    progress: Mapping[str, Any] | None,
    *,
    default_total_steps: int = 300_000,
) -> tuple[int, int, float | None]:
    src = progress or {}
    # BIRTH ENGINE 2026-05-17
    raw_cumulative = src.get(
        "ppo_steps_cumulative",
        src.get("ppo_steps", src.get("policy_steps", src.get("birth_ppo_steps", 0))),
    )
    raw_total = src.get("ppo_timesteps_planned_total", src.get("ppo_timesteps_total", default_total_steps))
    try:
        cumulative = max(0, int(raw_cumulative or 0))
    except (TypeError, ValueError):
        cumulative = 0
    display_steps = cumulative
    try:
        total_steps = max(1, int(raw_total or default_total_steps))
    except (TypeError, ValueError):
        total_steps = max(1, int(default_total_steps))
    if display_steps > 0 and total_steps > 0:
        pct = (float(display_steps) / float(total_steps)) * 100.0
    else:
        pct = None
    return display_steps, total_steps, (round(pct, 2) if pct is not None else None)


def resolve_ppo_progress_interval(config_payload: Mapping[str, Any] | None) -> int:
    cfg = config_payload or {}
    first_boot = cfg.get("first_boot")
    raw = None
    if isinstance(first_boot, Mapping):
        raw = first_boot.get("ppo_progress_interval")
    try:
        value = int(raw or 10_000)
    except (TypeError, ValueError):
        value = 10_000
    return max(1_000, min(100_000, value))
