"""get_birth_status / sanitize helpers (M5)."""
from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any, Dict

from lumina_core.first_boot_progress import birth_training_is_live, resolve_first_boot_stage


logger = logging.getLogger(__name__)

def _m():
    from lumina_launcher.services import birth_status_mapper as m
    return m

def sanitize_running_progress(progress: Dict[str, Any]) -> Dict[str, Any]:
    """Drop stale failure phases while a birth run is actively executing."""
    from lumina_core.birth.starship_swarm_gates import (
        CANONICAL_SWARM_NO_LIFT_REASON,
        LEGACY_SWARM_NO_LIFT_REASON,
        prefer_tournament_progress_keys,
    )

    # Track C: tournament physics names primary; legacy edgescore aliases still read.
    sanitized = prefer_tournament_progress_keys(progress)
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
        reason = str(sanitized.get("attention_reason_code", "") or "")
        starship_attention = reason in {
            LEGACY_SWARM_NO_LIFT_REASON,
            CANONICAL_SWARM_NO_LIFT_REASON,
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

def get_birth_status(svc: Any) -> Dict[str, Any]:
    """Build top-level birth status payload (enrichment applied separately)."""
    from lumina_launcher.services import birth_status_enricher as _enricher

    svc._maybe_execute_autonomous_recovery()
    # Remote autonomy: while freeze is open, poll Telegram for ACCEPT/WIPE
    # (throttled) so the operator need not be at the PC.
    try:
        from lumina_core.birth.champion_freeze_telegram import maybe_poll_freeze_telegram

        maybe_poll_freeze_telegram(svc.workspace_root)
    except Exception as exc:
        logger.debug("birth.status.freeze_telegram_poll_failed: %s", exc)
    # Orphan reconcile must run on every status poll (not only workspace bind).
    # Otherwise a dead runner leaves training_running on disk → API returns idle
    # and the UI never offers Resume / Wipe after an app restart.
    if not svc.is_running():
        svc.reconcile_orphaned_birth_progress()
    svc._maybe_auto_resume_stalled_birth()
    progress = svc._load_progress()
    lightweight = _m().should_use_lightweight_status_enrichment(svc, progress)

    def _ai() -> dict[str, Any]:
        return _enricher.adaptive_intelligence_status(svc, lightweight=lightweight)

    terminal = _m().resolve_terminal_birth_status(progress)
    # Operator stop / terminal failure wins over a still-draining worker thread.
    # Previously is_running() forced status=running after Stop, so UI looked "stuck".
    if terminal is not None and (
        not svc.is_running()
        or progress.get("user_initiated_stop") is True
        or (hasattr(svc, "is_stopping") and svc.is_stopping())
    ):
        terminal_status, terminal_message = terminal
        thread_still = bool(svc.is_running())
        live = birth_training_is_live(
            svc.workspace_root,
            thread_running=thread_still and progress.get("user_initiated_stop") is not True,
        )
        payload: Dict[str, Any] = {
            "progress": progress,
            "live": live,
            "status": terminal_status if not thread_still else (
                "stopping" if progress.get("user_initiated_stop") is True else terminal_status
            ),
            "progress_pct": float(progress.get("progress_pct", 0) or 0),
            "message": terminal_message,
            "result": svc._result,
            "orphaned": False,
            "adaptive_intelligence": _ai(),
        }
        if terminal_status == "error":
            payload["error"] = terminal_message
        if thread_still and progress.get("user_initiated_stop") is True:
            payload["status"] = "stopping"
            payload["message"] = str(
                progress.get("message")
                or "Birth Phase stop aangevraagd — worker ronden af…"
            )
        return _enricher.enrich_birth_status(svc, payload)

    if svc.is_running() or _m().progress_indicates_running(svc, progress):
        # Never sanitize away an explicit operator stop.
        if progress.get("user_initiated_stop") is not True:
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
        # Cooperative stop in flight but progress not yet marked — still report stopping.
        if hasattr(svc, "is_stopping") and svc.is_stopping():
            return _enricher.enrich_birth_status(
                svc,
                {
                    **base_meta,
                    "status": "stopping",
                    "runner": "thread",
                    "elapsed_seconds": round(time.time() - svc._start_time, 1)
                    if svc._start_time
                    else 0,
                    "message": "Birth Phase stop aangevraagd…",
                    "orphaned": False,
                    "adaptive_intelligence": _ai(),
                },
            )
        return _enricher.enrich_birth_status(
            svc,
            {
                **base_meta,
                "status": "running",
                "runner": "thread",
                "elapsed_seconds": round(time.time() - svc._start_time, 1) if svc._start_time else 0,
                "message": str(progress.get("message") or "Birth Phase draait..."),
                "orphaned": False,
                "adaptive_intelligence": _ai(),
            },
        )

    if _m().progress_indicates_running(svc, progress):
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
                "elapsed_seconds": _m().resolve_elapsed_seconds_from_progress(progress),
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

    terminal = _m().resolve_terminal_birth_status(progress)
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
