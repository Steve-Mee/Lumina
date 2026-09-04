"""Gate 2: one scratch PPO.learn() of 10_000 env steps on TRAIN seed 20260901."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_mark_eyes import (
    MARK_EYES_PPO_TIMESTEPS,
    TRAIN_SEED,
    MarkEyesProtocolError,
    assert_budget,
    assert_forbidden_init,
    assert_isolated_write,
    assert_not_holdout_b_path,
    assert_train_seed,
    child_meta_path,
    child_sidecar_payload,
    child_zip_path,
    isolated_workspace,
    reports_dir,
)
from lumina_core.birth.awakening_mark_eyes_env import make_mark_eyes_train_env
from lumina_core.birth.awakening_select_run import (
    _SelectEngine,
    _timestep_cap_callback,
    dump_learn_traceback,
    load_select_train_tape,
)
from lumina_core.birth.birth_exit_policy_export import file_sha256
from lumina_core.logging_utils import get_logger
from lumina_core.rl.ppo_trainer import PPOTrainer

logger = get_logger("lumina.birth.awakening_mark_eyes_train")


def run_mark_eyes_train(
    *,
    seed: int = TRAIN_SEED,
    timesteps: int = MARK_EYES_PPO_TIMESTEPS,
    workspace_root: Path | str | None = None,
    reports: Path | str | None = None,
    holdout_b_path: Path | str | None = None,
    init_zip: Path | str | None = None,
    learn_fn: Any | None = None,
    ppo_cls: Any | None = None,
) -> dict[str, Any]:
    """One learn() at the pin. Scratch PPO. Raises before learn on protocol violations."""
    if init_zip is not None:
        assert_forbidden_init(init_zip)
        raise MarkEyesProtocolError("init_policy must be scratch")
    pin = assert_budget(int(timesteps))
    assert_train_seed(int(seed))
    assert_not_holdout_b_path(holdout_b_path)
    ws = isolated_workspace(workspace_root) if workspace_root is not None else isolated_workspace()
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "state").mkdir(parents=True, exist_ok=True)
    reports_path = Path(reports) if reports is not None else reports_dir()
    tape = load_select_train_tape(seed=int(seed), workspace=ws, holdout_b_path=holdout_b_path)
    child = assert_isolated_write(child_zip_path(reports_path))
    meta = assert_isolated_write(child_meta_path(reports_path))
    env = make_mark_eyes_train_env(
        list(tape["train"]),
        workspace_root=ws,
        reports_dir=reports_path,
        max_steps=max(pin, len(tape["train"])),
        tax_r=0.0,
        train_reward_fn=None,
    )
    try:
        cls = ppo_cls
        if cls is None:
            from stable_baselines3 import PPO

            cls = PPO
        model = cls(
            "MlpPolicy",
            env,
            verbose=0,
            device="cpu",
            learning_rate=3e-4,
            n_steps=1024,
            batch_size=256,
            gamma=0.995,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            vf_coef=0.5,
        )
    except MarkEyesProtocolError:
        raise
    except Exception as exc:
        raise MarkEyesProtocolError(f"scratch PPO construct failed: {exc}") from exc
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
        logger.error("awakening.mark_eyes.learn_failed: %s", exc)
        raise MarkEyesProtocolError(f"S_MISSING: learn() {exc}") from exc
    actual = int(getattr(model, "num_timesteps", 0) or 0)
    if actual <= 0:
        raise MarkEyesProtocolError("S_MISSING: actual_timesteps == 0")
    if actual > pin:
        raise MarkEyesProtocolError(f"trainer ran {actual} steps > pin {pin}")
    trainer.save_weights(str(child))
    if not child.is_file() or child.stat().st_size <= 0:
        raise MarkEyesProtocolError("child zip missing after save_weights")
    child_sha = file_sha256(child)
    payload = child_sidecar_payload(
        zip_path=child,
        train_ticks_sha16=str(tape["ticks_sha16"]),
        timesteps=pin,
        train_seed=int(seed),
        actual_timesteps=actual,
        optimizer_steps=int(getattr(model, "_n_updates", 0) or 0),
    )
    meta.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "awakening.mark_eyes.frozen child=%s sha16=%s steps=%s init=scratch",
        child,
        child_sha[:16],
        actual,
    )
    return {
        "child_path": str(child),
        "child_sha256": child_sha,
        "init_policy": "scratch",
        "actual_timesteps": actual,
        "optimizer_steps": payload["optimizer_steps"],
        "train_ticks_sha16": tape["ticks_sha16"],
        "train_price_sha16": tape["price_sha16"],
        "train_bars_sha16": tape["bars_sha16"],
        "sidecar": payload,
        "learn_called": True,
    }


__all__ = ["dump_learn_traceback", "run_mark_eyes_train"]
