"""Living Proving Ground runner — exam clock, heartbeat, never-stop. No audit-scan pass."""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import mark_phase_failed, mark_phase_running
from lumina_core.maturity.phase_runners.common import finish_from_exit_eval, write_phase_progress
from lumina_core.maturity.proving_ground.law import evaluate_proving_ground_exit
from lumina_core.maturity.proving_ground.progress import merge_proving_ground_progress
from lumina_core.maturity.proving_ground.recovery import (
    MAX_STALL_RETRIES,
    is_stall,
    occupancy_crashed,
    recovery_proven,
    should_stop_retries,
)

logger = get_logger("lumina.maturity.proving_ground.runner")

StopFn = Callable[[], bool]


def run_proving_ground_live(
    workspace_root: Path | str,
    *,
    should_stop: StopFn | None = None,
    poll_sec: float = 2.0,
    max_stall_retries: int = MAX_STALL_RETRIES,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    root = Path(workspace_root).resolve()
    mark_phase_running(root, "proving_ground", learned={"status": "living_clock"})
    write_phase_progress(
        root, "proving_ground", progress_pct=5.0, message="Opening proving-ground clock"
    )
    sleeper = sleep_fn or time.sleep
    try:
        _seed_progress(root)
        ok, missing, learned = evaluate_proving_ground_exit(root)
        if ok:
            return _complete(root, learned)
        stall_retries = 0
        prev_n_g = int(learned.get("n_g") or 0)
        cycles = 0
        last_error: str | None = None
        while True:
            if should_stop is not None and should_stop():
                last_error = "stop_requested"
                break
            _seed_progress(root)
            seeded = merge_proving_ground_progress(root, {})
            merge_proving_ground_progress(
                root,
                {
                    "activity": "exam_watch",
                    "recovery_ok": recovery_proven(
                        freeze_ok=bool(seeded.get("freeze_ok")),
                        cycles_completed=max(1, cycles),
                        stall_retries=stall_retries,
                    ),
                },
            )
            ok, missing, learned = evaluate_proving_ground_exit(root)
            n_g = int(learned.get("n_g") or 0)
            write_phase_progress(
                root,
                "proving_ground",
                progress_pct=min(95.0, 10.0 + float(n_g) * 0.4),
                message=f"Exam · n_G {n_g} · gate {int(learned.get('promotion_criteria_passed') or 0)}/4",
                learned=learned,
            )
            merge_proving_ground_progress(
                root,
                {
                    "activity": "exam_watch",
                    "n_g": n_g,
                    "oos_wr": learned.get("oos_wr"),
                    "oos_sharpe": learned.get("oos_sharpe"),
                    "dd_pct": learned.get("dd_pct"),
                },
            )
            if ok:
                return _complete(root, learned)
            crash = occupancy_crashed(learned.get("occupancy"))
            if is_stall(prev_n_g=prev_n_g, n_g=n_g, occupancy_crash=crash) and cycles > 0:
                stall_retries += 1
                last_error = "stall"
                if should_stop_retries(stall_retries, max_retries=max_stall_retries):
                    last_error = "stall_retries_exhausted"
                    break
            prev_n_g = n_g
            cycles += 1
            sleeper(max(0.0, float(poll_sec)))
        write_phase_progress(
            root,
            "proving_ground",
            message="Clock halted — fail-closed, earlier ladder intact",
            learned={"status": "incomplete", "stop_reason": last_error, "missing": missing},
        )
        return {
            "ok": False,
            "status": "incomplete",
            "phase": "proving_ground",
            "missing": missing,
            "learned": learned,
            "stop_reason": last_error,
            "next_step": (
                "Need proving-ground tape n_G≥150, cert OOS 48%/0.35/8%, "
                "this-run shadow, and PromotionGate 4/4. Audit scans and Birth JSON do not count."
            ),
        }
    except Exception as exc:
        logger.exception("proving_ground.live_failed")
        mark_phase_failed(root, "proving_ground", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _complete(root: Path, learned: dict[str, Any]) -> dict[str, Any]:
    try:
        from lumina_core.maturity.milestone_hooks import (
            hook_promotion_gate_passed,
            hook_shadow_validation_passed,
        )

        sha = str(learned.get("child_sha") or "")
        hook_shadow_validation_passed(root, shadow_status="passed", dna_hash=sha)
        hook_promotion_gate_passed(root, mode="sim", dna_hash=sha)
    except Exception:
        logger.debug("proving_ground.milestone_hook_failed", exc_info=True)
    result = finish_from_exit_eval(
        root,
        "proving_ground",
        default_proofs=list(learned.get("exit_proofs") or []),
    )
    if result.get("ok"):
        write_phase_progress(root, "proving_ground", progress_pct=100.0, message="Proving Ground complete")
    return result


def _seed_progress(root: Path) -> None:
    from lumina_core.maturity.apprenticeship.progress import load_apprenticeship_progress
    from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

    ap = load_apprenticeship_progress(root)
    child = str(ap.get("child_sha") or "")
    birth = str(ap.get("birth_sha") or "")
    merge_proving_ground_progress(
        root,
        {
            "freeze_ok": bool(is_birth_exit_sufficient(root)),
            "child_sha": child,
            "apprenticeship_child_sha": child,
            "birth_sha": birth,
            "mode": str(ap.get("mode") or "sim_real_guard") or "sim_real_guard",
            "deck_live": True,
            "note": "Proving Ground AND: cert exam + shadow + PromotionGate (ADR-0052).",
        },
    )
