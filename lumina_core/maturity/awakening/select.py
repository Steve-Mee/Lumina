"""One Awakening select cycle: train A, eval B, persist metrics. Birth freeze intact."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.birth.fitness_vector import load_fitness_vector
from lumina_core.birth.foundation_metrics import median_loss_r
from lumina_core.logging_utils import get_logger
from lumina_core.maturity.awakening.clock import classify_stable
from lumina_core.maturity.awakening.progress import (
    load_awakening_progress,
    merge_awakening_progress,
)
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
    """Train from the keep-best incumbent. Frozen π* if none exists."""
    del cycle
    from lumina_core.maturity.awakening.keep_best import incumbent_zip

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


def same_tape_parent_locked(prog: dict[str, Any]) -> bool:
    """True once cycle 0 wrote the same-exam parent. Wipe is the only unlock."""
    return bool(prog.get("parent_same_tape")) and _f(prog.get("parent_holdout_wr")) is not None


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
    prev = load_awakening_progress(workspace_root)
    birth_mean = _f(shot.get("birth_mean_r"))
    parent_wr = _f(shot.get("polish_oos_winrate"))
    locked = same_tape_parent_locked(prev)
    parent_same = cycle <= 0 or bool(prev.get("parent_same_tape"))
    if cycle <= 0 and locked:
        birth_oos = _f(prev.get("birth_oos_wr"))
        if _f(prev.get("birth_mean_r")) is not None:
            birth_mean = _f(prev.get("birth_mean_r"))
        parent_same = True
    elif cycle <= 0:
        birth_oos = parent_wr
        if mean_r is not None:
            birth_mean = mean_r
    elif parent_same:
        birth_oos = _f(prev.get("birth_oos_wr"))
        if _f(prev.get("birth_mean_r")) is not None:
            birth_mean = _f(prev.get("birth_mean_r"))
    else:
        birth_oos = _f(shot.get("birth_exit_winrate"))
        if birth_mean is None:
            vec = load_fitness_vector(workspace_root)
            if vec is not None:
                birth_mean = float(vec.mean_r)
    split_meta = shot.get("split") if isinstance(shot.get("split"), dict) else {}
    patch: dict[str, Any] = {
        "cycle": int(cycle),
        "n_b": n_b,
        "n_plant": max(0, n_all - policy_n),
        "wr": shot.get("polish_oos_winrate"),
        "birth_oos_wr": birth_oos,
        "birth_mean_r": birth_mean,
        "parent_same_tape": bool(parent_same),
        "fitness_oos_wr": shot.get("birth_exit_winrate"),
        "exam_kind": split_meta.get("exam_kind") or prev.get("exam_kind") or "holdout_B",
        "exam_n": split_meta.get("exam_n") or prev.get("exam_n"),
        "child_sha": shot.get("child_sha256") or "",
        "init_sha": shot.get("init_sha256") or "",
        "freeze_ok": bool(shot.get("freeze_ok")),
        "policy_only": policy_only,
        "occupancy": occupancy,
        "mean_r": mean_r,
        "edge": edge,
        "median_loss_r": med,
        "sharpe": sharpe,
        "dd_pct": dd_pct,
        "stable_class": stable,
        "tape_exhausted": bool(shot.get("holdout_exhausted")),
        "occupancy_seed_source": shot.get("occupancy_seed_source") or "",
    }
    if cycle <= 0 and not locked:
        patch["parent_holdout_wr"] = parent_wr
        patch["parent_holdout_mean_r"] = mean_r
        patch["parent_holdout_n_b"] = n_b
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
) -> dict[str, Any]:
    from lumina_core.maturity.phase_runners.awakening_shot import run_live_awakening_shot

    root = Path(workspace_root)
    init_override = continuation_init_path(root, cycle=cycle)
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
    )
    persist_cycle(root, shot, cycle=cycle)
    apply_keep_best(root, shot, eval_only=eval_only)
    return shot


def apply_keep_best(workspace_root: Path, shot: dict[str, Any], *, eval_only: bool) -> None:
    from lumina_core.maturity.awakening.keep_best import (
        child_beats_incumbent,
        copy_zip,
        incumbent_from_shot,
        incumbent_zip,
        persist_incumbent_proof,
        progress_from_incumbent,
    )
    from lumina_core.maturity.awakening.progress import load_awakening_progress, merge_awakening_progress

    root = Path(workspace_root)
    child = live_child_zip(root)
    inc_path = incumbent_zip(root)
    snap = incumbent_from_shot(shot)
    if eval_only:
        copy_zip(child, inc_path)
        merge_awakening_progress(
            root,
            {
                **snap,
                "kept": True,
                "parent_holdout_n_b": snap["incumbent_n_b"],
                "parent_holdout_wr": snap["incumbent_wr"],
                "parent_holdout_mean_r": snap["incumbent_mean_r"],
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
        "incumbent_occupancy": prog.get("incumbent_occupancy"),
        "incumbent_edge": prog.get("incumbent_edge"),
        "incumbent_sharpe": prog.get("incumbent_sharpe"),
        "incumbent_dd_pct": prog.get("incumbent_dd_pct"),
        "incumbent_median_loss_r": prog.get("incumbent_median_loss_r"),
        "incumbent_n_plant": int(prog.get("incumbent_n_plant") or 0),
    }
    if int(incumbent["incumbent_n_b"] or 0) <= 0:
        copy_zip(child, inc_path)
        merge_awakening_progress(root, {**snap, "kept": True})
        persist_incumbent_proof(root, snap)
        return
    last_shot = {
        "last_shot_n_b": int(shot.get("policy_trades") or 0),
        "last_shot_wr": shot.get("polish_oos_winrate"),
        "last_shot_mean_r": shot.get("mean_r"),
        "last_shot_sha": str(shot.get("child_sha256") or ""),
    }
    kept = child_beats_incumbent(shot, incumbent)
    if kept:
        copy_zip(child, inc_path)
        merge_awakening_progress(root, {**snap, "kept": True, **last_shot})
        persist_incumbent_proof(root, snap)
        return
    copy_zip(inc_path, child)
    merge_awakening_progress(
        root,
        {
            **progress_from_incumbent(incumbent),
            "kept": False,
            "discarded_n_b": int(shot.get("policy_trades") or 0),
            "discarded_wr": shot.get("polish_oos_winrate"),
            **last_shot,
        },
    )
    persist_incumbent_proof(root, incumbent)


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
    "same_tape_parent_locked",
]
