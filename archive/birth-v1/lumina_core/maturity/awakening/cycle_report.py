"""First Watch measurement. Never a phase pass by itself."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.maturity.awakening.clock import classify_stable
from lumina_core.maturity.awakening.law import (
    AwakeningSnapshot,
    evaluate_awakening_exit,
    evaluate_awakening_pass,
    exam_occupancy,
)
from lumina_core.maturity.awakening.progress import load_awakening_progress
from lumina_core.maturity.awakening.twin_watch import watch_count

_DISCARD_PLAIN: dict[str, str] = {
    "stable_rank_drop": "drawdown of Sharpe slechter dan de stabiele ouder",
    "occupancy_out_of_band": "occupancy buiten de band 25-75%",
    "skill_regression": "winrate en mean_r allebei slechter dan de ouder",
    "evolution_wall_lost": "evolution proof verloren tegenover de ouder",
    "overhold_volume_down": "te lang vastgehouden en minder trades",
    "no_prefer_better": "niet beter dan de ouder",
}

_MEASURED: tuple[str, ...] = (
    "policy_trades",
    "holdout_trades",
    "polish_oos_winrate",
    "birth_exit_winrate",
    "winrate_lift",
    "oos_sharpe",
    "oos_dd_pct",
    "mean_r",
    "edge",
    "median_loss_r",
    "n_plant",
    "policy_only",
    "holdout_exhausted",
    "n_all",
    "eval_only",
    "child_sha256",
    "init_sha256",
    "paired_ci_low",
    "paired_delta",
    "parent_replay_present",
    "child_median_win_r",
    "parent_median_win_r",
)


def cycle_notice(workspace_root: Path | str, cycle: int, shot: dict[str, Any]) -> dict[str, Any]:
    """Telegram payload plus the journal row. ``passed`` / ``ok`` are not copied."""
    root = Path(workspace_root)
    failed = bool(shot.get("error"))
    prog = load_awakening_progress(root)
    full_tape = _f(shot.get("occupancy_full_tape"))
    if full_tape is None:
        full_tape = _f(shot.get("occupancy"))
    at_nb = _f(shot.get("occupancy_at_nb"))
    n_b = int(shot.get("policy_trades") or 0)
    if shot.get("policy_only") is True and n_b <= 0:
        n_b = int(shot.get("holdout_trades") or 0)
    exam = exam_occupancy(n_b=n_b, occupancy_at_nb=at_nb, occupancy_full_tape=full_tape)
    blockers: list[str] = []
    if not failed:
        blockers = list(evaluate_awakening_pass(_snapshot(root, prog, shot, n_b=n_b)).blockers)
    proof = _proof_label(shot, failed=failed)
    kept, discard = _keep_fields(prog, failed=failed)
    message = _message(cycle=cycle, proof=proof, kept=kept, discard=discard, failed=failed, shot=shot)
    learned = _learned(shot, exam=exam, full_tape=full_tape, at_nb=at_nb, proof=proof, kept=kept, discard=discard)
    journal = {
        "schema": "awakening_cycle_journal_v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle": int(cycle),
        "source": "runner",
        "eval_only": shot.get("eval_only") is True,
        "error": str(shot.get("error") or ""),
        "n_b": n_b,
        "wr": shot.get("polish_oos_winrate"),
        "birth_oos_wr": shot.get("birth_exit_winrate"),
        "lift": shot.get("winrate_lift"),
        "mean_r": shot.get("mean_r"),
        "edge": shot.get("edge"),
        "median_loss_r": shot.get("median_loss_r"),
        "sharpe": shot.get("oos_sharpe"),
        "dd_pct": shot.get("oos_dd_pct"),
        "occupancy_exam": exam,
        "occupancy_at_nb": at_nb,
        "occupancy_full_tape": full_tape,
        "n_plant": shot.get("n_plant"),
        "evolution_proof": proof,
        "child_sha": str(shot.get("child_sha256") or ""),
        "init_sha": str(shot.get("init_sha256") or prog.get("init_sha") or ""),
        "child_weight_sha": str(shot.get("child_weight_sha") or ""),
        "init_weight_sha": str(shot.get("init_weight_sha") or ""),
        "kept": kept,
        "discard_reason": discard,
        "student_reset": prog.get("student_reset") is True,
        "run_id": str(prog.get("run_id") or ""),
        "and_blockers": blockers,
        "phase_exit": False,
    }
    return {
        "message": message,
        "learned": learned,
        "missing": blockers,
        "journal": journal,
        "error": str(shot["error"]) if failed else None,
    }


def _snapshot(root: Path, prog: dict[str, Any], shot: dict[str, Any], *, n_b: int) -> AwakeningSnapshot:
    slices_raw = prog.get("regime_slices")
    slices = tuple(str(s) for s in slices_raw if s) if isinstance(slices_raw, list) else ()
    observed_raw = prog.get("regime_observed")
    observed = tuple(str(s) for s in observed_raw if s) if isinstance(observed_raw, list) else ()
    sharpe = _f(shot.get("oos_sharpe", shot.get("sharpe")))
    dd_pct = _f(shot.get("oos_dd_pct", shot.get("dd_pct")))
    full = _f(shot.get("occupancy_full_tape"))
    if full is None:
        full = _f(shot.get("occupancy"))
    birth_mean = _f(shot.get("birth_mean_r"))
    if birth_mean is None:
        birth_mean = _f(prog.get("birth_mean_r"))
    birth_wr = _f(shot.get("birth_exit_winrate"))
    if birth_wr is None:
        birth_wr = _f(prog.get("birth_oos_wr"))
    return AwakeningSnapshot(
        n_b=n_b,
        n_plant=int(shot.get("n_plant") or 0),
        occupancy=full,
        occupancy_at_nb=_f(shot.get("occupancy_at_nb")),
        occupancy_full_tape=full,
        wr=_f(shot.get("polish_oos_winrate", shot.get("wr"))),
        birth_oos_wr=birth_wr,
        mean_r=_f(shot.get("mean_r")),
        birth_mean_r=birth_mean,
        edge=_f(shot.get("edge")),
        median_loss_r=_f(shot.get("median_loss_r")),
        sharpe=sharpe,
        dd_pct=dd_pct,
        stable_class=classify_stable(n_b=n_b, sharpe=sharpe, dd_pct=dd_pct),
        freeze_ok=bool(prog.get("freeze_ok")),
        policy_only=shot.get("policy_only") is True,
        child_sha=str(shot.get("child_sha256") or ""),
        init_sha=str(shot.get("init_sha256") or prog.get("init_sha") or ""),
        child_weight_sha=str(shot.get("child_weight_sha") or prog.get("child_weight_sha") or ""),
        init_weight_sha=str(shot.get("init_weight_sha") or prog.get("init_weight_sha") or ""),
        twin_watch_n=watch_count(root),
        recovery_ok=bool(prog.get("recovery_ok")),
        regime_slices=slices,
        regime_observed=observed,
        tape_exhausted=bool(shot.get("holdout_exhausted")),
        paired_ci_low=_first_f(shot.get("paired_ci_low"), prog.get("paired_ci_low")),
        paired_delta=_first_f(shot.get("paired_delta"), prog.get("paired_delta")),
        parent_replay_present=bool(
            shot.get("parent_replay_present") or prog.get("parent_replay_present")
        ),
        child_median_win_r=_first_f(shot.get("child_median_win_r"), prog.get("child_median_win_r")),
        parent_median_win_r=_first_f(shot.get("parent_median_win_r"), prog.get("parent_median_win_r")),
    )


def _learned(
    shot: dict[str, Any],
    *,
    exam: float | None,
    full_tape: float | None,
    at_nb: float | None,
    proof: str,
    kept: bool | None,
    discard: str,
) -> dict[str, Any]:
    learned: dict[str, Any] = {key: shot[key] for key in _MEASURED if key in shot and shot[key] is not None}
    if exam is not None:
        learned["occupancy_exam"] = exam
    if at_nb is not None:
        learned["occupancy_at_nb"] = at_nb
    if full_tape is not None:
        learned["occupancy_full_tape"] = full_tape
    if proof:
        learned["evolution_proof"] = proof
    if kept is not None:
        learned["kept"] = kept
    if discard:
        learned["discard_reason"] = discard
    lift = shot.get("winrate_lift")
    if lift is not None:
        learned["lift"] = lift
    wr = shot.get("polish_oos_winrate", shot.get("wr"))
    if wr is not None:
        learned["wr"] = wr
    birth = shot.get("birth_exit_winrate", shot.get("birth_oos_wr"))
    if birth is not None:
        learned["birth_oos_wr"] = birth
    n_b = shot.get("policy_trades", shot.get("holdout_trades"))
    if n_b is not None:
        learned["n_b"] = n_b
    return learned


def _proof_label(shot: dict[str, Any], *, failed: bool) -> str:
    if failed or "passed" not in shot:
        return ""
    return "gehaald" if shot.get("passed") is True else "niet gehaald"


def _keep_fields(prog: dict[str, Any], *, failed: bool) -> tuple[bool | None, str]:
    if failed or "kept" not in prog:
        return None, ""
    kept = prog.get("kept")
    if kept is True:
        return True, ""
    if kept is False:
        return False, str(prog.get("discard_reason") or "")
    return None, ""


def discard_plain(reason: str) -> str:
    """Operator sentence. The machine code stays in parentheses so logs still grep."""
    code = str(reason or "").strip()
    if not code:
        return "reden onbekend"
    plain = _DISCARD_PLAIN.get(code, code)
    return f"{plain} ({code})"


def exam_failure_note(workspace_root: Path | str) -> str:
    """Phase-exit sentence. First Watch grades the frozen plant, not a trained child."""
    ok, missing, _learned = evaluate_awakening_exit(workspace_root)
    if ok:
        return "First Watch AND gehaald. Bevroren Birth-plant intact."
    shown = ",".join(str(item) for item in missing[:8]) if missing else "AND missing"
    return f"First Watch AND niet gehaald. Bevroren Birth-plant intact. Ontbreekt: {shown}."


def phase_exit_journal(
    workspace_root: Path | str,
    *,
    passed: bool,
    missing: list[str],
    note: str,
) -> dict[str, Any]:
    """One durable row when the clock stops. Not a cycle measurement."""
    root = Path(workspace_root)
    prog = load_awakening_progress(root)
    wr = _f(prog.get("wr"))
    birth = _f(prog.get("birth_oos_wr"))
    lift = (float(wr) - float(birth)) if wr is not None and birth is not None else None
    return {
        "schema": "awakening_cycle_journal_v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "runner",
        "phase_exit": True,
        "passed": bool(passed),
        "run_id": str(prog.get("run_id") or ""),
        "cycle": prog.get("cycle"),
        "kept": prog.get("kept") is True,
        "student_reset": prog.get("student_reset") is True,
        "discard_reason": str(prog.get("discard_reason") or ""),
        "and_blockers": list(missing),
        "note": str(note),
        "child_sha": str(prog.get("child_sha") or ""),
        "init_sha": str(prog.get("init_sha") or ""),
        "mean_r": prog.get("mean_r"),
        "lift": lift,
        "dd_pct": prog.get("dd_pct"),
        "n_b": prog.get("n_b"),
        "eval_only": True,
    }


def _message(*, cycle: int, proof: str, kept: bool | None, discard: str, failed: bool, shot: dict[str, Any]) -> str:
    measure = _proof_measure(shot)
    if failed:
        return f"First Watch meting mislukt. Dit is geen fase-einde. {measure}"
    del cycle, proof, kept, discard
    return f"First Watch meting. Dit is geen fase-einde. {measure}"


def _proof_measure(shot: dict[str, Any]) -> str:
    """Lift and paired CI are recorded. They do not open First Watch."""
    lift = _f(shot.get("winrate_lift"))
    lift_txt = f"Lift {lift:.1%} (diagnose)." if lift is not None else "Lift onbekend (diagnose)."
    ci = _f(shot.get("paired_ci_low"))
    if ci is not None:
        return f"{lift_txt} Paired CI {ci:.4f}R (record; Playground-handmuur +0.05R)."
    if shot.get("parent_replay_present") is True:
        return f"{lift_txt} Paired CI ontbreekt (record)."
    return f"{lift_txt} Paired CI ontbreekt: geen handelsdag op de holdout-ledger."


def _first_f(*values: Any) -> float | None:
    for value in values:
        parsed = _f(value)
        if parsed is not None:
            return parsed
    return None


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
