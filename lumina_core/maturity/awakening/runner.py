"""Living Awakening runner — skill clock, stall→retry, Twin-watch, Birth freeze."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.awakening.clock import (
    MAX_CYCLES,
    MAX_STALL_RETRIES,
    clock_keeps_running,
)
from lumina_core.maturity.awakening.law import evaluate_awakening_exit, snapshot_from_workspace
from lumina_core.maturity.awakening.progress import load_awakening_progress, merge_awakening_progress
from lumina_core.maturity.awakening.recovery import (
    is_stall,
    occupancy_crashed,
    recovery_proven,
    should_stop_retries,
)
from lumina_core.maturity.awakening.regime import attempt_regime_slices
from lumina_core.maturity.awakening.select import AwakeningShotError, run_select_cycle
from lumina_core.maturity.awakening.twin_watch import append_watch, twin_watch_cycle, watch_count
from lumina_core.maturity.continuum import mark_phase_failed, mark_phase_running
from lumina_core.maturity.maturation_progress import record_maturation_milestone
from lumina_core.maturity.phase_runners.awakening_shot import (
    live_ledger_path,
    snapshot_birth_freeze,
)
from lumina_core.maturity.phase_runners.common import finish_from_exit_eval, write_phase_progress

logger = get_logger("lumina.maturity.awakening.runner")

StopFn = Callable[[], bool]
ProgressFn = Callable[[float, str], None]


def run_awakening_live(
    workspace_root: Path | str,
    *,
    should_stop: StopFn | None = None,
    max_cycles: int = MAX_CYCLES,
    max_stall_retries: int = MAX_STALL_RETRIES,
    train_fn: Callable[..., dict[str, Any]] | None = None,
    eval_fn: Callable[..., dict[str, Any]] | None = None,
    split_loader: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    root = Path(workspace_root)
    mark_phase_running(root, "awakening", learned={"status": "living_clock"})
    write_phase_progress(root, "awakening", progress_pct=5.0, message="Syncing birth → maturity")
    try:
        from lumina_core.maturity.maturation_progress import sync_maturation_from_birth_state

        sync_maturation_from_birth_state(root)
        freeze = snapshot_birth_freeze(root)
        already, _, learned = evaluate_awakening_exit(root)
        stored_fp = load_awakening_progress(root).get("freeze_fingerprint")
        if already and stored_fp == freeze:
            from lumina_core.maturity.phase_runners.awakening_shot import assert_birth_freeze

            assert_birth_freeze(root, freeze)
            write_phase_progress(root, "awakening", progress_pct=100.0, message="Awakening law already passed")
            return finish_from_exit_eval(root, "awakening", default_proofs=list(learned.get("exit_proofs") or []))
        cycle = 0
        stall_retries = 0
        prev_n_b = -1
        last_error: str | None = None
        discarded = False
        if split_loader is None:
            write_phase_progress(
                root,
                "awakening",
                progress_pct=10.0,
                message="Preparing eyes-open exam (Birth B, continue later OOS if B cannot carry n_B≥500)",
            )
            try:
                from lumina_core.maturity.awakening.exam_tape import load_awakening_exam_split

                _, exam, exam_meta = load_awakening_exam_split(root)
                merge_awakening_progress(
                    root,
                    {
                        "exam_kind": exam_meta.get("exam_kind"),
                        "exam_n": len(exam),
                        "exam_extended": bool(exam_meta.get("exam_extended")),
                    },
                )
            except Exception:
                logger.warning("awakening.exam_prepare_failed", exc_info=True)
        write_phase_progress(
            root,
            "awakening",
            progress_pct=12.0,
            message="Cycle 0 — eval frozen π* on exam (no learn)",
        )
        try:
            shot = run_select_cycle(
                root,
                cycle=0,
                eval_only=True,
                progress=lambda p, m: write_phase_progress(root, "awakening", progress_pct=p, message=m),
                train_fn=train_fn,
                eval_fn=eval_fn,
                split_loader=split_loader,
            )
            last_error = None
            prev_n_b = int(shot.get("policy_trades") or 0)
            from lumina_core.maturity.phase_runners.awakening_shot import assert_birth_freeze

            assert_birth_freeze(root, freeze)
            merge_awakening_progress(root, {"freeze_ok": True, "freeze_fingerprint": freeze})
            _watch_cycle(root, shot=shot, n_b=prev_n_b)
            _persist_regime_and_recovery(root, stall_retries=0, freeze_ok=True, cycles_completed=0)
        except AwakeningShotError as exc:
            logger.warning("awakening.parent_eval_fail_closed err=%s", exc)
            last_error = str(exc)
            shot = {"error": str(exc), "ok": False, "holdout_trades": 0}

        while last_error is None:
            if should_stop is not None and should_stop():
                last_error = "stop_requested"
                break
            snap = snapshot_from_workspace(root)
            law_now, _, _ = evaluate_awakening_exit(root)
            if cycle > 0 and not clock_keeps_running(
                snap,
                cycle=cycle,
                max_cycles=max_cycles,
                stall_retries=stall_retries,
                max_stall_retries=max_stall_retries,
                passed=law_now,
            ):
                merge_awakening_progress(
                    root,
                    {
                        "cycle_budget_exhausted": True,
                        "clock_stop_cycle": int(cycle),
                    },
                )
                break
            if law_now:
                break
            cycle += 1
            pct = min(85.0, 10.0 + (70.0 * cycle / max(1, max_cycles)))
            write_phase_progress(
                root,
                "awakening",
                progress_pct=pct,
                message=f"Awakening cycle {cycle}/{max_cycles} — train A, eval B",
            )
            shot_error = False
            try:
                shot = run_select_cycle(
                    root,
                    cycle=cycle,
                    lr_scale=0.25 if discarded else 1.0,
                    progress=lambda p, m: write_phase_progress(root, "awakening", progress_pct=p, message=m),
                    train_fn=train_fn,
                    eval_fn=eval_fn,
                    split_loader=split_loader,
                )
                last_error = None
                discarded = load_awakening_progress(root).get("kept") is False
            except AwakeningShotError as exc:
                logger.warning("awakening.cycle_fail_closed cycle=%s err=%s", cycle, exc)
                shot_error = True
                last_error = str(exc)
                discarded = True
                shot = {"error": str(exc), "ok": False, "holdout_trades": prev_n_b if prev_n_b > 0 else 0}
            from lumina_core.maturity.phase_runners.awakening_shot import assert_birth_freeze

            assert_birth_freeze(root, freeze)
            merge_awakening_progress(
                root,
                {"freeze_ok": True, "freeze_fingerprint": freeze},
            )
            n_b = int(shot.get("policy_trades") or 0)
            if shot.get("policy_only") is True and n_b <= 0:
                n_b = int(shot.get("holdout_trades") or 0)
            occ = shot.get("occupancy")
            stalled = is_stall(
                prev_n_b=prev_n_b,
                n_b=n_b,
                shot_error=shot_error,
                occupancy_crash=occupancy_crashed(_f(occ)),
                tape_exhausted=bool(shot.get("holdout_exhausted")),
            )
            if stalled:
                stall_retries += 1
                append_watch(
                    root,
                    kind="recovery",
                    note=f"stall cycle={cycle} n_B={n_b} retries={stall_retries}",
                )
            _watch_cycle(root, shot=shot, n_b=n_b)
            _persist_regime_and_recovery(
                root,
                stall_retries=stall_retries,
                freeze_ok=True,
                cycles_completed=cycle,
            )
            prev_n_b = n_b
            law_ok, _, _ = evaluate_awakening_exit(root)
            if law_ok:
                break
            if should_stop_retries(stall_retries, max_retries=max_stall_retries):
                break

        law_ok, law_missing, law_learned = evaluate_awakening_exit(root)
        if not law_ok:
            write_phase_progress(
                root,
                "awakening",
                progress_pct=90.0,
                message=(f"Cycle {cycle}/{max_cycles} · incumbent kept · AND missing: " + ",".join(law_missing[:6])),
            )
        else:
            write_phase_progress(root, "awakening", progress_pct=90.0, message="Evaluating ADR-0049 AND")
        if law_ok:
            record_maturation_milestone(root, "evolution_proof_passed", metadata=law_learned)
            try:
                from lumina_core.maturity.milestone_hooks import hook_evolution_proof_passed

                lift_raw = law_learned.get("lift")
                hook_evolution_proof_passed(
                    root,
                    oos_winrate=float(law_learned.get("wr") or 0.0),
                    lift=float(lift_raw) if lift_raw is not None else None,
                )
            except Exception:
                logger.warning("awakening.evolution_proof_hook_failed", exc_info=True)
        write_phase_progress(
            root,
            "awakening",
            progress_pct=92.0,
            message="Evaluating exit proofs",
            learned={
                "cycles": cycle,
                "stall_retries": stall_retries,
                "twin_watch_n": watch_count(root),
                "twin_dump_is_not_proof": True,
                "last_error": last_error,
                **law_learned,
                "law_missing": law_missing,
            },
        )
        result = finish_from_exit_eval(
            root,
            "awakening",
            default_proofs=["evolution_proof_passed", "twin_watch"],
        )
        if result.get("ok"):
            write_phase_progress(root, "awakening", progress_pct=100.0, message="Awakening complete")
        return result
    except Exception as exc:
        logger.exception("awakening.failed")
        mark_phase_failed(root, "awakening", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _watch_cycle(root: Path, *, shot: dict[str, Any], n_b: int) -> None:
    wr = shot.get("polish_oos_winrate")
    birth = shot.get("birth_exit_winrate")
    lift = None
    if wr is not None and birth is not None:
        lift = float(wr) - float(birth)
    extra = {"n_b": n_b, "wr": wr, "birth_oos_wr": birth}
    note = f"n_B={n_b} lift={lift}"
    append_watch(root, kind="prefer_better", note=note, extra=extra, source="runner")
    twin_watch_cycle(root, kind="prefer_better", note=note, extra=extra)


def _persist_regime_and_recovery(
    root: Path,
    *,
    stall_retries: int,
    freeze_ok: bool,
    cycles_completed: int,
) -> None:
    rows: list[dict[str, Any]] = []
    ledger = live_ledger_path(root)
    if ledger.is_file():
        try:
            import json

            for line in ledger.read_text(encoding="utf-8").splitlines():
                raw = line.strip()
                if not raw:
                    continue
                row = json.loads(raw)
                if isinstance(row, dict):
                    rows.append(row)
        except (OSError, ValueError):
            rows = []
    vis = attempt_regime_slices(rows)
    note = " ".join(f"{k}={vis['status'][k]}" for k in vis["slices"])
    extra = {"counts": vis["counts"], "observed": vis["observed"]}
    append_watch(root, kind="regime", note=note, extra=extra, source="runner")
    twin_watch_cycle(root, kind="regime", note=note, extra=extra)
    merge_awakening_progress(
        root,
        {
            "regime_slices": vis["slices"],
            "regime_status": vis["status"],
            "regime_observed": list(vis["observed"]),
            "recovery_ok": recovery_proven(
                stall_retries=stall_retries,
                freeze_ok=freeze_ok,
                cycles_completed=cycles_completed,
            ),
            "stall_retries": int(stall_retries),
        },
    )


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
