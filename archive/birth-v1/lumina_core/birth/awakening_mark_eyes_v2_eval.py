"""G2/G4 evaluate-only: frozen a9ffa852 (46) then V2 child (48) on THIS tape A/B."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_mark_eyes_eval import mark_eyes_gym_rollout
from lumina_core.birth.awakening_mark_eyes_v2 import (
    BASELINE_ZIP_NAME,
    CHILD_ZIP_NAME,
    MARK_EYES_V2_OBS_DIM,
    SOURCE,
    V2_HOLDOUT_PCT,
    MarkEyesV2ProtocolError,
    refuse_old_baseline,
)
from lumina_core.birth.awakening_mark_eyes_v2_env import make_mark_eyes_v2_eval_env
from lumina_core.birth.awakening_mech import bucket_stats
from lumina_core.birth.awakening_open_split_flags import hole_from_u, universe_rows, winners_from_u
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW, load_close_jsonl
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_select_env import select_runtime
from lumina_core.birth.birth_exit_policy_export import load_frozen_policy
from lumina_core.birth.genesis_hold_compare import bars_held_values, percentile
from lumina_core.birth.genesis_mark_eyes_eval import split_holdout_ab
from lumina_core.birth.sim_runner import SimRolloutResult
from lumina_core.birth.tick_cache_persist import load_split_cache

LEDGER_NAMES = {
    ("base", "A"): "v2_base_A_close_ledger.jsonl",
    ("base", "B"): "v2_base_B_close_ledger.jsonl",
    ("child", "A"): "v2_child_A_close_ledger.jsonl",
    ("child", "B"): "v2_child_B_close_ledger.jsonl",
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


def mark_eyes_v2_gym_rollout(
    *,
    runtime: Any,
    data: list[dict[str, Any]],
    policy: Any,
    workspace_root: Path | str,
    reports_dir: Path | str | None = None,
    max_steps: int | None = None,
    rollout_step_budget: int | None = None,
    target_trades: int = 0,
    **_kwargs: Any,
) -> SimRolloutResult:
    _ = runtime, target_trades
    from lumina_core.birth.awakening_select import reports_dir as default_reports

    rd = Path(reports_dir) if reports_dir is not None else default_reports()
    budget = int(rollout_step_budget or max_steps or len(data))
    env = make_mark_eyes_v2_eval_env(
        list(data), workspace_root=workspace_root, reports_dir=rd, max_steps=budget
    )
    reset_out = env.reset()
    obs = reset_out[0] if isinstance(reset_out, tuple) else reset_out
    trajectories: list[dict[str, Any]] = []
    pnl_series: list[float] = []
    steps = 0
    try:
        while steps < budget:
            raw = policy.predict(obs, deterministic=True)
            action = raw[0] if isinstance(raw, (tuple, list)) and raw else raw
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            if bool((info or {}).get("trade_closed")):
                pnl = float(info.get("rl_close_accounting_net_usd") or info.get("pnl") or 0.0)
                trajectories.append(
                    {
                        "pnl": pnl,
                        "reward": float(reward),
                        "reward_on_close": float(reward),
                        "trade_r": info.get("trade_r"),
                        "qty": info.get("qty"),
                        "risk_usd": info.get("risk_usd"),
                        "regime": str(info.get("regime") or "NEUTRAL"),
                        "close_regime": str(info.get("regime") or "NEUTRAL"),
                        "close_reason": info.get("close_reason"),
                        "plant_entry": bool(info.get("plant_entry") or info.get("plant")),
                        "plant": bool(info.get("plant_entry") or info.get("plant")),
                        "force_open": bool(info.get("force_open") or info.get("plant_entry")),
                        "cap_usd": info.get("cap_usd"),
                        "gap": info.get("gap"),
                        "entry_price": info.get("entry_price"),
                        "point_value": info.get("point_value"),
                        "entry_regime": str(info.get("entry_regime") or "NEUTRAL"),
                        "entry_bar_index": info.get("entry_bar_index"),
                        "bars_held": info.get("bars_held"),
                    }
                )
                pnl_series.append(pnl)
            if terminated or truncated:
                break
    finally:
        env.close()
    return SimRolloutResult(
        trades=len(trajectories),
        wins=sum(1 for p in pnl_series if p > 0),
        hold_signals=0,
        total_signals=steps,
        total_pnl=float(sum(pnl_series)),
        trajectories=trajectories,
        pnl_series=pnl_series,
        constitution_violations=0,
        regimes_seen=set(),
        rollout_steps=steps,
    )


def _assert_eval_ready(leg: str, zip_path: Path, kind: str) -> None:
    if TRAIN:
        raise MarkEyesV2ProtocolError("TRAIN must stay False")
    if str(leg) not in {"A", "B"}:
        raise MarkEyesV2ProtocolError("seeds recorded as labels A/B only")
    refuse_old_baseline(zip_path)
    allowed = {BASELINE_ZIP_NAME} if kind == "base" else {CHILD_ZIP_NAME}
    if zip_path.name not in allowed:
        raise MarkEyesV2ProtocolError(f"refused PPO.load of non-v2 zip {zip_path.name}")
    if bool(PATH_EXIT_K3_SHADOW.get()) or bool(PATH_SHAPE_K3_SHADOW.get()):
        raise MarkEyesV2ProtocolError("path_exit / path_shape hooks must stay False")


def eval_v2_leg(
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
    expected = int(MARK_EYES_OBS_DIM) if kind == "base" else int(MARK_EYES_V2_OBS_DIM)
    if dim != expected:
        return {**organism_stats([]), "S_MISSING": True, "reason": f"obs_dim {dim}!={expected}"}
    rollout = mark_eyes_gym_rollout if kind == "base" else mark_eyes_v2_gym_rollout
    source = f"{SOURCE}_{kind}_{leg}"
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
            rollout_fn=rollout,
            ledger_source=source,
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


def run_v2_eval(
    *,
    work: Path,
    art: Path,
    zip_path: Path,
    kind: str,
    holdout_pct: float = V2_HOLDOUT_PCT,
) -> dict[str, Any]:
    if TRAIN:
        raise MarkEyesV2ProtocolError("TRAIN flag False")
    if kind not in {"base", "child"}:
        raise MarkEyesV2ProtocolError("kind must be base or child")
    split = load_split_cache(work, holdout_pct=float(holdout_pct))
    if split is None or not split.holdout:
        return {"S_MISSING": True, "reason": "holdout_missing"}
    refuse_old_baseline(None)
    leg_a, leg_b = split_holdout_ab(list(split.holdout))
    book_a = eval_v2_leg(holdout=leg_a, work=work, art=art, zip_path=zip_path, kind=kind, leg="A")
    book_b = eval_v2_leg(holdout=leg_b, work=work, art=art, zip_path=zip_path, kind=kind, leg="B")
    missing = bool(book_a.get("S_MISSING")) or bool(book_b.get("S_MISSING"))
    reasons = [str(x.get("reason") or "") for x in (book_a, book_b) if x.get("S_MISSING")]
    return {
        "ticks_per_leg": [len(leg_a), len(leg_b)],
        "A": book_a,
        "B": book_b,
        "S_MISSING": missing,
        "reason": "; ".join(r for r in reasons if r),
        "both_loaded": (not bool(book_a.get("S_MISSING"))) and (not bool(book_b.get("S_MISSING"))),
        "used_old_path_early": False,
        "eval_seeds": ["A", "B"],
        "learn_called": False,
        "train": False,
        "hook_default": False,
        "kind": kind,
    }


__all__ = ["eval_v2_leg", "mark_eyes_v2_gym_rollout", "organism_stats", "policy_obs_dim", "run_v2_eval"]
