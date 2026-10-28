"""Shared helpers for phase runners."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import (
    ContinuumUnreadable,
    load_continuum,
    mark_phase_completed,
    mark_phase_failed,
    save_continuum,
)
from lumina_core.maturity.maturity_config import MaturityConfig, load_maturity_config
from lumina_core.maturity.phase_specs import evaluate_exit_proofs
from lumina_core.notifications.phase_status_notify import notify_phase_status

logger = get_logger("lumina.maturity.phase_runners")


def cfg() -> MaturityConfig:
    return load_maturity_config()


def write_phase_progress(
    workspace_root: Path | str,
    phase: str,
    *,
    progress_pct: float | None = None,
    message: str | None = None,
    learned: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    telegram: bool = True,
) -> None:
    root = Path(workspace_root)
    try:
        data = load_continuum(root)
    except ContinuumUnreadable:
        logger.warning("phase_progress.continuum_unreadable phase=%s", phase)
        return
    rec = dict((data.get("phase_records") or {}).get(phase) or {})
    if progress_pct is not None:
        rec["progress_pct"] = max(0.0, min(100.0, float(progress_pct)))
    if message is not None:
        rec["message"] = str(message)[:500]
    if learned:
        rec["learned"] = {**(rec.get("learned") or {}), **learned}
    if extra:
        rec.update(extra)
    data.setdefault("phase_records", {})[phase] = rec
    save_continuum(root, data)
    if not telegram:
        return
    stored = rec.get("learned") if isinstance(rec.get("learned"), dict) else None
    try:
        notify_phase_status(
            root,
            phase,
            kind="progress",
            message=message,
            learned=stored,
        )
    except Exception as exc:
        logger.warning("phase_progress.telegram_failed phase=%s err=%s", phase, exc)


def finish_from_exit_eval(
    workspace_root: Path | str,
    phase: str,
    *,
    default_proofs: list[str] | None = None,
    failure_message: str | None = None,
) -> dict[str, Any]:
    """Evaluate hard proofs; complete or fail honestly.

    ``failure_message`` is an operator sentence for Awakening. The ``missing:``
    blockers stay on the error and under Ontbreekt. Other phases omit it.
    """
    root = Path(workspace_root)
    ok, missing, learned = evaluate_exit_proofs(root, phase)
    proofs = list(learned.get("exit_proofs") or default_proofs or [])
    if ok and phase == "awakening" and not proofs:
        ok = False
        missing = ["first_watch_proofs_missing"]
    if ok:
        if not proofs and not missing:
            proofs = default_proofs or [f"{phase}_passed"]
        mark_phase_completed(root, phase, learned=learned, exit_proofs=proofs)
        _notify_exit(root, phase, kind="passed", learned=_merged_learned(root, phase, learned), missing=[])
        return {"ok": True, "phase": phase, "learned": learned, "missing": []}
    err = f"missing:{','.join(missing)}"
    mark_phase_failed(
        root,
        phase,
        error=err,
        telegram=False,
        message=failure_message,
    )
    _notify_exit(
        root,
        phase,
        kind="failed",
        learned=_merged_learned(root, phase, learned),
        missing=list(missing),
        error=err,
        message=failure_message,
    )
    return {
        "ok": False,
        "phase": phase,
        "missing": missing,
        "learned": learned,
        "status": "incomplete",
    }


def notify_clock_halt(
    workspace_root: Path | str,
    phase: str,
    *,
    message: str,
    learned: dict[str, Any] | None = None,
    missing: list[str] | None = None,
    stop_reason: str | None = None,
    next_step: str | None = None,
) -> None:
    """Clock stopped short of the exit law. Not a pass."""
    try:
        notify_phase_status(
            workspace_root,
            phase,
            kind="incomplete",
            message=message,
            learned=learned,
            missing=list(missing or []),
            stop_reason=stop_reason,
            next_step=next_step,
        )
    except Exception as exc:
        logger.warning("phase_halt.telegram_failed phase=%s err=%s", phase, exc)


def _merged_learned(root: Path, phase: str, learned: dict[str, Any]) -> dict[str, Any]:
    data = load_continuum(root)
    records = data.get("phase_records")
    rec_raw = records.get(phase) if isinstance(records, dict) else None
    rec = rec_raw if isinstance(rec_raw, dict) else {}
    raw_learned = rec.get("learned")
    stored: dict[str, Any] = dict(raw_learned) if isinstance(raw_learned, dict) else {}
    return {**stored, **learned}


def _notify_exit(
    root: Path,
    phase: str,
    *,
    kind: str,
    learned: dict[str, Any],
    missing: list[str],
    error: str | None = None,
    message: str | None = None,
) -> None:
    try:
        notify_phase_status(
            root,
            phase,
            kind=kind,
            learned=learned,
            missing=missing,
            error=error,
            message=message,
        )
    except Exception as exc:
        logger.warning("phase_exit.telegram_failed phase=%s kind=%s err=%s", phase, kind, exc)
