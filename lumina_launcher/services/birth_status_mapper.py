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
    if svc.is_running():
        return True
    stage = str(progress.get("stage", "") or "").strip().lower()
    phase = str(progress.get("phase", "") or "").strip().lower()
    if stage == "loading_data" or phase in LIGHTWEIGHT_STATUS_PHASES:
        return True
    return progress_indicates_running(svc, progress)


def sanitize_running_progress(progress: Dict[str, Any]) -> Dict[str, Any]:
    """Drop stale failure phases while a birth run is actively executing."""
    sanitized = dict(progress)
    phase = str(sanitized.get("phase", "") or "").strip().lower()
    stage = str(sanitized.get("stage", "") or "").strip().lower()
    if phase in {
        "stage_stalled",
        "certificate_failed",
        "certificate_remediation",
        "error",
    } or stage in {
        "stage_stalled",
        "failed",
        "error",
    }:
        sanitized["phase"] = "loading_history"
        sanitized["stage"] = "loading_data"
        sanitized.pop("terminal_stall_reason", None)
        sanitized.pop("pass_reason", None)
        sanitized.pop("last_error", None)
        sanitized["retryable"] = True
        sanitized["needs_attention"] = False
    if phase in {"curriculum_failed", "simulation_stall"}:
        sanitized["phase"] = "curriculum_learning"
        sanitized["stage"] = "training_running"
    active_training_phases = {
        "curriculum_learning",
        "curriculum_stage",
        "curriculum_research",
        "ppo_training",
        "parallel_simulation",
        "curriculum_stage_complete",
        "ppo_polish",
        "policy_init",
        "ticks_ready",
        "loading_history",
        "enriching_regimes",
        "enriching_news",
    }
    if phase in active_training_phases or sanitized.get("stage") == "training_running":
        # Starship: preserve swarm no-lift attention while training (fail-closed UX).
        starship_attention = str(sanitized.get("attention_reason_code", "") or "") in {
            "swarm_no_edgescore_lift",  # legacy synonym
            "swarm_no_tournament_lift",
            "swarm_inconclusive_sample",
            "swarm_frozen_windows_missing",
            "swarm_incomplete_restore",
        } or bool(sanitized.get("swarm_rejected_no_lift"))
        if not starship_attention:
            sanitized.pop("needs_attention", None)
            sanitized.pop("attention_summary", None)
            sanitized.pop("attention_reason_code", None)
            sanitized.pop("attention_recommended_actions", None)
            sanitized.pop("attention_notified_at", None)
        sanitized["user_initiated_stop"] = False
    birth_start = float(sanitized.get("birth_start_time", 0) or 0)
    if birth_start > 0:
        start_sec = birth_start / 1000.0 if birth_start > 1e12 else birth_start
        sanitized["elapsed_sec"] = round(max(0.0, time.time() - start_sec), 2)
    return sanitized


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


def get_birth_status(svc: Any) -> Dict[str, Any]:
    """Build top-level birth status payload (enrichment applied separately)."""
    from lumina_launcher.services import birth_status_enricher as _enricher

    svc._maybe_execute_autonomous_recovery()
    # Orphan reconcile must run on every status poll (not only workspace bind).
    # Otherwise a dead runner leaves training_running on disk → API returns idle
    # and the UI never offers Resume / Wipe after an app restart.
    if not svc.is_running():
        svc.reconcile_orphaned_birth_progress()
    svc._maybe_auto_resume_stalled_birth()
    progress = svc._load_progress()
    lightweight = should_use_lightweight_status_enrichment(svc, progress)

    def _ai() -> dict[str, Any]:
        return _enricher.adaptive_intelligence_status(svc, lightweight=lightweight)

    terminal = resolve_terminal_birth_status(progress)
    if terminal is not None and not svc.is_running():
        terminal_status, terminal_message = terminal
        live = birth_training_is_live(svc.workspace_root, thread_running=False)
        payload: Dict[str, Any] = {
            "progress": progress,
            "live": live,
            "status": terminal_status,
            "progress_pct": float(progress.get("progress_pct", 0) or 0),
            "message": terminal_message,
            "result": svc._result,
            "orphaned": False,
            "adaptive_intelligence": _ai(),
        }
        if terminal_status == "error":
            payload["error"] = terminal_message
        return _enricher.enrich_birth_status(svc, payload)

    if svc.is_running() or progress_indicates_running(svc, progress):
        progress = sanitize_running_progress(progress)
    live = birth_training_is_live(svc.workspace_root, thread_running=svc.is_running())
    stage = resolve_first_boot_stage(progress)
    base_meta = {"progress": progress, "live": live}

    if svc._error:
        return _enricher.enrich_birth_status(
            svc,
            {
                **base_meta,
                "status": "error",
                "error": svc._error,
                "message": "Birth Phase gefaald",
                "orphaned": False,
                "adaptive_intelligence": _ai(),
            },
        )

    if svc.is_running():
        return _enricher.enrich_birth_status(
            svc,
            {
                **base_meta,
                "status": "running",
                "runner": "thread",
                "elapsed_seconds": round(time.time() - svc._start_time, 1) if svc._start_time else 0,
                "message": "Birth Phase draait...",
                "orphaned": False,
                "adaptive_intelligence": _ai(),
            },
        )

    if progress_indicates_running(svc, progress):
        from lumina_launcher.services.birth_runner_lock import read_runner_lock

        runner_meta = read_runner_lock(svc) or {}
        return _enricher.enrich_birth_status(
            svc,
            {
                **base_meta,
                "status": "running",
                "runner": str(runner_meta.get("runner", "file_progress")),
                "message": str(progress.get("message") or "Birth Phase actief (cross-process)."),
                "runner_pid": runner_meta.get("pid"),
                "runner_host": runner_meta.get("host"),
                "elapsed_seconds": resolve_elapsed_seconds_from_progress(progress),
                "orphaned": False,
                "adaptive_intelligence": _ai(),
            },
        )

    if svc.completed_flag.exists():
        cert_ok = svc.certificate_ok()
        if not cert_ok:
            phase = str(progress.get("phase", "") or "").lower()
            stage_name = str(progress.get("stage", "") or "").lower()
            if phase == "certificate_failed" or stage_name == "failed":
                status = "certificate_failed"
                message = str(
                    progress.get("message") or "Birth Certificate v2 thresholds not met."
                )
            else:
                status = "certificate_failed"
                message = (
                    "Birth completion flag present but Birth Certificate v2 is missing or invalid."
                )
            return _enricher.enrich_birth_status(
                svc,
                {
                    **base_meta,
                    "status": status,
                    "progress_pct": float(progress.get("progress_pct", 100) or 100),
                    "message": message,
                    "result": svc._result,
                    "orphaned": False,
                    "adaptive_intelligence": _ai(),
                },
            )
        return _enricher.enrich_birth_status(
            svc,
            {
                **base_meta,
                "status": "completed",
                "progress_pct": 100,
                "message": "Birth Phase complete",
                "result": svc._result,
                "orphaned": False,
                "adaptive_intelligence": _ai(),
            },
        )

    if stage in {"interrupted", "paused"} or progress.get("user_initiated_stop") is True:
        status_name = "interrupted" if progress.get("user_initiated_stop") is True else "paused"
        if stage == "interrupted":
            status_name = "interrupted"
        return _enricher.enrich_birth_status(
            svc,
            {
                **base_meta,
                "status": status_name,
                "orphaned": status_name == "interrupted",
                "message": str(
                    progress.get("message")
                    or "Vorige sessie onderbroken — klik Hervat checkpoint om verder te gaan."
                ),
                "adaptive_intelligence": _ai(),
            },
        )

    terminal = resolve_terminal_birth_status(progress)
    if terminal is not None:
        terminal_status, terminal_message = terminal
        return _enricher.enrich_birth_status(
            svc,
            {
                **base_meta,
                "status": terminal_status,
                "progress_pct": float(progress.get("progress_pct", 0) or 0),
                "message": terminal_message,
                "result": svc._result,
                "orphaned": False,
                "adaptive_intelligence": _ai(),
            },
        )

    if isinstance(svc._result, dict) and svc._result and svc._progress_is_persisted():
        status = str(svc._result.get("status", "idle") or "idle")
        msg = str(progress.get("message") or svc._result.get("message") or "Birth Phase klaar.")
        return _enricher.enrich_birth_status(
            svc,
            {
                **base_meta,
                "status": status,
                "result": svc._result,
                "message": msg,
                "orphaned": False,
                "adaptive_intelligence": _ai(),
            },
        )
    return _enricher.enrich_birth_status(
        svc,
        {
            **base_meta,
            "status": "idle",
            "message": "Birth Phase nog niet gestart",
            "orphaned": False,
            "adaptive_intelligence": _ai(),
        },
    )