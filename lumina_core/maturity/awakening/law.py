"""Awakening pass law (ADR-0049). AND-gates, fail-closed, no WR-only cheat."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import (
    MEDIAN_LOSS_R_MAX,
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
    S5_DD_MAX_PCT,
    S5_SHARPE_FLOOR,
)
from lumina_core.maturity.post_birth_skill_gates import EVOLUTION_PROOF_OOS_WR_MIN

N_B_MIN = 500
STABLE = "STABLE"
CLASS_INCONCLUSIVE = "INCONCLUSIVE"
CLASS_REGRESS = "GRIND_REGRESS"


@dataclass(frozen=True, slots=True)
class AwakeningSnapshot:
    n_b: int = 0
    n_plant: int = 0
    occupancy: float | None = None
    occupancy_at_nb: float | None = None
    occupancy_full_tape: float | None = None
    wr: float | None = None
    birth_oos_wr: float | None = None
    mean_r: float | None = None
    birth_mean_r: float | None = None
    edge: float | None = None
    median_loss_r: float | None = None
    sharpe: float | None = None
    dd_pct: float | None = None
    stable_class: str = CLASS_INCONCLUSIVE
    freeze_ok: bool = False
    policy_only: bool = False
    child_sha: str = ""
    init_sha: str = ""
    child_weight_sha: str = ""
    init_weight_sha: str = ""
    twin_watch_n: int = 0
    recovery_ok: bool = False
    regime_slices: tuple[str, ...] = ()
    regime_observed: tuple[str, ...] = ()
    tape_exhausted: bool = False
    proof_record_passed: bool = False
    paired_ci_low: float | None = None
    paired_delta: float | None = None
    parent_replay_present: bool = False
    child_median_win_r: float | None = None
    parent_median_win_r: float | None = None
    constitution_violations: int | None = None
    constitution_blocks: int | None = None


@dataclass(frozen=True, slots=True)
class AwakeningPassResult:
    passed: bool
    blockers: tuple[str, ...]
    proofs: tuple[str, ...]
    clock_open: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def to_learned(self) -> dict[str, Any]:
        learned = dict(self.detail)
        learned["pass_now"] = self.passed
        learned["clock_open"] = self.clock_open
        learned["blockers"] = list(self.blockers)
        learned["exit_proofs"] = list(self.proofs)
        return learned


def exam_occupancy(
    *,
    n_b: int,
    occupancy_at_nb: float | None,
    occupancy_full_tape: float | None,
) -> float | None:
    """Once n_B≥500 the sample window is the gate. Below that, the full tape is."""
    if int(n_b) >= N_B_MIN:
        return occupancy_at_nb
    return occupancy_full_tape


def evaluate_awakening_pass(snap: AwakeningSnapshot) -> AwakeningPassResult:
    blockers: list[str] = []
    proofs: list[str] = []
    n_b = int(snap.n_b)
    clock_open = n_b < N_B_MIN

    if not snap.freeze_ok:
        blockers.append("birth_freeze_violated")
    else:
        proofs.append("birth_freeze_intact")

    if not snap.policy_only:
        blockers.append("skill_not_policy_only")
    else:
        proofs.append("policy_only")

    if n_b < N_B_MIN:
        blockers.append(f"n_B={n_b} < {N_B_MIN}")
    else:
        proofs.append("n_B>=500")

    full_tape = snap.occupancy_full_tape if snap.occupancy_full_tape is not None else snap.occupancy
    exam = exam_occupancy(
        n_b=n_b,
        occupancy_at_nb=snap.occupancy_at_nb,
        occupancy_full_tape=full_tape,
    )
    if exam is None:
        blockers.append("occupancy_missing")
    elif not (S3_OCCUPANCY_MIN - 1e-12 <= float(exam) <= S3_OCCUPANCY_MAX + 1e-12):
        blockers.append(
            f"occupancy={float(exam):.4f} not in {S3_OCCUPANCY_MIN:.2f}-{S3_OCCUPANCY_MAX:.2f}"
        )
    else:
        proofs.append("occupancy_in_band")

    if snap.median_loss_r is None:
        blockers.append("median_loss_r_missing")
    elif float(snap.median_loss_r) > MEDIAN_LOSS_R_MAX + 1e-12:
        blockers.append(f"median_loss_r={snap.median_loss_r:.4f} > {MEDIAN_LOSS_R_MAX}")
    else:
        proofs.append("process_r")

    if not snap.parent_replay_present:
        blockers.append("baseline_book_missing")
    else:
        proofs.append("baseline_book")

    if str(snap.stable_class or "") != STABLE:
        blockers.append(f"stable_class={snap.stable_class or CLASS_INCONCLUSIVE}")
    else:
        if snap.sharpe is None or float(snap.sharpe) <= S5_SHARPE_FLOOR:
            blockers.append(f"sharpe={snap.sharpe} <= {S5_SHARPE_FLOOR}")
        elif snap.dd_pct is None or float(snap.dd_pct) > S5_DD_MAX_PCT + 1e-12:
            blockers.append(f"dd={snap.dd_pct} > {S5_DD_MAX_PCT}")
        else:
            proofs.append("STABLE")

    # Tensor storages, not the zip container. A resave is not a new child.
    child_w = str(snap.child_weight_sha or "")
    init_w = str(snap.init_weight_sha or "")
    if not child_w or not init_w:
        blockers.append("weight_sha_missing")
    elif child_w != init_w:
        blockers.append("baseline_not_the_plant")
    else:
        proofs.append("baseline_is_plant")

    if snap.constitution_violations is None or snap.constitution_blocks is None:
        blockers.append("constitution_unmeasured")
    elif int(snap.constitution_violations) > 0 or int(snap.constitution_blocks) > 0:
        blockers.append("constitution_event")
    else:
        proofs.append("constitution_clear")

    if int(snap.twin_watch_n) < 1:
        blockers.append("twin_watch_missing")
    else:
        proofs.append("twin_watch")

    if not snap.recovery_ok:
        blockers.append("recovery_not_proven")
    else:
        proofs.append("recovery_ok")

    if not snap.regime_observed:
        blockers.append("regime_visibility_missing")
    else:
        proofs.append("regime_visibility")

    passed = not blockers
    detail = {
        "n_b": n_b,
        "n_plant": int(snap.n_plant),
        "occupancy": exam,
        "occupancy_at_nb": snap.occupancy_at_nb,
        "occupancy_full_tape": full_tape,
        "wr": snap.wr,
        "birth_oos_wr": snap.birth_oos_wr,
        "lift": _lift(snap),
        "mean_r": snap.mean_r,
        "birth_mean_r": snap.birth_mean_r,
        "edge": snap.edge,
        "median_loss_r": snap.median_loss_r,
        "sharpe": snap.sharpe,
        "dd_pct": snap.dd_pct,
        "stable_class": snap.stable_class,
        "freeze_ok": snap.freeze_ok,
        "policy_only": snap.policy_only,
        "twin_watch_n": int(snap.twin_watch_n),
        "recovery_ok": snap.recovery_ok,
        "regime_slices": list(snap.regime_slices),
        "regime_observed": list(snap.regime_observed),
        "tape_exhausted": snap.tape_exhausted,
        "proof_record_passed": snap.proof_record_passed,
        "note": "First Watch: frozen plant baseline on holdout B, no learn (ADR-0049)",
        "evolution_notes": _adr0026_reasons(snap),
        "constitution_violations": snap.constitution_violations,
        "constitution_blocks": snap.constitution_blocks,
    }
    return AwakeningPassResult(
        passed=passed,
        blockers=tuple(blockers),
        proofs=tuple(proofs),
        clock_open=clock_open and not passed,
        detail=detail,
    )


def _lift(snap: AwakeningSnapshot) -> float | None:
    if snap.wr is None or snap.birth_oos_wr is None:
        return None
    return float(snap.wr) - float(snap.birth_oos_wr)


def _adr0026_reasons(snap: AwakeningSnapshot) -> list[str]:
    """Every Evolution Proof miss. A collapsed median does not hide a missed CI.

    Pass/fail is unchanged: any reason fails the AND. OOS >= 45% still clears
    the regret clause and does not excuse a collapsed median win.
    """
    from lumina_core.birth.evolution_proof_gate import PAIRED_REGRET_MIN_R, median_win_collapsed

    if snap.wr is None or snap.birth_oos_wr is None:
        return ["adr0026_wr_missing"]
    reasons: list[str] = []
    if median_win_collapsed(snap.child_median_win_r, snap.parent_median_win_r):
        reasons.append("median_win_r_collapsed")
    oos_ok = float(snap.wr) + 1e-12 >= EVOLUTION_PROOF_OOS_WR_MIN
    ci = snap.paired_ci_low
    ci_ok = (
        snap.parent_replay_present
        and ci is not None
        and float(ci) + 1e-12 >= PAIRED_REGRET_MIN_R
    )
    if oos_ok or ci_ok:
        return reasons
    if not snap.parent_replay_present:
        reasons.append("parent_replay_missing")
        return reasons
    shown = "missing" if ci is None else f"{float(ci):.4f}R"
    reasons.append(f"paired regret CI {shown} < {PAIRED_REGRET_MIN_R:.2f}R")
    return reasons


def snapshot_from_workspace(workspace_root: Path | str) -> AwakeningSnapshot:
    from lumina_core.birth.evolution_proof_gate import load_evolution_proof_record
    from lumina_core.birth.fitness_vector import load_fitness_vector
    from lumina_core.maturity.awakening.progress import load_awakening_progress
    from lumina_core.maturity.awakening.twin_watch import watch_count

    root = Path(workspace_root)
    prog = load_awakening_progress(root)
    rec = load_evolution_proof_record(root)
    vector = load_fitness_vector(root)
    slices_raw = prog.get("regime_slices") if prog else None
    slices: tuple[str, ...] = ()
    if isinstance(slices_raw, (list, tuple)):
        slices = tuple(str(s) for s in slices_raw if s)
    observed_raw = prog.get("regime_observed") if prog else None
    observed: tuple[str, ...] = ()
    if isinstance(observed_raw, (list, tuple)):
        observed = tuple(str(s) for s in observed_raw if s)
    elif isinstance((prog.get("regime_status") if prog else None), dict):
        status = prog.get("regime_status") or {}
        observed = tuple(k for k, v in status.items() if str(v) == "observed")

    wr = _f(prog.get("wr") if prog else None)
    if wr is None:
        wr = _f(rec.get("polish_oos_winrate") or rec.get("oos_winrate"))
    birth_wr = _f(prog.get("birth_oos_wr") if prog else None)
    if birth_wr is None:
        birth_wr = _f(rec.get("birth_exit_winrate"))
    if birth_wr is None and vector is not None:
        birth_wr = float(vector.oos_wr)
    birth_mean = _f(prog.get("birth_mean_r") if prog else None)
    if birth_mean is None and vector is not None:
        birth_mean = float(vector.mean_r)
    n_b = int(prog.get("n_b") or rec.get("holdout_trades") or 0)
    full_tape = _f(prog.get("occupancy_full_tape") if prog else None)
    if full_tape is None:
        full_tape = _f(prog.get("occupancy") if prog else None)
    paired_ci = _f(prog.get("paired_ci_low") if prog else None)
    paired_delta = _f(prog.get("paired_delta") if prog else None)
    parent_replay = bool(prog.get("parent_replay_present")) if prog else False
    child_med = _f(prog.get("child_median_win_r") if prog else None)
    parent_med = _f(prog.get("parent_median_win_r") if prog else None)
    book = _ledger_book(root)
    if book is not None:
        parent_replay = bool(book["parent_replay_present"])
        paired_ci = book["paired_ci_low"]
        paired_delta = book["paired_delta"]
        child_med = book["child_median_win_r"]
        parent_med = book["parent_median_win_r"]
        # The book on disk is the sample. A progress n_B cannot outvote it.
        n_b = min(int(book.get("n_policy") or 0), int(book.get("n_parent") or 0))

    return AwakeningSnapshot(
        n_b=n_b,
        n_plant=int(prog.get("n_plant") or 0),
        occupancy=full_tape,
        occupancy_at_nb=_f(prog.get("occupancy_at_nb") if prog else None),
        occupancy_full_tape=full_tape,
        wr=wr,
        birth_oos_wr=birth_wr,
        mean_r=_f(prog.get("mean_r") if prog else None),
        birth_mean_r=birth_mean,
        edge=_f(prog.get("edge") if prog else None),
        median_loss_r=_f(prog.get("median_loss_r") if prog else None),
        sharpe=_f(prog.get("sharpe") if prog else None),
        dd_pct=_f(prog.get("dd_pct") if prog else None),
        stable_class=str(prog.get("stable_class") or CLASS_INCONCLUSIVE),
        freeze_ok=bool(prog.get("freeze_ok")),
        policy_only=bool(prog.get("policy_only")),
        child_sha=str(prog.get("child_sha") or rec.get("child_sha256") or ""),
        init_sha=str(prog.get("init_sha") or rec.get("init_sha256") or ""),
        child_weight_sha=str(prog.get("child_weight_sha") or ""),
        init_weight_sha=str(prog.get("init_weight_sha") or ""),
        twin_watch_n=watch_count(root),
        recovery_ok=bool(prog.get("recovery_ok")),
        regime_slices=slices,
        regime_observed=observed,
        tape_exhausted=bool(prog.get("tape_exhausted")),
        proof_record_passed=bool(rec.get("passed")),
        paired_ci_low=paired_ci,
        paired_delta=paired_delta,
        parent_replay_present=parent_replay,
        child_median_win_r=child_med,
        parent_median_win_r=parent_med,
        constitution_violations=_opt_int(prog, "constitution_violations"),
        constitution_blocks=_opt_int(prog, "constitution_blocks"),
    )


def _ledger_book(root: Path) -> dict[str, Any] | None:
    """Paired regret of the kept organism.

    The live student ledger is overwritten every cycle. Reading it here scored
    a discarded shot against the incumbent. Missing frozen ledgers stay on the
    progress fields. They are not filled from the live ledger.
    """
    from lumina_core.birth.evolution_proof_gate import paired_book_from_rows
    from lumina_core.maturity.phase_runners.awakening_shot import (
        INCUMBENT_LEDGER_NAME,
        INCUMBENT_PARENT_LEDGER_NAME,
        artifacts_dir,
    )

    art = artifacts_dir(root)
    child = art / INCUMBENT_LEDGER_NAME
    parent = art / INCUMBENT_PARENT_LEDGER_NAME
    if not child.is_file() or not parent.is_file():
        return None
    if child.stat().st_size <= 0 or parent.stat().st_size <= 0:
        return None
    child_rows = _jsonl(child)
    parent_rows = _jsonl(parent)
    book = paired_book_from_rows(child_rows, parent_rows)
    book["n_policy"] = _policy_closes(child_rows)
    book["n_parent"] = _policy_closes(parent_rows)
    return book


def _policy_closes(rows: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        if isinstance(row, dict) and row.get("plant") is not True and row.get("trade_r") is not None
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            return []
        if isinstance(row, dict):
            rows.append(row)
    return rows


def evaluate_awakening_exit(
    workspace_root: Path | str,
) -> tuple[bool, list[str], dict[str, Any]]:
    result = evaluate_awakening_pass(snapshot_from_workspace(workspace_root))
    learned = result.to_learned()
    missing = list(result.blockers) if not result.passed else []
    return result.passed, missing, learned


def _opt_int(prog: dict[str, Any], key: str) -> int | None:
    if key not in prog or prog.get(key) is None:
        return None
    try:
        return int(prog[key])
    except (TypeError, ValueError):
        return None


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
