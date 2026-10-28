"""Living Awakening runner — skill clock, stall→retry, Twin-watch, Birth freeze."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.awakening.clock import (
    MAX_CYCLES,
    MAX_STALL_RETRIES,
)
from lumina_core.maturity.awakening.cycle_journal import append_cycle, new_run_id
from lumina_core.maturity.awakening.cycle_report import cycle_notice, exam_failure_note, phase_exit_journal
from lumina_core.maturity.awakening.law import evaluate_awakening_exit
from lumina_core.maturity.awakening.progress import load_awakening_progress, merge_awakening_progress
from lumina_core.maturity.awakening.recovery import recovery_proven
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
from lumina_core.notifications.phase_status_notify import notify_phase_status

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
    merge_awakening_progress(
        root,
        {"run_id": new_run_id(), "eval_only": True, "activity": "eval_B"},
    )
    del max_cycles, max_stall_retries
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
            write_phase_progress(
                root,
                "awakening",
                progress_pct=100.0,
                message="Awakening law already passed",
                telegram=False,
            )
            result = finish_from_exit_eval(
                root, "awakening", default_proofs=list(learned.get("exit_proofs") or [])
            )
            _journal_phase_exit(root, result, note="Awakening law already passed.")
            return result
        cycle = 0
        stall_retries = 0
        prev_n_b = -1
        last_error: str | None = None
        write_phase_progress(
            root,
            "awakening",
            progress_pct=12.0,
            message="First Watch — eval frozen plant on holdout B (no learn)",
        )
        if should_stop is not None and should_stop():
            last_error = "stop_requested"
            shot = {"ok": False, "holdout_trades": 0}
        else:
            try:
                shot = run_select_cycle(
                    root,
                    cycle=0,
                    eval_only=True,
                    progress=lambda p, m: write_phase_progress(root, "awakening", progress_pct=p, message=m),
                    train_fn=train_fn,
                    eval_fn=eval_fn,
                    split_loader=split_loader,
                    should_stop=should_stop,
                )
                last_error = None
                prev_n_b = int(shot.get("policy_trades") or 0)
                from lumina_core.maturity.phase_runners.awakening_shot import assert_birth_freeze

                assert_birth_freeze(root, freeze)
                merge_awakening_progress(root, {"freeze_ok": True, "freeze_fingerprint": freeze})
                _watch_cycle(root, shot=shot, n_b=prev_n_b)
                watched = 1 if prev_n_b >= 500 else 0
                _persist_regime_and_recovery(
                    root, stall_retries=0, freeze_ok=True, cycles_completed=watched
                )
                _notify_measured_shot(root, 0, shot)
            except AwakeningShotError as exc:
                logger.warning("awakening.parent_eval_fail_closed err=%s", exc)
                last_error = str(exc)
                shot = {"error": str(exc), "ok": False, "holdout_trades": 0}
                last_error = _clear_freeze_error_if_pin_intact(root, last_error)
                if last_error is None:
                    from lumina_core.maturity.phase_runners.awakening_shot import assert_birth_freeze

                    try:
                        assert_birth_freeze(root, freeze)
                        merge_awakening_progress(root, {"freeze_ok": True, "freeze_fingerprint": freeze})
                    except AwakeningShotError as pin_exc:
                        last_error = str(pin_exc)
                _notify_measured_shot(root, 0, shot)

        if last_error and "stop_requested" in str(last_error):
            from lumina_core.maturity.continuum import mark_phase_stopped

            message = "Stopped — Birth plant intact. Freeze held."
            write_phase_progress(root, "awakening", progress_pct=90.0, message=message, telegram=False)
            mark_phase_stopped(root, "awakening", message=message)
            merge_awakening_progress(root, {"activity": "stopped"})
            return {"ok": False, "stopped": True, "phase": "awakening"}

        law_ok, law_missing, law_learned = evaluate_awakening_exit(root)
        if not law_ok:
            write_phase_progress(
                root,
                "awakening",
                progress_pct=90.0,
                message=("First Watch · AND missing: " + ",".join(law_missing[:6])),
                telegram=False,
            )
        else:
            write_phase_progress(
                root,
                "awakening",
                progress_pct=90.0,
                message="Evaluating First Watch",
                telegram=False,
            )
        if law_ok:
            from lumina_core.maturity.awakening.baseline import seal_first_watch

            seal_first_watch(root)
            record_maturation_milestone(root, "first_watch_passed", metadata=law_learned)
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
            telegram=False,
        )
        failure_note = exam_failure_note(root)
        result = finish_from_exit_eval(
            root,
            "awakening",
            default_proofs=list(law_learned.get("exit_proofs") or []),
            failure_message=None if law_ok else failure_note,
        )
        exit_note = "Awakening law passed." if result.get("ok") else failure_note
        _journal_phase_exit(root, result, note=exit_note)
        if result.get("ok"):
            write_phase_progress(root, "awakening", progress_pct=100.0, message="Awakening complete", telegram=False)
        return result
    except Exception as exc:
        logger.exception("awakening.failed")
        _journal_phase_exit(root, {"ok": False, "missing": []}, note=f"runner_exception: {exc}")
        mark_phase_failed(root, "awakening", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _journal_phase_exit(root: Path, result: dict[str, Any], *, note: str) -> None:
    """Durable phase-end row. A wipe of Awakening does not delete the journal."""
    try:
        missing = result.get("missing")
        blockers = [str(item) for item in missing] if isinstance(missing, list) else []
        append_cycle(
            root,
            phase_exit_journal(root, passed=bool(result.get("ok")), missing=blockers, note=note),
        )
    except Exception:
        logger.warning("awakening.phase_exit_journal_failed", exc_info=True)


def _notify_measured_shot(root: Path, cycle: int, shot: dict[str, Any]) -> None:
    """Journal every cycle, then Telegram the AND. Evolution-proof success is not 'missing'."""
    notice = cycle_notice(root, cycle, shot)
    try:
        append_cycle(root, notice["journal"])
    except Exception:
        logger.warning("awakening.cycle_journal_failed cycle=%s", cycle, exc_info=True)
    try:
        notify_phase_status(
            root,
            "awakening",
            kind="progress",
            message=str(notice["message"]),
            learned=notice["learned"],
            missing=list(notice["missing"]),
            error=notice["error"],
        )
    except Exception:
        logger.warning("awakening.shot_telegram_failed cycle=%s", cycle, exc_info=True)


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


def _clear_freeze_error_if_pin_intact(root: Path, last_error: str | None) -> str | None:
    """Git-harvest vs pin restore is not a dead clock when the Birth pin holds."""
    if not last_error or "birth_freeze_violated" not in str(last_error):
        return last_error
    from lumina_core.maturity.awakening.freeze_pin import (
        align_live_pi_star_to_pin,
        live_matches_pin,
    )

    align_live_pi_star_to_pin(root)
    if live_matches_pin(root):
        logger.warning("awakening.freeze.restored_to_pin clock_continues")
        return None
    return last_error
