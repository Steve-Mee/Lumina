"""Living Playground runner — SIM crawl clock, heartbeat, no learn(), no deck stamp."""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import mark_phase_failed, mark_phase_running
from lumina_core.maturity.phase_runners.awakening_shot import (
    AwakeningShotError,
    assert_birth_freeze,
    snapshot_birth_freeze,
)
from lumina_core.maturity.phase_runners.common import finish_from_exit_eval, write_phase_progress
from lumina_core.maturity.playground.clock import clock_keeps_running
from lumina_core.maturity.playground.envelope import envelope_sealed_for_pass
from lumina_core.maturity.playground.habitat import habitat_snapshot
from lumina_core.maturity.playground.law import evaluate_playground_exit
from lumina_core.maturity.playground.progress import merge_playground_progress
from lumina_core.maturity.playground.recovery import (
    MAX_STALL_RETRIES,
    is_stall,
    occupancy_crashed,
    recovery_proven,
    should_stop_retries,
)
from lumina_core.maturity.playground.select import load_policy_identities

logger = get_logger("lumina.maturity.playground.runner")

StopFn = Callable[[], bool]


def run_playground_live(
    workspace_root: Path | str,
    *,
    should_stop: StopFn | None = None,
    poll_sec: float = 2.0,
    max_stall_retries: int = MAX_STALL_RETRIES,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    root = Path(workspace_root).resolve()
    mark_phase_running(root, "playground", learned={"status": "living_clock"})
    write_phase_progress(root, "playground", progress_pct=5.0, message="Opening Playground clock")
    sleeper = sleep_fn or time.sleep
    freeze = snapshot_birth_freeze(root)
    try:
        _seed_progress(root, freeze=freeze)
        ok, missing, learned = evaluate_playground_exit(root)
        if ok:
            return _complete(root, learned)
        stall_retries = 0
        prev_n_p = int(learned.get("n_p") or 0)
        cycles = 0
        last_error: str | None = None
        while clock_keeps_running(
            passed=False,
            stall_retries=stall_retries,
            max_stall_retries=max_stall_retries,
        ):
            if should_stop is not None and should_stop():
                last_error = "stop_requested"
                break
            try:
                assert_birth_freeze(root, freeze)
            except AwakeningShotError as exc:
                last_error = str(exc)
                merge_playground_progress(root, {"freeze_ok": False})
                break
            _seed_progress(root, freeze=freeze)
            hab = habitat_snapshot(root)
            if hab.get("mode") == "real":
                last_error = "mode_not_sim=real"
                break
            merge_playground_progress(
                root,
                {
                    "activity": "session_watch",
                    "recovery_ok": recovery_proven(
                        freeze_ok=True,
                        cycles_completed=max(1, cycles),
                        stall_retries=stall_retries,
                    ),
                },
            )
            ok, missing, learned = evaluate_playground_exit(root)
            n_p = int(learned.get("n_p") or 0)
            write_phase_progress(
                root,
                "playground",
                progress_pct=min(95.0, 10.0 + float(n_p) * 0.5),
                message=f"Crawling · n_P {n_p}/150",
                learned=learned,
            )
            merge_playground_progress(root, {"activity": "session_watch", "n_p": n_p})
            if ok:
                return _complete(root, learned)
            crash = occupancy_crashed(learned.get("occupancy") if learned else None)
            waiting = bool(hab.get("waiting_operator"))
            if is_stall(
                prev_n_p=prev_n_p,
                n_p=n_p,
                occupancy_crash=crash,
                habitat_error=bool(hab.get("habitat_error")),
                waiting_operator=waiting,
            ) and cycles > 0:
                stall_retries += 1
                last_error = "stall"
                if should_stop_retries(stall_retries, max_retries=max_stall_retries):
                    last_error = "stall_retries_exhausted"
                    break
            prev_n_p = n_p
            cycles += 1
            sleeper(max(0.0, float(poll_sec)))
        sealed = envelope_sealed_for_pass(root)
        write_phase_progress(
            root,
            "playground",
            message="Clock halted — fail-closed, Birth + Awakening intact",
            learned={"status": "incomplete", "stop_reason": last_error, "missing": missing},
        )
        next_step = "Open Command Deck and crawl in NT SIM (JSON stamps do not count)"
        if not sealed:
            next_step = "Seal the SIM risk envelope (PlaygroundEnvelopeSeal UI)"
        if last_error == "mode_not_sim=real":
            next_step = "Playground is SIM only. REAL is locked."
        return {
            "ok": False,
            "status": "incomplete",
            "phase": "playground",
            "missing": missing,
            "learned": learned,
            "stop_reason": last_error,
            "next_step": next_step,
        }
    except Exception as exc:
        logger.exception("playground.live_failed")
        mark_phase_failed(root, "playground", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _complete(root: Path, learned: dict[str, Any]) -> dict[str, Any]:
    result = finish_from_exit_eval(
        root,
        "playground",
        default_proofs=list(learned.get("exit_proofs") or []),
    )
    if result.get("ok"):
        write_phase_progress(root, "playground", progress_pct=100.0, message="Playground complete")
    return result


def _seed_progress(root: Path, *, freeze: dict[str, str]) -> None:
    ids = load_policy_identities(root)
    hab = habitat_snapshot(root)
    patch: dict[str, Any] = {
        "freeze_ok": bool(ids.get("freeze_ok")),
        "freeze_fingerprint": freeze,
        "child_sha": ids.get("child_sha") or "",
        "awakening_child_sha": ids.get("awakening_child_sha") or "",
        "birth_sha": ids.get("birth_sha") or "",
        "mode": hab.get("mode") or "",
        "envelope_breached": bool(hab.get("envelope_breached")),
        "note": "Playground AND: crawl in NT SIM. JSON first-order and Birth fitness are not pass.",
    }
    if hab.get("occupancy") is not None:
        patch["occupancy"] = hab.get("occupancy")
    if hab.get("breakeven_wr") is not None:
        patch["breakeven_wr"] = hab.get("breakeven_wr")
    merge_playground_progress(root, patch)
