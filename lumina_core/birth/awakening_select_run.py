"""One-shot Awakening selection train + evaluate-only child grind.

Exactly one learn() at AWAKENING_SELECT_PPO_TIMESTEPS. Holdout B never trains.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any

from types import SimpleNamespace

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_mech import bucket_stats, split_close_rows
from lumina_core.birth.awakening_select import (
    AWAKENING_SELECT_PPO_TIMESTEPS,
    EVAL_A_SEED,
    EVAL_B_SEED,
    STATUS_INCONCLUSIVE,
    TRAIN_SEED,
    SelectProtocolError,
    assert_budget,
    assert_init_sha,
    assert_isolated_write,
    assert_not_holdout_b_path,
    assert_train_seed,
    child_meta_path,
    child_sidecar_payload,
    child_zip_path,
    isolated_workspace,
    price_sha16,
    reports_dir,
    resolve_select_init_path,
)
from lumina_core.birth.awakening_select_env import make_select_train_env, select_runtime
from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip, load_frozen_policy
from lumina_core.birth.synthetic_cloud_fixture import CloudFixtureSpec, persist_cloud_fixture
from lumina_core.birth.tick_cache_persist import compute_ticks_fingerprint
from lumina_core.logging_utils import get_logger
from lumina_core.rl.ppo_trainer import PPOTrainer

logger = get_logger("lumina.birth.awakening_select_run")


class _SelectEngine:
    def __init__(self, model: Any) -> None:
        self.rl_policy_model = model
        self.config = SimpleNamespace(trade_mode="sim", instrument="MES", risk_controller={})

    def set_rl_policy(self, model: Any) -> None:
        self.rl_policy_model = model


def load_select_train_tape(
    *,
    seed: int,
    workspace: Path,
    holdout_b_path: Path | str | None = None,
) -> dict[str, Any]:
    """Train loader. Seed 20260903 / holdout-B path raises. Prefers 20260901 only."""
    assert_train_seed(seed)
    assert_not_holdout_b_path(holdout_b_path)
    assert_not_holdout_b_path(workspace)
    spec = CloudFixtureSpec(seed=int(seed))
    result = persist_cloud_fixture(workspace, spec=spec)
    train = list(result.split.train)
    if not train:
        raise SelectProtocolError("train tape empty — SELECT_INCONCLUSIVE")
    return {
        "train": train,
        "ticks_sha16": str(result.fixture_manifest.get("hash") or compute_ticks_fingerprint(train)),
        "bars_sha16": str(result.fixture_manifest.get("raw_ticks_hash") or ""),
        "price_sha16": price_sha16(train),
        "manifest": dict(result.fixture_manifest),
    }


def _timestep_cap_callback(cap: int) -> Any:
    from stable_baselines3.common.callbacks import BaseCallback

    class _Cap(BaseCallback):
        def __init__(self, max_steps: int) -> None:
            super().__init__()
            self.max_steps = int(max_steps)

        def _on_step(self) -> bool:
            return int(self.num_timesteps) < self.max_steps

    return _Cap(cap)


def run_select_train(
    *,
    seed: int = TRAIN_SEED,
    timesteps: int = AWAKENING_SELECT_PPO_TIMESTEPS,
    workspace_root: Path | str | None = None,
    reports: Path | str | None = None,
    holdout_b_path: Path | str | None = None,
    learn_fn: Any | None = None,
) -> dict[str, Any]:
    """One learn() at the pin. Raises before learn on split/budget/init violations."""
    pin = assert_budget(int(timesteps))
    assert_train_seed(int(seed))
    assert_not_holdout_b_path(holdout_b_path)
    ws = isolated_workspace(workspace_root) if workspace_root is not None else isolated_workspace()
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "state").mkdir(parents=True, exist_ok=True)
    reports_path = Path(reports) if reports is not None else reports_dir()
    init_path = resolve_select_init_path(reports_path / "workspace")
    init_sha = assert_init_sha(init_path)
    tape = load_select_train_tape(seed=int(seed), workspace=ws, holdout_b_path=holdout_b_path)
    child = assert_isolated_write(child_zip_path(reports_path))
    meta = assert_isolated_write(child_meta_path(reports_path))
    env = make_select_train_env(
        list(tape["train"]),
        workspace_root=ws,
        reports_dir=reports_path,
        max_steps=max(pin, len(tape["train"])),
    )
    try:
        from stable_baselines3 import PPO
    except Exception as exc:
        raise SelectProtocolError(f"PPO import failed: {exc}") from exc
    model = PPO.load(str(init_path), env=env, device="cpu")
    engine = _SelectEngine(model)
    trainer = PPOTrainer(engine=engine, model_dir=ws / "ppo_out")
    engine.set_rl_policy(model)
    cap = _timestep_cap_callback(pin)
    try:
        if learn_fn is not None:
            learn_fn(total_timesteps=pin, reset_num_timesteps=True, callback=cap, progress_bar=False)
        else:
            model.learn(total_timesteps=pin, reset_num_timesteps=True, callback=cap, progress_bar=False)
    except Exception as exc:
        logger.error("awakening.select.learn_failed: %s", exc)
        raise SelectProtocolError(f"{STATUS_INCONCLUSIVE}: learn() {exc}") from exc
    actual = int(getattr(model, "num_timesteps", 0) or 0)
    if actual > pin:
        raise SelectProtocolError(f"trainer ran {actual} steps > pin {pin}")
    trainer.save_weights(str(child))
    if not child.is_file() or child.stat().st_size <= 0:
        raise SelectProtocolError("child zip missing after save_weights")
    child_sha = file_sha256(child)
    noop = child_sha == init_sha
    payload = child_sidecar_payload(
        zip_path=child,
        init_path=init_path,
        train_ticks_sha16=str(tape["ticks_sha16"]),
        train_price_sha16=str(tape["price_sha16"]),
        timesteps=pin,
        train_seed=int(seed),
    )
    payload["select_noop"] = bool(noop)
    payload["optimizer_steps"] = int(getattr(model, "_n_updates", 0) or 0)
    payload["actual_timesteps"] = actual
    meta.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "awakening.select.frozen child=%s sha16=%s noop=%s steps=%s",
        child,
        child_sha[:16],
        noop,
        actual,
    )
    return {
        "child_path": str(child),
        "child_sha256": child_sha,
        "init_sha256": init_sha,
        "select_noop": bool(noop),
        "actual_timesteps": actual,
        "optimizer_steps": payload["optimizer_steps"],
        "train_ticks_sha16": tape["ticks_sha16"],
        "train_price_sha16": tape["price_sha16"],
        "train_bars_sha16": tape["bars_sha16"],
        "sidecar": payload,
    }


def run_select_eval_leg(
    *,
    holdout: list[dict[str, Any]],
    workspace_root: Path | str,
    reports_dir: Path,
    ledger_path: Path,
    policy_path: Path,
    rollout_fn: Any | None = None,
) -> Any:
    if TRAIN:
        raise RuntimeError("select eval TRAIN must stay False")
    if is_gitignored_ppo_zip(policy_path):
        raise SelectProtocolError("eval refused gitignored ppo zip")
    loaded = load_frozen_policy(policy_path)
    if loaded is None:
        raise SelectProtocolError(f"child policy unloadable: {policy_path}")
    return run_evaluate_only(
        runtime=select_runtime(),
        holdout=list(holdout),
        workspace_root=workspace_root,
        reports_dir=reports_dir,
        ledger_path=ledger_path,
        policy=loaded,
        policy_path=policy_path,
        rollout_fn=rollout_fn,
    )


def _reason_regime_cell(rows: list[dict[str, Any]], reason: str, regime: str) -> dict[str, float]:
    cell = [
        r
        for r in rows
        if str(r.get("close_reason") or "") == reason and str(r.get("regime") or "") == regime
    ]
    return bucket_stats(cell)


def select_leg_table(
    rows: list[dict[str, Any]],
    *,
    grind_metrics: Any,
    ticks_sha16: str,
    bars_sha16: str,
    price_sha16_value: str,
    frozen_sha256: str,
) -> dict[str, Any]:
    parts = split_close_rows(rows)
    policy = parts["policy"]
    all_stats = bucket_stats(parts["all"])
    pol_stats = bucket_stats(policy)
    stop_n = _reason_regime_cell(policy, "stop", "NEUTRAL")
    targets = [r for r in policy if str(r.get("close_reason") or "") == "target"]
    times = [r for r in policy if str(r.get("close_reason") or "") == "time_stop"]
    return {
        "n": int(all_stats["n"]),
        "wr_all": float(all_stats["wr"]),
        "wr_policy": float(pol_stats["wr"]),
        "mean_usd_all": float(all_stats["mean_usd"]),
        "mean_usd_policy": float(pol_stats["mean_usd"]),
        "mean_r_policy": float(pol_stats["mean_r"]),
        "sharpe": float(grind_metrics.oos_sharpe),
        "dd_pct_of_50k": float(grind_metrics.oos_dd_pct),
        "occ": grind_metrics.occupancy,
        "plant_n": int(len(parts["plant"])),
        "force_open_closes": int(len(parts["force_open"])),
        "FORCE_OPEN_bars": int(grind_metrics.force_open),
        "exits": {
            "stop": int(all_stats["stop"]),
            "target": int(all_stats["target"]),
            "time_stop": int(all_stats["time_stop"]),
        },
        "stop_x_neutral": {
            "n": int(stop_n["n"]),
            "mean_r": float(stop_n["mean_r"]),
            "mean_usd": float(stop_n["mean_usd"]),
        },
        "target_mean_r": float(bucket_stats(targets)["mean_r"]),
        "time_stop_mean_r": float(bucket_stats(times)["mean_r"]),
        "classification": str(grind_metrics.classification),
        "ticks_sha16": ticks_sha16,
        "bars_sha16": bars_sha16,
        "price_sha16": price_sha16_value,
        "frozen_sha256": frozen_sha256,
        "optimizer_steps": 0,
        "train": False,
    }


def dump_learn_traceback(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


__all__ = [
    "dump_learn_traceback",
    "load_select_train_tape",
    "run_select_eval_leg",
    "run_select_train",
    "select_leg_table",
    "EVAL_A_SEED",
    "EVAL_B_SEED",
]
