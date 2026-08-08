"""Progress → API status mapping (extracted from birth_service)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict

from lumina_core.first_boot_progress import (
    birth_runner_lock_active,
    birth_training_is_live,
    resolve_first_boot_stage,
    resolve_progress_active_max_age_sec,
)
BIRTH_ACTIVE_STAGES = frozenset(
    {
        "detected",
        "loading_data",
        "training_running",
        "pipeline_boot",
        "historical_loaded",
        "synthetic_top_up",
        "parallel_simulation",
        "ppo_training",
        "deferred_calendar",
        "simulation_stall_retry",
        "curriculum_learning",
        "curriculum_research",
        "data_expansion",
    }
)
LIGHTWEIGHT_STATUS_PHASES = frozenset(
    {
        "loading_history",
        "loading_history_failed",
        "enriching_news",
        "enriching_regimes",
        "train_holdout_split",
        "holdout_preflight",
        "holdout_preflight_expansion",
        "policy_init",
        "ticks_ready",
    }
)


def resolve_terminal_birth_status(progress: Dict[str, Any] | None) -> tuple[str, str] | None:
    """Map durable progress terminal phases to top-level API status (SSOT for recovery UI)."""
    if not progress:
        return None
    phase = str(progress.get("phase", "") or "").strip().lower()
    stage_name = str(progress.get("stage", "") or "").strip().lower()

    # Starship A5: paused + user_initiated_stop ≡ interrupted (one pause truth).
    if progress.get("user_initiated_stop") is True and stage_name in {
        "paused",
        "interrupted",
    }:
        message = str(
            progress.get("message")
            or "Birth Phase gestopt door gebruiker. Hervat checkpoint of wis birth-data."
        )
        return ("interrupted", message)
    if stage_name == "paused" and phase == "paused":
        message = str(progress.get("message") or "Birth Phase gepauzeerd.")
        return ("paused", message)

    if phase == "stage_stalled" or stage_name == "stage_stalled":
        message = str(
            progress.get("pass_reason")
            or progress.get("message")
            or "Curriculum stage stalled — metrics did not converge."
        )
        return ("stage_stalled", message)

    if phase == "error" or stage_name == "error":
        message = str(
            progress.get("last_error")
            or progress.get("message")
            or "Birth Phase gefaald"
        )
        return ("error", message)

    if phase in {"certificate_failed", "certificate_remediation"}:
        message = str(
            progress.get("message") or "Birth Certificate v2 thresholds not met."
        )
        return ("certificate_failed", message)

    if stage_name == "failed" and phase == "certificate_failed":
        message = str(
            progress.get("message") or "Birth Certificate v2 thresholds not met."
        )
        return ("certificate_failed", message)

    return None


def should_use_lightweight_status_enrichment(svc: Any, progress: Dict[str, Any]) -> bool:
    """Prefer lightweight enrichment whenever the training worker is not live.

    Cold app restart must return checkpoint_resumable / pause SSOT quickly so the
    Genesis UI can show Resume / Wipe without waiting on AI hardware probes or
    full maturity scans. Heavy enrichment still runs while training is live
    (cached artifact fields keep that path cheap).
    """
    if svc.is_running():
        return True
    # Cooperative stop drain — keep status snappy while worker finalizes.
    if hasattr(svc, "is_stopping") and svc.is_stopping():
        return True
    stage = str(progress.get("stage", "") or "").strip().lower()
    phase = str(progress.get("phase", "") or "").strip().lower()
    if stage == "loading_data" or phase in LIGHTWEIGHT_STATUS_PHASES:
        return True
    if progress.get("user_initiated_stop") is True:
        return True
    if stage in {"paused", "interrupted", "not_started", ""} or phase in {
        "paused",
        "interrupted",
        "",
    }:
        return True
    if resolve_terminal_birth_status(progress) is not None:
        return True
    return progress_indicates_running(svc, progress)




def resolve_elapsed_seconds_from_progress(progress: Dict[str, Any]) -> float:
    birth_start = float(progress.get("birth_start_time", 0) or 0)
    if birth_start > 0:
        start_sec = birth_start / 1000.0 if birth_start > 1e12 else birth_start
        return round(max(0.0, time.time() - start_sec), 1)
    elapsed = float(progress.get("elapsed_sec", 0) or 0)
    return round(elapsed, 1) if elapsed > 0 else 0.0


def progress_timestamp_age_sec(progress: Dict[str, Any]) -> float | None:
    raw = str(progress.get("timestamp", "") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return None


def progress_indicates_running(svc: Any, progress: Dict[str, Any]) -> bool:
    if resolve_terminal_birth_status(progress) is not None:
        return False
    phase = str(progress.get("phase", "") or "").strip().lower()
    stage_name = str(progress.get("stage", "") or "").strip().lower()
    if phase == "stage_stalled" or stage_name == "stage_stalled":
        return False
    stage = resolve_first_boot_stage(progress)
    if stage not in BIRTH_ACTIVE_STAGES:
        return False
    if not birth_training_is_live(svc.workspace_root, thread_running=svc.is_running()):
        return False
    lock_active = birth_runner_lock_active(svc.workspace_root)
    age = progress_timestamp_age_sec(progress)
    if age is None:
        return lock_active
    max_age = resolve_progress_active_max_age_sec(stage, runner_lock_active=lock_active)
    return age <= max_age

from lumina_launcher.services.birth_status_mapper_get import get_birth_status, sanitize_running_progress  # noqa: F401
