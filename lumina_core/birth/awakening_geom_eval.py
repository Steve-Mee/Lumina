"""G2/G4 evaluate-only: frozen a9ffa852 then scratch V1 child. FORCE_OPEN off."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_geom_flags import SOURCE
from lumina_core.birth.awakening_geom_reward import GeomProtocolError
from lumina_core.birth.awakening_geom_tape import BASELINE_ZIP_NAME, CHILD_ZIP_NAME
from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_mark_eyes_eval import mark_eyes_gym_rollout
from lumina_core.birth.awakening_obj_eval import organism_stats, policy_obs_dim
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW, load_close_jsonl
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_select_env import select_runtime
from lumina_core.birth.awakening_strat_split import STRAT_HOLD_PCT
from lumina_core.birth.birth_exit_policy_export import load_frozen_policy
from lumina_core.birth.genesis_mark_eyes_eval import split_holdout_ab
from lumina_core.birth.tick_cache_persist import load_split_cache

LEDGER_NAMES = {
    ("base", "A"): "geom_base_A_close_ledger.jsonl",
    ("base", "B"): "geom_base_B_close_ledger.jsonl",
    ("child", "A"): "geom_child_A_close_ledger.jsonl",
    ("child", "B"): "geom_child_B_close_ledger.jsonl",
}


def _write_jsonl_sha(path: Path) -> None:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    path.with_suffix(".sha256").write_text(digest.hexdigest() + "\n", encoding="utf-8")


def _assert_eval_ready(leg: str, zip_path: Path, kind: str) -> None:
    if TRAIN:
        raise GeomProtocolError("TRAIN must stay False")
    if str(leg) not in {"A", "B"}:
        raise GeomProtocolError("seeds recorded as labels A/B only")
    if zip_path.name == "awakening_mark_eyes_v2_pi_star.zip":
        raise GeomProtocolError("used_v2_child is forbidden")
    allowed = {BASELINE_ZIP_NAME} if kind == "base" else {CHILD_ZIP_NAME}
    if zip_path.name not in allowed:
        raise GeomProtocolError(f"refused PPO.load of non-geom zip {zip_path.name}")
    if bool(PATH_EXIT_K3_SHADOW.get()) or bool(PATH_SHAPE_K3_SHADOW.get()):
        raise GeomProtocolError("path_exit / path_shape hooks must stay False")


def eval_geom_leg(
    *,
    holdout: list[dict[str, Any]],
    work: Path,
    art: Path,
    zip_path: Path,
    kind: str,
    leg: str,
) -> dict[str, Any]:
    _assert_eval_ready(leg, zip_path, kind)
    ledger = art / LEDGER_NAMES[(kind, leg)]
    loaded = load_frozen_policy(zip_path)
    if loaded is None:
        return {**organism_stats([]), "S_MISSING": True, "reason": "zip_unloadable"}
    dim = policy_obs_dim(loaded)
    if dim != int(MARK_EYES_OBS_DIM):
        return {**organism_stats([]), "S_MISSING": True, "reason": f"obs_dim {dim}!=46"}
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
            rollout_fn=mark_eyes_gym_rollout,
            ledger_source=f"{SOURCE}_{kind}_{leg}",
            path_exit_k3_shadow=False,
        )
    finally:
        PATH_SHAPE_K3_SHADOW.reset(token_s)
        PATH_EXIT_K3_SHADOW.reset(token_e)
    if not ledger.is_file():
        ledger.write_text("", encoding="utf-8")
    _write_jsonl_sha(ledger)
    rows = load_close_jsonl(ledger) if ledger.is_file() else []
    stats = organism_stats(rows)
    stats.update(
        {
            "S_MISSING": False,
            "ledger": str(ledger),
            "n_rows": len(rows),
            "obs_dim": dim,
            "train": bool(TRAIN),
            "eval_force_open": False,
            "use_geom_close_reward": False,
        }
    )
    return stats


def run_geom_eval(
    *,
    work: Path,
    art: Path,
    zip_path: Path,
    kind: str,
    holdout_pct: float = STRAT_HOLD_PCT,
) -> dict[str, Any]:
    if TRAIN:
        raise GeomProtocolError("TRAIN flag False")
    if kind not in {"base", "child"}:
        raise GeomProtocolError("kind must be base or child")
    split = load_split_cache(work, holdout_pct=float(holdout_pct))
    if split is None or not split.holdout:
        return {"S_MISSING": True, "reason": "holdout_missing"}
    leg_a, leg_b = split_holdout_ab(list(split.holdout))
    book_a = eval_geom_leg(holdout=leg_a, work=work, art=art, zip_path=zip_path, kind=kind, leg="A")
    book_b = eval_geom_leg(holdout=leg_b, work=work, art=art, zip_path=zip_path, kind=kind, leg="B")
    missing = bool(book_a.get("S_MISSING")) or bool(book_b.get("S_MISSING"))
    reasons = [str(x.get("reason") or "") for x in (book_a, book_b) if x.get("S_MISSING")]
    return {
        "ticks_per_leg": [len(leg_a), len(leg_b)],
        "A": book_a,
        "B": book_b,
        "S_MISSING": missing,
        "reason": "; ".join(r for r in reasons if r),
        "both_loaded": (not bool(book_a.get("S_MISSING"))) and (not bool(book_b.get("S_MISSING"))),
        "used_v2_child": False,
        "eval_seeds": ["A", "B"],
        "learn_called": False,
        "train": False,
        "hook_default": False,
        "eval_force_open": False,
        "use_geom_close_reward": False,
        "kind": kind,
    }


__all__ = ["eval_geom_leg", "run_geom_eval"]
