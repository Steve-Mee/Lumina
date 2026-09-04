"""G2 evaluate-only: newborn 43-dim then MARK_EYES child 46-dim on legs A/B."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_mark_eyes_eval import mark_eyes_gym_rollout
from lumina_core.birth.awakening_mech import bucket_stats
from lumina_core.birth.awakening_open_split_flags import hole_from_u, universe_rows, winners_from_u
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW, load_close_jsonl
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_select_env import select_runtime
from lumina_core.birth.birth_exit_policy_export import load_frozen_policy
from lumina_core.birth.genesis_eyes_budget import (
    STUDENT_BIRTH_NAME,
    STUDENT_EYES_NAME,
    BudgetProtocolError,
    refuse_path_early_baseline,
)
from lumina_core.birth.genesis_hold_compare import bars_held_values, percentile
from lumina_core.birth.genesis_mark_eyes_eval import split_holdout_ab
from lumina_core.birth.tick_cache_persist import load_split_cache
from lumina_core.rl.observation_builder import OBSERVATION_DIM

LEDGER_NAMES = {
    ("birth", "A"): "budget_birth_A_close_ledger.jsonl",
    ("birth", "B"): "budget_birth_B_close_ledger.jsonl",
    ("eyes", "A"): "budget_eyes_A_close_ledger.jsonl",
    ("eyes", "B"): "budget_eyes_B_close_ledger.jsonl",
}


def _write_jsonl_sha(path: Path) -> None:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    path.with_suffix(".sha256").write_text(digest.hexdigest() + "\n", encoding="utf-8")


def policy_obs_dim(policy: Any) -> int:
    space = getattr(policy, "observation_space", None)
    shape = getattr(space, "shape", None) if space is not None else None
    if not shape:
        return -1
    return int(shape[0])


def organism_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    winners = winners_from_u(universe)
    pol = bucket_stats(policy)
    held = bars_held_values(policy)
    return {
        "n_policy": int(len(policy)),
        "wr": float(pol["wr"]),
        "mean_r": float(pol["mean_r"]),
        "n_H": int(len(hole)),
        "n_W": int(len(winners)),
        "bars_held_p50": float(percentile(held, 50.0) or 0.0) if held else 0.0,
    }


def _assert_eval_ready(leg: str, zip_path: Path) -> None:
    if TRAIN:
        raise BudgetProtocolError("TRAIN must stay False")
    if str(leg) not in {"A", "B"}:
        raise BudgetProtocolError("seeds recorded as labels A/B only")
    refuse_path_early_baseline(zip_path)
    if zip_path.name not in {STUDENT_BIRTH_NAME, STUDENT_EYES_NAME}:
        raise BudgetProtocolError(f"refused PPO.load of non-student zip {zip_path.name}")
    if bool(PATH_EXIT_K3_SHADOW.get()) or bool(PATH_SHAPE_K3_SHADOW.get()):
        raise BudgetProtocolError("path_exit / path_shape hooks must stay False")


def eval_budget_leg(
    *,
    holdout: list[dict[str, Any]],
    work: Path,
    art: Path,
    zip_path: Path,
    organism: str,
    leg: str,
    expected_dim: int,
) -> dict[str, Any]:
    _assert_eval_ready(leg, zip_path)
    ledger = art / LEDGER_NAMES[(organism, leg)]
    loaded = load_frozen_policy(zip_path)
    if loaded is None:
        return {**organism_stats([]), "S_MISSING": True, "reason": "zip_unloadable"}
    dim = policy_obs_dim(loaded)
    if dim != int(expected_dim):
        return {**organism_stats([]), "S_MISSING": True, "reason": f"obs_dim {dim}!={expected_dim}"}
    rollout_fn = mark_eyes_gym_rollout if organism == "eyes" else None
    token_e = PATH_EXIT_K3_SHADOW.set(False)
    token_s = PATH_SHAPE_K3_SHADOW.set(False)
    try:
        run_evaluate_only(
            runtime=select_runtime(),
            holdout=list(holdout),
            workspace_root=work,
            reports_dir=art,
            ledger_path=ledger,
            policy=loaded,
            policy_path=zip_path,
            rollout_fn=rollout_fn,
            ledger_source=f"genesis_eyes_budget_{organism}_{leg}",
            path_exit_k3_shadow=False,
        )
    finally:
        PATH_SHAPE_K3_SHADOW.reset(token_s)
        PATH_EXIT_K3_SHADOW.reset(token_e)
    _write_jsonl_sha(ledger)
    rows = load_close_jsonl(ledger) if ledger.is_file() else []
    stats = organism_stats(rows)
    stats["S_MISSING"] = False
    stats["ledger"] = str(ledger)
    stats["n_rows"] = len(rows)
    stats["obs_dim"] = dim
    stats["train"] = bool(TRAIN)
    return stats


def run_budget_eval(*, work: Path, art: Path, holdout_pct: float) -> dict[str, Any]:
    if TRAIN:
        raise BudgetProtocolError("TRAIN flag False")
    split = load_split_cache(work, holdout_pct=float(holdout_pct))
    if split is None or not split.holdout:
        return {"S_MISSING": True, "reason": "holdout_missing"}
    refuse_path_early_baseline(None)
    leg_a, leg_b = split_holdout_ab(list(split.holdout))
    birth_zip = art / STUDENT_BIRTH_NAME
    eyes_zip = art / STUDENT_EYES_NAME
    birth_a = eval_budget_leg(
        holdout=leg_a, work=work, art=art, zip_path=birth_zip, organism="birth",
        leg="A", expected_dim=int(OBSERVATION_DIM),
    )
    birth_b = eval_budget_leg(
        holdout=leg_b, work=work, art=art, zip_path=birth_zip, organism="birth",
        leg="B", expected_dim=int(OBSERVATION_DIM),
    )
    eyes_a = eval_budget_leg(
        holdout=leg_a, work=work, art=art, zip_path=eyes_zip, organism="eyes",
        leg="A", expected_dim=int(MARK_EYES_OBS_DIM),
    )
    eyes_b = eval_budget_leg(
        holdout=leg_b, work=work, art=art, zip_path=eyes_zip, organism="eyes",
        leg="B", expected_dim=int(MARK_EYES_OBS_DIM),
    )
    missing = any(bool(x.get("S_MISSING")) for x in (birth_a, birth_b, eyes_a, eyes_b))
    return {
        "ticks_per_leg": [len(leg_a), len(leg_b)],
        "birth_A": birth_a,
        "birth_B": birth_b,
        "eyes_A": eyes_a,
        "eyes_B": eyes_b,
        "S_MISSING": missing,
        "used_old_path_early": False,
        "used_g5_halves_as_exam": False,
        "eval_seeds": ["A", "B"],
        "learn_called": False,
        "train": False,
        "hook_default": False,
    }


__all__ = ["eval_budget_leg", "organism_stats", "policy_obs_dim", "run_budget_eval"]
