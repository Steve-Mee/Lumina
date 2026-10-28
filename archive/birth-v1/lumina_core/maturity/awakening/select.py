"""One Awakening select cycle: train A, eval B, persist metrics. Birth freeze intact."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import median_loss_r
from lumina_core.logging_utils import get_logger
from lumina_core.maturity.awakening.clock import classify_stable
from lumina_core.maturity.awakening.progress import merge_awakening_progress
from lumina_core.maturity.phase_runners.awakening_shot import (
    AwakeningShotError,
    live_child_zip,
    live_ledger_path,
)

logger = get_logger("lumina.maturity.awakening.select")

ProgressFn = Callable[[float, str], None]
TrainFn = Callable[..., dict[str, Any]]
EvalFn = Callable[..., dict[str, Any]]
SplitLoader = Callable[..., tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]]


def continuation_init_path(workspace_root: Path, *, cycle: int) -> Path | None:
    """Train from the student zip. Exam incumbent if the student was reset."""
    del cycle
    from lumina_core.maturity.awakening.keep_best import incumbent_zip, student_zip

    student = student_zip(workspace_root)
    if student.is_file() and student.stat().st_size > 0:
        return student
    inc = incumbent_zip(workspace_root)
    if inc.is_file() and inc.stat().st_size > 0:
        return inc
    child = live_child_zip(workspace_root)
    if not child.is_file() or child.stat().st_size <= 0:
        return None
    if not child_is_preferable(workspace_root):
        return None
    return child


def child_is_preferable(workspace_root: Path) -> bool:
    from lumina_core.maturity.awakening.law import N_B_MIN
    from lumina_core.maturity.awakening.progress import load_awakening_progress

    prog = load_awakening_progress(workspace_root)
    n_b = int(prog.get("n_b") or 0)
    if n_b <= 0:
        return False
    wr = prog.get("wr")
    birth = prog.get("birth_oos_wr")
    if wr is None or birth is None:
        return n_b >= N_B_MIN
    if float(wr) + 1e-12 < float(birth) and n_b < N_B_MIN:
        return False
    return True


def persist_cycle(workspace_root: Path, shot: dict[str, Any], *, cycle: int) -> dict[str, Any]:
    policy_n = int(shot.get("policy_trades") or 0)
    n_all = int(shot.get("n_all") or 0)
    policy_only = shot.get("policy_only") is True
    if policy_only and policy_n <= 0:
        policy_n = int(shot.get("holdout_trades") or 0)
    n_b = policy_n
    occupancy = _f(shot.get("occupancy"))
    mean_r = _f(shot.get("mean_r"))
    edge = _f(shot.get("edge"))
    med = _f(shot.get("median_loss_r"))
    if med is None:
        med = _median_loss_from_ledger(live_ledger_path(workspace_root))
    sharpe = _f(shot.get("oos_sharpe"))
    dd_pct = _f(shot.get("oos_dd_pct"))
    stable = classify_stable(n_b=n_b, sharpe=sharpe, dd_pct=dd_pct)
    birth_mean = _f(shot.get("birth_mean_r"))
    if birth_mean is None:
        try:
            from lumina_core.birth.fitness_vector import load_fitness_vector

            vec = load_fitness_vector(workspace_root)
            if vec is not None:
                birth_mean = float(vec.mean_r)
        except Exception:
            birth_mean = None
    patch: dict[str, Any] = {
        "cycle": int(cycle),
        "n_b": n_b,
        "n_plant": max(0, n_all - policy_n),
        "wr": shot.get("polish_oos_winrate"),
        "birth_oos_wr": shot.get("birth_exit_winrate"),
        "birth_mean_r": birth_mean,
        "child_sha": shot.get("child_sha256") or "",
        "init_sha": shot.get("init_sha256") or "",
        "child_weight_sha": str(shot.get("child_weight_sha") or ""),
        "init_weight_sha": str(shot.get("init_weight_sha") or ""),
        "freeze_ok": bool(shot.get("freeze_ok")),
        "policy_only": policy_only,
        "occupancy": occupancy,
        "occupancy_full_tape": occupancy,
        "occupancy_at_nb": _f(shot.get("occupancy_at_nb")),
        "mean_r": mean_r,
        "edge": edge,
        "median_loss_r": med,
        "sharpe": sharpe,
        "dd_pct": dd_pct,
        "stable_class": stable,
        "tape_exhausted": bool(shot.get("holdout_exhausted")),
        "occupancy_seed_source": shot.get("occupancy_seed_source") or "",
        "mean_hold_bars": _f(shot.get("mean_hold_bars")),
        "geometry_hold_bars": _f(shot.get("geometry_hold_bars")),
        "paired_delta": _f(shot.get("paired_delta")),
        "paired_ci_low": _f(shot.get("paired_ci_low")),
        "parent_replay_present": bool(shot.get("parent_replay_present")),
        "child_median_win_r": _f(shot.get("child_median_win_r")),
        "parent_median_win_r": _f(shot.get("parent_median_win_r")),
        "constitution_violations": shot.get("constitution_violations"),
        "constitution_blocks": shot.get("constitution_blocks"),
    }
    merge_awakening_progress(workspace_root, patch)
    return patch


def run_select_cycle(
    workspace_root: Path,
    *,
    cycle: int,
    progress: ProgressFn | None = None,
    train_fn: TrainFn | None = None,
    eval_fn: EvalFn | None = None,
    split_loader: SplitLoader | None = None,
    eval_only: bool = False,
    lr_scale: float = 1.0,
    should_stop: Any | None = None,
) -> dict[str, Any]:
    from lumina_core.maturity.phase_runners.awakening_shot import run_live_awakening_shot

    root = Path(workspace_root)
    # Cycle 0 is the frozen Birth plant. A leftover student zip is not that plant.
    init_override = None if eval_only else continuation_init_path(root, cycle=cycle)
    shot = run_live_awakening_shot(
        root,
        progress=progress,
        train_fn=train_fn,
        eval_fn=eval_fn,
        split_loader=split_loader,
        init_path=init_override,
        eval_only=eval_only,
        lr_scale=lr_scale,
        cycle=cycle,
        should_stop=should_stop,
    )
    persist_cycle(root, shot, cycle=cycle)
    apply_keep_best(root, shot, eval_only=eval_only)
    return shot


_STUDENT_RESET_REASONS = frozenset({
    "evolution_wall_lost",
    "stable_rank_drop",
    "paired_delta_not_higher",
})


def apply_keep_best(workspace_root: Path, shot: dict[str, Any], *, eval_only: bool) -> None:
    from lumina_core.maturity.awakening.keep_best import (
        copy_zip,
        freeze_incumbent_ledgers,
        incumbent_from_shot,
        incumbent_zip,
        keep_block_reason,
        last_shot_card,
        parent_replay_card,
        persist_incumbent_proof,
        progress_from_incumbent,
        skill_regressed,
        sync_student_zip,
    )
    from lumina_core.maturity.awakening.progress import load_awakening_progress, merge_awakening_progress

    root = Path(workspace_root)
    child = live_child_zip(root)
    inc_path = incumbent_zip(root)
    snap = incumbent_from_shot(shot)
    if eval_only:
        copy_zip(child, inc_path)
        sync_student_zip(root, child=child, incumbent=inc_path, reset=False)
        freeze_incumbent_ledgers(root)
        merge_awakening_progress(
            root,
            {
                **snap,
                "kept": True,
                "student_reset": False,
                **parent_replay_card(root),
            },
        )
        persist_incumbent_proof(root, snap)
        return
    prog = load_awakening_progress(root)
    incumbent = {
        "incumbent_n_b": int(prog.get("incumbent_n_b") or 0),
        "incumbent_wr": prog.get("incumbent_wr"),
        "incumbent_mean_r": prog.get("incumbent_mean_r"),
        "incumbent_sha": prog.get("incumbent_sha") or "",
        "incumbent_weight_sha": str(prog.get("incumbent_weight_sha") or ""),
        "incumbent_init_weight_sha": str(
            prog.get("incumbent_init_weight_sha") or prog.get("init_weight_sha") or ""
        ),
        "incumbent_occupancy": prog.get("incumbent_occupancy"),
        "incumbent_edge": prog.get("incumbent_edge"),
        "incumbent_sharpe": prog.get("incumbent_sharpe"),
        "incumbent_dd_pct": prog.get("incumbent_dd_pct"),
        "incumbent_median_loss_r": prog.get("incumbent_median_loss_r"),
        "incumbent_n_plant": int(prog.get("incumbent_n_plant") or 0),
        "incumbent_occupancy_at_nb": prog.get("incumbent_occupancy_at_nb"),
        "incumbent_paired_delta": prog.get("incumbent_paired_delta"),
        "incumbent_paired_ci_low": prog.get("incumbent_paired_ci_low"),
        "incumbent_parent_replay_present": bool(prog.get("incumbent_parent_replay_present")),
        "incumbent_child_median_win_r": prog.get("incumbent_child_median_win_r"),
        "incumbent_parent_median_win_r": prog.get("incumbent_parent_median_win_r"),
    }
    card = last_shot_card(shot)
    if int(incumbent["incumbent_n_b"] or 0) <= 0:
        _keep_child(root, child, inc_path, snap, card, copy_zip, sync_student_zip, persist_incumbent_proof)
        return
    reason = keep_block_reason(shot, incumbent)
    if reason is None:
        _keep_child(root, child, inc_path, snap, card, copy_zip, sync_student_zip, persist_incumbent_proof)
        return
    reset_student = skill_regressed(shot, incumbent) or reason in _STUDENT_RESET_REASONS
    if reset_student:
        logger.info("awakening.student.reset reason=%s", reason)
        sync_student_zip(root, child=child, incumbent=inc_path, reset=True)
    else:
        logger.info("awakening.student.continue reason=%s", reason)
        sync_student_zip(root, child=child, incumbent=inc_path, reset=False)
    copy_zip(inc_path, child)
    merge_awakening_progress(
        root,
        {
            **progress_from_incumbent(incumbent),
            "kept": False,
            "discard_reason": reason,
            "student_reset": reset_student,
            "discarded_n_b": int(shot.get("policy_trades") or 0),
            "discarded_wr": shot.get("polish_oos_winrate"),
            **card,
        },
    )
    persist_incumbent_proof(root, incumbent)


def _keep_child(
    root: Path,
    child: Path,
    inc_path: Path,
    snap: dict[str, Any],
    card: dict[str, Any],
    copy_zip: Any,
    sync_student_zip: Any,
    persist_incumbent_proof: Any,
) -> None:
    from lumina_core.maturity.awakening.keep_best import freeze_incumbent_ledgers, parent_replay_card
    from lumina_core.maturity.awakening.progress import merge_awakening_progress

    copy_zip(child, inc_path)
    sync_student_zip(root, child=child, incumbent=inc_path, reset=False)
    freeze_incumbent_ledgers(root)
    merge_awakening_progress(
        root,
        {
            **snap,
            "kept": True,
            "discard_reason": "",
            "student_reset": False,
            **card,
            **parent_replay_card(root),
        },
    )
    persist_incumbent_proof(root, snap)


def _median_loss_from_ledger(path: Path) -> float | None:
    if not path.is_file():
        return None
    rs: list[float] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            if not isinstance(row, dict) or row.get("plant"):
                continue
            val = row.get("trade_r")
            if val is None:
                continue
            rs.append(float(val))
    except (OSError, ValueError, TypeError):
        return None
    return median_loss_r(rs)


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "AwakeningShotError",
    "apply_keep_best",
    "child_is_preferable",
    "continuation_init_path",
    "persist_cycle",
    "run_select_cycle",
]
