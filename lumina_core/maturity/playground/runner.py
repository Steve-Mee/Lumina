"""Living Playground runner — SIM crawl clock, heartbeat, no learn(), no deck stamp.

A flat n_P on a 2s poll is not a stall. A stall is three 30-minute windows.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.market.archive_repair import repair_next_hole
from lumina_core.maturity.continuum import mark_phase_failed, mark_phase_running
from lumina_core.maturity.phase_runners.awakening_shot import (
    AwakeningShotError,
    assert_birth_freeze,
    snapshot_birth_freeze,
)
from lumina_core.maturity.phase_runners.common import finish_from_exit_eval, write_phase_progress
from lumina_core.maturity.playground.clock import clock_keeps_running
from lumina_core.maturity.playground.crawl import unfilled_edge_seq, watch_crawl
from lumina_core.maturity.playground.envelope import envelope_sealed_for_pass
from lumina_core.maturity.playground.habitat import habitat_snapshot
from lumina_core.maturity.playground.journal import append_heartbeat
from lumina_core.maturity.playground.law import evaluate_playground_exit
from lumina_core.maturity.playground.portfolio_seal import ensure_portfolio_seal
from lumina_core.maturity.playground.progress import load_playground_progress, merge_playground_progress
from lumina_core.maturity.playground.sense_audit import ensure_sense_audit
from lumina_core.maturity.playground.sense_clock import (
    playground_flat_line,
    recognize_existing_flat_book,
)
from lumina_core.maturity.playground.recovery import (
    WINDOW_SEC,
    ConclusiveState,
    StallState,
    active_fault,
    step_conclusive,
    step_stall,
)
from lumina_core.maturity.playground.select import load_policy_identities

logger = get_logger("lumina.maturity.playground.runner")

StopFn = Callable[[], bool]


def run_playground_live(
    workspace_root: Path | str,
    *,
    should_stop: StopFn | None = None,
    poll_sec: float = 2.0,
    stall_window_sec: float = WINDOW_SEC,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    root = Path(workspace_root).resolve()
    mark_phase_running(root, "playground", learned={"status": "living_clock"})
    write_phase_progress(root, "playground", progress_pct=5.0, message="Opening Playground clock")
    sleeper = sleep_fn or time.sleep
    freeze = snapshot_birth_freeze(root)
    missing: list[str] = []
    learned: dict[str, Any] = {}
    try:
        _seed_progress(root, freeze=freeze)
        try:
            ensure_sense_audit(root)
            from lumina_core.maturity.playground.globex_gap import note_globex_once, on_clock

            note_globex_once(root)
            on_clock(root)
            recognize_existing_flat_book(root)
        except Exception:
            logger.warning("playground.sense_audit_failed", exc_info=True)
        ok, missing, learned = evaluate_playground_exit(root)
        if ok:
            return _complete(root, learned)
        stall = _stall_from_progress(root)
        conclusive = _conclusive_from_progress(root)
        seen_seq = unfilled_edge_seq(root)
        last_sig = ""
        last_error: str | None = None
        while clock_keeps_running(passed=False, stall_windows=stall.windows):
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
            seal_note = _refresh_seal(root)
            hab = habitat_snapshot(root)
            if hab.get("mode") == "real":
                last_error = "mode_not_sim=real"
                break
            status, seen_seq = watch_crawl(root, seen_seq=seen_seq)
            try:
                from lumina_core.maturity.playground.globex_gap import on_clock
                from lumina_core.maturity.playground.research_kit import on_school_clock

                repair_next_hole(root)
                on_school_clock(root)
                on_clock(root)
                from lumina_core.maturity.playground.session_flat import note_stale_open_feed

                note_stale_open_feed(root)
            except Exception:
                logger.warning("playground.shadow_promote_failed", exc_info=True)
            ok, missing, learned = evaluate_playground_exit(root)
            n_p = int(learned.get("n_p") or 0)
            now = time.time()
            fault = active_fault(
                nt_health=str(hab.get("nt_health") or "unknown"),
                occupancy=_as_float(learned.get("occupancy")),
                total_bars=int(status.get("total_bars") or 0),
            )
            stepped = step_stall(
                stall,
                now=now,
                active=fault,
                unfilled_edge=bool(status.get("orders_unfilled")),
                frozen=bool(hab.get("waiting_operator")),
                window_sec=float(stall_window_sec),
            )
            stall = stepped.state
            conclusive, ask = step_conclusive(
                conclusive,
                now=now,
                n_p=n_p,
                blockers=missing,
                window_sec=float(stall_window_sec),
            )
            waiting = bool(hab.get("waiting_operator"))
            green_days = int(learned.get("green_days") or 0)
            message = _clock_message(
                n_p=n_p,
                green_days=green_days,
                waiting=waiting,
                sealed=bool(hab.get("envelope_sealed")),
                seal_note=seal_note,
            )
            if not waiting:
                message = playground_flat_line(root, n_p=n_p) or message
            from lumina_core.maturity.playground.demo_cash import note_refill_needed_once

            refill = note_refill_needed_once(root)
            if refill:
                message = refill
            write_phase_progress(
                root,
                "playground",
                progress_pct=min(100.0, float(green_days) / 5.0 * 100.0),
                message=message,
                learned=learned,
            )
            _store_clock(root, stall=stall, conclusive=conclusive, n_p=n_p, seal_note=seal_note)
            sig = f"{n_p}|{stall.windows}|{status.get('reason')}|{ask}|{','.join(missing[:6])}"
            if sig != last_sig:
                append_heartbeat(
                    root,
                    {
                        "n_p": n_p,
                        "stall_windows": stall.windows,
                        "stop_reason": ask or str(status.get("reason") or ""),
                        "blockers": list(missing[:8]),
                        "waiting_operator": bool(hab.get("waiting_operator")),
                    },
                )
                last_sig = sig
            if ok:
                return _complete(root, learned)
            if stepped.stop:
                last_error = "stall_windows_exhausted"
                break
            if ask == "expire":
                last_error = "conclusive_silence"
                break
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
            next_step = "Seal the SIM risk envelope from the live account cash"
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


def _refresh_seal(root: Path) -> str:
    try:
        return str(ensure_portfolio_seal(root) or "")
    except Exception:
        logger.debug("playground.seal_refresh_failed", exc_info=True)
        return ""


def _clock_message(*, n_p: int, green_days: int, waiting: bool, sealed: bool, seal_note: str) -> str:
    if waiting and not sealed:
        return seal_note or "Sim-cash nog niet gelezen. Dagvloer opent bij een gelezen cash-saldo."
    if waiting:
        return "Nodig: DECK. Daarmee bevestig je dat jij de operator bent."
    return f"School · groen {int(green_days)}/5 · closes {int(n_p)}"


def _store_clock(
    root: Path,
    *,
    stall: StallState,
    conclusive: ConclusiveState,
    n_p: int,
    seal_note: str,
) -> None:
    patch: dict[str, Any] = {
        "activity": "session_watch",
        "n_p": n_p,
        "stall_windows": stall.windows,
        "stall_fault": stall.fault,
        "stall_fault_since": stall.fault_since,
        "stall_healthy_since": stall.healthy_since,
        "stall_hold_fault": stall.hold_fault,
        "conclusive_bracket": conclusive.bracket,
        "conclusive_asked_at": conclusive.asked_at,
        "conclusive_continued_through": conclusive.continued_through,
    }
    if seal_note:
        patch["seal_note"] = seal_note
    merge_playground_progress(root, patch)


def _stall_from_progress(root: Path) -> StallState:
    prog = load_playground_progress(root)
    return StallState(
        windows=int(prog.get("stall_windows") or 0),
        fault=str(prog.get("stall_fault") or ""),
        fault_since=_as_float(prog.get("stall_fault_since")),
        healthy_since=_as_float(prog.get("stall_healthy_since")),
        hold_fault=str(prog.get("stall_hold_fault") or ""),
    )


def _conclusive_from_progress(root: Path) -> ConclusiveState:
    prog = load_playground_progress(root)
    return ConclusiveState(
        bracket=int(prog.get("conclusive_bracket") or 0),
        asked_at=_as_float(prog.get("conclusive_asked_at")),
        continued_through=int(prog.get("conclusive_continued_through") or 0),
    )


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
