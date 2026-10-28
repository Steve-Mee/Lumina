"""Gate 3: evaluate-only A then B on the 46-dim child. Parent baseline is path_early JSONL."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_mark_eyes import (
    EVAL_A_SEED,
    EVAL_B_SEED,
    SOURCE,
    MarkEyesProtocolError,
    assert_isolated_write,
    mark_eyes_ledger_path,
)
from lumina_core.birth.awakening_mark_eyes_env import make_mark_eyes_eval_env
from lumina_core.birth.awakening_select_env import select_runtime
from lumina_core.birth.birth_exit_policy_export import is_gitignored_ppo_zip, load_frozen_policy
from lumina_core.birth.sim_runner import SimRolloutResult
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.awakening_mark_eyes_eval")


def write_jsonl_sha256(path: Path) -> Path:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    sidecar = path.with_suffix(".sha256")
    sidecar.write_text(digest.hexdigest() + "\n", encoding="utf-8")
    return sidecar


def mark_eyes_gym_rollout(
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
    _ = runtime
    _ = target_trades
    from lumina_core.birth.awakening_select import reports_dir as default_reports

    rd = Path(reports_dir) if reports_dir is not None else default_reports()
    budget = int(rollout_step_budget or max_steps or len(data))
    env = make_mark_eyes_eval_env(
        list(data),
        workspace_root=workspace_root,
        reports_dir=rd,
        max_steps=budget,
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


def run_mark_eyes_eval_leg(
    *,
    seed: int,
    holdout: list[dict[str, Any]],
    workspace_root: Path | str,
    reports: Path,
    policy_path: Path,
    rollout_fn: Any | None = None,
) -> Any:
    if TRAIN:
        raise RuntimeError("mark eyes eval TRAIN must stay False")
    n = int(seed)
    if n not in {EVAL_A_SEED, EVAL_B_SEED}:
        raise MarkEyesProtocolError(f"eval seed must be A/B only, got {n}")
    if is_gitignored_ppo_zip(policy_path):
        raise MarkEyesProtocolError("eval refused gitignored ppo zip")
    loaded = load_frozen_policy(policy_path)
    if loaded is None:
        raise MarkEyesProtocolError(f"child policy unloadable: {policy_path}")
    ledger = assert_isolated_write(
        mark_eyes_ledger_path(reports, leg="A" if n == EVAL_A_SEED else "B")
    )
    metrics = run_evaluate_only(
        runtime=select_runtime(),
        holdout=list(holdout),
        workspace_root=workspace_root,
        reports_dir=reports,
        ledger_path=ledger,
        policy=loaded,
        policy_path=policy_path,
        rollout_fn=rollout_fn or mark_eyes_gym_rollout,
        ledger_source=SOURCE,
        path_exit_k3_shadow=False,
    )
    write_jsonl_sha256(ledger)
    return metrics


__all__ = ["mark_eyes_gym_rollout", "run_mark_eyes_eval_leg", "write_jsonl_sha256"]
