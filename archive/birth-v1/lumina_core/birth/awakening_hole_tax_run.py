"""One-shot Awakening hole-tax train + evaluate-only child grind.

Exactly one learn() at AWAKENING_HOLE_TAX_PPO_TIMESTEPS with tax_r=1.0.
Holdout B never trains. Does not overwrite parent or PR #20 child zips.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_hole_tax import (
    AWAKENING_HOLE_TAX_PPO_TIMESTEPS,
    AWAKENING_HOLE_TAX_R,
    STATUS_INCONCLUSIVE,
    TRAIN_SEED,
    HoleTaxProtocolError,
    assert_budget,
    assert_init_sha,
    assert_isolated_write,
    assert_not_holdout_b_path,
    assert_train_seed,
    child_meta_path,
    child_sidecar_payload,
    child_zip_path,
    isolated_workspace,
    reports_dir,
    resolve_hole_tax_init_path,
)
from lumina_core.birth.awakening_select_env import make_select_train_env
from lumina_core.birth.awakening_select_run import (
    _SelectEngine,
    _timestep_cap_callback,
    dump_learn_traceback,
    load_select_train_tape,
    run_select_eval_leg,
    select_leg_table,
)
from lumina_core.birth.birth_exit_policy_export import file_sha256
from lumina_core.logging_utils import get_logger
from lumina_core.rl.ppo_trainer import PPOTrainer

logger = get_logger("lumina.birth.awakening_hole_tax_run")


def load_hole_tax_train_tape(
    *,
    seed: int,
    workspace: Path,
    holdout_b_path: Path | str | None = None,
) -> dict[str, Any]:
    """Train loader. Seed 20260902 / 20260903 / holdout-B path raises."""
    assert_train_seed(seed)
    assert_not_holdout_b_path(holdout_b_path)
    assert_not_holdout_b_path(workspace)
    return load_select_train_tape(seed=int(seed), workspace=workspace, holdout_b_path=holdout_b_path)


def run_hole_tax_train(
    *,
    seed: int = TRAIN_SEED,
    timesteps: int = AWAKENING_HOLE_TAX_PPO_TIMESTEPS,
    workspace_root: Path | str | None = None,
    reports: Path | str | None = None,
    holdout_b_path: Path | str | None = None,
    learn_fn: Any | None = None,
    ppo_load_fn: Any | None = None,
    tax_r: float = AWAKENING_HOLE_TAX_R,
    train_reward_fn: Any | None = None,
) -> dict[str, Any]:
    """One learn() at the pin with the hole tax. Raises before learn on violations."""
    pin = assert_budget(int(timesteps))
    assert_train_seed(int(seed))
    assert_not_holdout_b_path(holdout_b_path)
    ws = isolated_workspace(workspace_root) if workspace_root is not None else isolated_workspace()
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "state").mkdir(parents=True, exist_ok=True)
    reports_path = Path(reports) if reports is not None else reports_dir()
    init_path = resolve_hole_tax_init_path(reports_path / "workspace")
    init_sha = assert_init_sha(init_path)
    tape = load_hole_tax_train_tape(seed=int(seed), workspace=ws, holdout_b_path=holdout_b_path)
    child = assert_isolated_write(child_zip_path(reports_path))
    meta = assert_isolated_write(child_meta_path(reports_path))
    env = make_select_train_env(
        list(tape["train"]),
        workspace_root=ws,
        reports_dir=reports_path,
        max_steps=max(pin, len(tape["train"])),
        tax_r=float(tax_r),
        train_reward_fn=train_reward_fn,
    )
    if ppo_load_fn is not None:
        model = ppo_load_fn(str(init_path), env=env, device="cpu")
    else:
        try:
            from stable_baselines3 import PPO
        except Exception as exc:
            raise HoleTaxProtocolError(f"PPO import failed: {exc}") from exc
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
        logger.error("awakening.hole_tax.learn_failed: %s", exc)
        raise HoleTaxProtocolError(f"{STATUS_INCONCLUSIVE}: learn() {exc}") from exc
    actual = int(getattr(model, "num_timesteps", 0) or 0)
    if actual > pin:
        raise HoleTaxProtocolError(f"trainer ran {actual} steps > pin {pin}")
    trainer.save_weights(str(child))
    if not child.is_file() or child.stat().st_size <= 0:
        raise HoleTaxProtocolError("child zip missing after save_weights")
    child_sha = file_sha256(child)
    noop = child_sha == init_sha
    payload = child_sidecar_payload(
        zip_path=child,
        init_path=init_path,
        train_ticks_sha16=str(tape["ticks_sha16"]),
        train_price_sha16=str(tape["price_sha16"]),
        timesteps=pin,
        train_seed=int(seed),
        actual_timesteps=actual,
        optimizer_steps=int(getattr(model, "_n_updates", 0) or 0),
        select_noop=bool(noop),
        hole_tax_r=float(tax_r),
    )
    meta.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "awakening.hole_tax.frozen child=%s sha16=%s noop=%s steps=%s tax_r=%s",
        child,
        child_sha[:16],
        noop,
        actual,
        tax_r,
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
        "hole_tax_r": float(tax_r),
        "sidecar": payload,
    }


__all__ = [
    "dump_learn_traceback",
    "load_hole_tax_train_tape",
    "run_hole_tax_train",
    "run_select_eval_leg",
    "select_leg_table",
]
