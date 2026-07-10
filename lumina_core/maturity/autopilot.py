"""Maturation autopilot — post-birth autonomous path to REAL-ready notification."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.maturation_progress import (
    REAL_ELIGIBILITY_MILESTONES,
    load_maturation_progress,
    maturation_eligible_for_real,
    record_maturation_milestone,
    sync_maturation_from_birth_state,
)

logger = get_logger("lumina.maturity.autopilot")

_AUTOPILOT_THREAD: threading.Thread | None = None
_AUTOPILOT_STOP = threading.Event()
_AUTOPILOT_INTERVAL_SEC = 300.0


def _workspace_root() -> Path:
    return Path.cwd()


def _shadow_gate_passed_from_audit(workspace_root: Path) -> tuple[bool, dict[str, Any]]:
    audit_path = workspace_root / "state" / "promotion_gate_audit.jsonl"
    if not audit_path.is_file():
        return False, {}
    try:
        lines = [ln.strip() for ln in audit_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for line in reversed(lines[-50:]):
            import json

            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            promoted = bool(row.get("promoted") or row.get("passed") or row.get("shadow_passed"))
            if promoted:
                return True, row
    except Exception as exc:
        logger.debug("maturity.autopilot.audit_read_failed: %s", exc)
    return False, {}


def _run_shadow_promotion_gate(workspace_root: Path) -> bool:
    try:
        passed, metadata = _shadow_gate_passed_from_audit(workspace_root)
        if passed:
            from lumina_core.maturity.milestone_hooks import hook_promotion_gate_passed

            hook_promotion_gate_passed(
                workspace_root,
                mode=str(metadata.get("mode", "") or ""),
                dna_hash=str(metadata.get("dna_hash", "") or ""),
            )
        return passed
    except Exception as exc:
        logger.debug("maturity.autopilot.shadow_failed: %s", exc)
        return False


def _sync_playground_milestones(workspace_root: Path) -> None:
    sync_maturation_from_birth_state(workspace_root)
    progress = load_maturation_progress(workspace_root)
    if "deck_unlocked" not in progress.milestones_reached:
        record_maturation_milestone(workspace_root, "deck_unlocked")


def _maybe_notify_real_ready(workspace_root: Path) -> None:
    eligible, blockers = maturation_eligible_for_real(workspace_root)
    if not eligible:
        return
    progress = load_maturation_progress(workspace_root)
    if "real_ready_notified" in progress.metadata:
        return
    try:
        from lumina_core.notifications.maturation_events import maturation_milestone_event
        from lumina_core.notifications.attention_notifier import notify_attention

        notify_attention(
            maturation_milestone_event(
                milestone_id="real_ready",
                metadata={"phase": "proving_ground"},
            ),
            workspace_root=workspace_root,
        )
        progress.metadata["real_ready_notified"] = True
        from lumina_core.maturity.maturation_progress import save_maturation_progress

        save_maturation_progress(workspace_root, progress)
    except Exception as exc:
        logger.warning("maturity.autopilot.notify_failed: %s", exc)


def run_maturation_autopilot_tick(workspace_root: Path | str | None = None) -> dict[str, Any]:
    """Single autopilot cycle: sync milestones, stability, shadow gate."""
    root = Path(workspace_root or _workspace_root())
    _sync_playground_milestones(root)
    try:
        from lumina_core.maturity.maturation_progress import sync_stability_milestone

        sync_stability_milestone(root)
    except Exception as exc:
        logger.debug("maturity.autopilot.stability_sync_failed: %s", exc)

    progress = load_maturation_progress(root)
    reached = set(progress.milestones_reached)
    shadow_ok = "promotion_gate_passed" in reached
    if "sim_real_guard_stable" in reached and not shadow_ok:
        shadow_ok = _run_shadow_promotion_gate(root)

    eligible, blockers = maturation_eligible_for_real(root)
    if eligible:
        _maybe_notify_real_ready(root)

    return {
        "milestones_reached": list(progress.milestones_reached),
        "real_eligible": eligible,
        "blockers": blockers,
        "shadow_gate_passed": shadow_ok,
        "required": list(REAL_ELIGIBILITY_MILESTONES),
    }


def _autopilot_loop(workspace_root: Path) -> None:
    while not _AUTOPILOT_STOP.wait(_AUTOPILOT_INTERVAL_SEC):
        try:
            from lumina_launcher.services.birth_service import BirthService

            svc = BirthService()
            svc.configure_workspace(workspace_root)
            if not svc.artifacts_ok():
                continue
            tick = run_maturation_autopilot_tick(workspace_root)
            logger.info(
                "maturity.autopilot.tick eligible=%s shadow=%s",
                tick.get("real_eligible"),
                tick.get("shadow_gate_passed"),
            )
        except Exception as exc:
            logger.warning("maturity.autopilot.loop_error: %s", exc)


def start_maturation_autopilot(workspace_root: Path | str | None = None) -> None:
    """Start background maturation autopilot daemon (idempotent)."""
    global _AUTOPILOT_THREAD
    if _AUTOPILOT_THREAD is not None and _AUTOPILOT_THREAD.is_alive():
        return
    root = Path(workspace_root or _workspace_root())
    _AUTOPILOT_STOP.clear()
    _AUTOPILOT_THREAD = threading.Thread(
        target=_autopilot_loop,
        args=(root,),
        daemon=True,
        name="LuminaMaturationAutopilot",
    )
    _AUTOPILOT_THREAD.start()
    logger.info("maturity.autopilot.started workspace=%s", root)


def stop_maturation_autopilot() -> None:
    _AUTOPILOT_STOP.set()