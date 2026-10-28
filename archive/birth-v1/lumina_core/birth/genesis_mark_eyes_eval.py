"""G5: evaluate-only A/B on THIS fixture holdout. Birth zip 43-dim vs MARK_EYES 46-dim."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_mark_eyes_eval import mark_eyes_gym_rollout
from lumina_core.birth.awakening_mark_eyes_flags import hole_moved_leg
from lumina_core.birth.awakening_mech import bucket_stats
from lumina_core.birth.awakening_open_split_flags import hole_from_u, universe_rows
from lumina_core.birth.awakening_path_exit_k3 import load_close_jsonl
from lumina_core.birth.awakening_select_env import select_runtime
from lumina_core.birth.genesis_cloud_const import (
    G5_BIRTH_ONLY,
    G5_EYES_FAIL,
    G5_EYES_OK,
    G5_S_MISSING,
    GENESIS_HOLDOUT_PCT,
    SKIP_BIRTH_INCOMPLETE,
)
from lumina_core.birth.tick_cache_persist import load_split_cache


def split_holdout_ab(holdout: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """First 50% / last 50% of holdout ticks in purged calendar order."""
    n = len(holdout)
    mid = n // 2
    return list(holdout[:mid]), list(holdout[mid:])


def _write_jsonl_sha(path: Path) -> None:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    path.with_suffix(".sha256").write_text(digest.hexdigest() + "\n", encoding="utf-8")


def _leg_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from lumina_core.birth.awakening_edge import policy_only_rows

    policy = policy_only_rows(rows)
    universe = universe_rows(policy)
    hole = hole_from_u(universe)
    pol = bucket_stats(policy)
    return {
        "n_policy": int(len(policy)),
        "wr_policy": float(pol["wr"]),
        "mean_r_policy": float(pol["mean_r"]),
        "n_H": int(len(hole)),
    }


def _eval_leg(
    *,
    holdout: list[dict[str, Any]],
    work: Path,
    art: Path,
    ledger: Path,
    policy_path: Path,
    rollout_fn: Any | None,
    source: str,
) -> dict[str, Any]:
    run_evaluate_only(
        runtime=select_runtime(),
        holdout=list(holdout),
        workspace_root=work,
        reports_dir=art,
        ledger_path=ledger,
        policy_path=policy_path,
        rollout_fn=rollout_fn,
        ledger_source=source,
        path_exit_k3_shadow=False,
    )
    _write_jsonl_sha(ledger)
    rows = load_close_jsonl(ledger) if ledger.is_file() else []
    stats = _leg_stats(rows)
    stats["ledger"] = str(ledger)
    stats["n_rows"] = len(rows)
    return stats


def license_genesis_eyes(
    *,
    eyes_a: dict[str, Any],
    eyes_b: dict[str, Any],
    birth_a: dict[str, Any],
    birth_b: dict[str, Any],
    learn_called: bool,
    actual_timesteps: int,
) -> dict[str, Any]:
    if not learn_called or int(actual_timesteps) <= 0:
        return {"G5_tag": G5_S_MISSING, "HOLE_MOVED_A": False, "HOLE_MOVED_B": False}
    moved_a = hole_moved_leg(
        n_h_child=int(eyes_a.get("n_H") or 0),
        n_h_base=int(birth_a.get("n_H") or 0),
        mean_r_child=float(eyes_a.get("mean_r_policy") or 0.0),
        mean_r_base=float(birth_a.get("mean_r_policy") or 0.0),
        n_policy_child=int(eyes_a.get("n_policy") or 0),
    )
    moved_b = hole_moved_leg(
        n_h_child=int(eyes_b.get("n_H") or 0),
        n_h_base=int(birth_b.get("n_H") or 0),
        mean_r_child=float(eyes_b.get("mean_r_policy") or 0.0),
        mean_r_base=float(birth_b.get("mean_r_policy") or 0.0),
        n_policy_child=int(eyes_b.get("n_policy") or 0),
    )
    tag = G5_EYES_OK if (moved_a and moved_b) else G5_EYES_FAIL
    return {
        "G5_tag": tag,
        "HOLE_MOVED_A": bool(moved_a),
        "HOLE_MOVED_B": bool(moved_b),
        "delta_n_H_A": int(birth_a.get("n_H") or 0) - int(eyes_a.get("n_H") or 0),
        "delta_mean_r_A": float(eyes_a.get("mean_r_policy") or 0.0) - float(birth_a.get("mean_r_policy") or 0.0),
        "delta_n_H_B": int(birth_b.get("n_H") or 0) - int(eyes_b.get("n_H") or 0),
        "delta_mean_r_B": float(eyes_b.get("mean_r_policy") or 0.0) - float(birth_b.get("mean_r_policy") or 0.0),
    }


def run_genesis_eval(
    *,
    work: Path,
    art: Path,
    newborn_zip: Path | None,
    eyes_zip: Path | None,
    learn_called: bool,
    actual_timesteps: int,
    skip_reason: str = "",
) -> dict[str, Any]:
    if skip_reason == SKIP_BIRTH_INCOMPLETE:
        payload = {"G5_tag": G5_BIRTH_ONLY, "skip_reason": skip_reason}
        (art / "g5_eval.json").write_text(json.dumps(payload, indent=2) + "\n")
        return payload
    split = load_split_cache(work, holdout_pct=GENESIS_HOLDOUT_PCT)
    if split is None or not split.holdout:
        payload = {"G5_tag": G5_BIRTH_ONLY, "skip_reason": "holdout_missing"}
        (art / "g5_eval.json").write_text(json.dumps(payload, indent=2) + "\n")
        return payload
    leg_a, leg_b = split_holdout_ab(list(split.holdout))
    birth_a: dict[str, Any] = {}
    birth_b: dict[str, Any] = {}
    if newborn_zip is not None and newborn_zip.is_file():
        birth_a = _eval_leg(
            holdout=leg_a,
            work=work,
            art=art,
            ledger=art / "genesis_birth_A_close_ledger.jsonl",
            policy_path=newborn_zip,
            rollout_fn=None,
            source="genesis_birth_eval",
        )
        birth_b = _eval_leg(
            holdout=leg_b,
            work=work,
            art=art,
            ledger=art / "genesis_birth_B_close_ledger.jsonl",
            policy_path=newborn_zip,
            rollout_fn=None,
            source="genesis_birth_eval",
        )
    eyes_a: dict[str, Any] = {}
    eyes_b: dict[str, Any] = {}
    if eyes_zip is not None and eyes_zip.is_file() and learn_called and actual_timesteps > 0:
        eyes_a = _eval_leg(
            holdout=leg_a,
            work=work,
            art=art,
            ledger=art / "genesis_mark_eyes_A_close_ledger.jsonl",
            policy_path=eyes_zip,
            rollout_fn=mark_eyes_gym_rollout,
            source="genesis_mark_eyes_eval",
        )
        eyes_b = _eval_leg(
            holdout=leg_b,
            work=work,
            art=art,
            ledger=art / "genesis_mark_eyes_B_close_ledger.jsonl",
            policy_path=eyes_zip,
            rollout_fn=mark_eyes_gym_rollout,
            source="genesis_mark_eyes_eval",
        )
        licensed = license_genesis_eyes(
            eyes_a=eyes_a,
            eyes_b=eyes_b,
            birth_a=birth_a or {"n_H": 0, "mean_r_policy": 0.0, "n_policy": 0},
            birth_b=birth_b or {"n_H": 0, "mean_r_policy": 0.0, "n_policy": 0},
            learn_called=learn_called,
            actual_timesteps=actual_timesteps,
        )
    elif not learn_called or actual_timesteps <= 0:
        licensed = {"G5_tag": G5_S_MISSING, "HOLE_MOVED_A": False, "HOLE_MOVED_B": False}
    else:
        licensed = {"G5_tag": G5_BIRTH_ONLY, "HOLE_MOVED_A": False, "HOLE_MOVED_B": False}
    payload = {
        "holdout_a_ticks": len(leg_a),
        "holdout_b_ticks": len(leg_b),
        "birth_A": birth_a,
        "birth_B": birth_b,
        "eyes_A": eyes_a,
        "eyes_B": eyes_b,
        "baseline_present": bool(birth_a and birth_b),
        **licensed,
        "used_old_path_early": False,
        "eval_seeds_20260902_20260903": False,
    }
    (art / "g5_eval.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return payload


__all__ = ["license_genesis_eyes", "run_genesis_eval", "split_holdout_ab"]
