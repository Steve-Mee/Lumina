"""Living Apprenticeship runner — session clock, heartbeat, never-stop. No backtest."""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.apprenticeship.law import evaluate_apprenticeship_exit
from lumina_core.maturity.apprenticeship.progress import merge_apprenticeship_progress
from lumina_core.maturity.apprenticeship.recovery import (
    MAX_STALL_RETRIES,
    is_stall,
    occupancy_crashed,
    recovery_proven,
    should_stop_retries,
)
from lumina_core.maturity.continuum import mark_phase_failed, mark_phase_running
from lumina_core.maturity.phase_runners.common import finish_from_exit_eval, write_phase_progress

logger = get_logger("lumina.maturity.apprenticeship.runner")

StopFn = Callable[[], bool]


def run_apprenticeship_live(
    workspace_root: Path | str,
    *,
    should_stop: StopFn | None = None,
    poll_sec: float = 2.0,
    max_stall_retries: int = MAX_STALL_RETRIES,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    root = Path(workspace_root).resolve()
    mark_phase_running(root, "apprenticeship", learned={"status": "living_clock"})
    write_phase_progress(
        root, "apprenticeship", progress_pct=5.0, message="Opening apprenticeship clock"
    )
    sleeper = sleep_fn or time.sleep
    try:
        _seed_progress(root)
        ok, missing, learned = evaluate_apprenticeship_exit(root)
        if ok:
            return _complete(root, learned)
        stall_retries = 0
        prev_n_a = int(learned.get("n_a") or 0)
        cycles = 0
        last_error: str | None = None
        while True:
            if should_stop is not None and should_stop():
                last_error = "stop_requested"
                break
            _seed_progress(root)
            seeded = merge_apprenticeship_progress(root, {})
            merge_apprenticeship_progress(
                root,
                {
                    "activity": "session_watch",
                    "recovery_ok": recovery_proven(
                        freeze_ok=bool(seeded.get("freeze_ok")),
                        cycles_completed=max(1, cycles),
                        stall_retries=stall_retries,
                    ),
                },
            )
            ok, missing, learned = evaluate_apprenticeship_exit(root)
            n_a = int(learned.get("n_a") or 0)
            n_d = int(learned.get("n_d") or 0)
            write_phase_progress(
                root,
                "apprenticeship",
                progress_pct=min(95.0, 10.0 + float(n_d) * 15.0),
                message=f"Walking · n_A {n_a} · green days {n_d}/5",
                learned=learned,
            )
            merge_apprenticeship_progress(
                root,
                {
                    "activity": "session_watch",
                    "n_a": n_a,
                    "n_d": n_d,
                    "sharpe": learned.get("sharpe"),
                    "dd_pct": learned.get("dd_pct"),
                },
            )
            if ok:
                return _complete(root, learned)
            crash = occupancy_crashed(learned.get("occupancy"))
            if is_stall(prev_n_a=prev_n_a, n_a=n_a, occupancy_crash=crash) and cycles > 0:
                stall_retries += 1
                last_error = "stall"
                if should_stop_retries(stall_retries, max_retries=max_stall_retries):
                    last_error = "stall_retries_exhausted"
                    break
            prev_n_a = n_a
            cycles += 1
            sleeper(max(0.0, float(poll_sec)))
        write_phase_progress(
            root,
            "apprenticeship",
            message="Clock halted — fail-closed, Birth + Playground intact",
            learned={"status": "incomplete", "stop_reason": last_error, "missing": missing},
        )
        return {
            "ok": False,
            "status": "incomplete",
            "phase": "apprenticeship",
            "missing": missing,
            "learned": learned,
            "stop_reason": last_error,
            "next_step": (
                "Need five consecutive NT SIM session days under sim_real_guard "
                "with Sharpe ≥ 0.20, DD ≤ 12%, n_A ≥ 150, constitution 0."
            ),
        }
    except Exception as exc:
        logger.exception("apprenticeship.live_failed")
        mark_phase_failed(root, "apprenticeship", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _complete(root: Path, learned: dict[str, Any]) -> dict[str, Any]:
    try:
        from lumina_core.maturity.milestone_hooks import hook_sim_real_guard_stable

        hook_sim_real_guard_stable(
            root,
            consecutive_green_days=int(learned.get("n_d") or 0),
            source="apprenticeship_law",
        )
    except Exception:
        logger.debug("apprenticeship.ready_hook_failed", exc_info=True)
    result = finish_from_exit_eval(
        root,
        "apprenticeship",
        default_proofs=list(learned.get("exit_proofs") or []),
    )
    if result.get("ok"):
        write_phase_progress(root, "apprenticeship", progress_pct=100.0, message="Apprenticeship complete")
    return result


def _seed_progress(root: Path) -> None:
    from lumina_core.maturity.birth_exit import is_birth_exit_sufficient
    from lumina_core.maturity.playground.progress import load_playground_progress

    pg = load_playground_progress(root)
    child = str(pg.get("child_sha") or "")
    birth = str(pg.get("birth_sha") or "")
    patch: dict[str, Any] = {
        "freeze_ok": bool(is_birth_exit_sufficient(root)),
        "child_sha": child,
        "playground_child_sha": child,
        "birth_sha": birth,
        "mode": "sim_real_guard",
        "deck_live": True,
        "note": "Apprenticeship AND: walk on NT SIM under sim_real_guard (ADR-0051).",
    }
    if pg.get("occupancy") is not None:
        patch["occupancy"] = pg.get("occupancy")
    merge_apprenticeship_progress(root, patch)
