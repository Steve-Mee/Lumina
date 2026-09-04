"""G4: scratch V1 PPO.learn() of 10_000 env steps. Reuses FORCE_OPEN train factory."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_drift_tape import (
    BASELINE_SHA256,
    CHILD_META_NAME,
    CHILD_SCHEMA,
    CHILD_ZIP_NAME,
    DRIFT_SEEDS,
    DRIFT_TIMESTEPS,
    DriftProtocolError,
    assert_forbidden_init,
    load_drift_train_split,
)
from lumina_core.birth.awakening_mark_eyes import EXTRA_SLOT_NAMES, MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_mark_eyes_env import make_mark_eyes_train_env
from lumina_core.birth.awakening_occupancy_tape import write_bytes_sha
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_select_run import _SelectEngine, _timestep_cap_callback
from lumina_core.logging_utils import get_logger
from lumina_core.rl.ppo_trainer import PPOTrainer

logger = get_logger("lumina.birth.awakening_drift_train")


def pin_train_seed(seed: int) -> None:
    if int(seed) not in DRIFT_SEEDS:
        raise DriftProtocolError(f"train seed {seed} not in {DRIFT_SEEDS}")
    random.seed(int(seed))
    try:
        import numpy as np

        np.random.seed(int(seed))
    except Exception:
        pass
    try:
        import torch

        torch.manual_seed(int(seed))
    except Exception:
        pass


def _obs_shape(obj: Any) -> tuple[int, ...]:
    space = getattr(obj, "observation_space", None)
    shape = getattr(space, "shape", None) if space is not None else None
    return tuple(int(x) for x in shape) if shape else ()


def _fail(**kwargs: Any) -> dict[str, Any]:
    out = {
        "status": "S_MISSING",
        "learn_called": False,
        "actual_timesteps": 0,
        "child_sha256": "",
        "init_policy": "scratch",
        "train_force_open": True,
        "eval_force_open": False,
    }
    out.update(kwargs)
    return out


def run_drift_v1_train(
    *,
    work: Path,
    art: Path,
    train_seed: int,
    init_zip: Path | str | None = None,
    timesteps: int = DRIFT_TIMESTEPS,
    learn_fn: Any | None = None,
    ppo_cls: Any | None = None,
) -> dict[str, Any]:
    if init_zip is not None:
        assert_forbidden_init(init_zip)
        raise DriftProtocolError("init_policy must be scratch")
    if int(timesteps) != int(DRIFT_TIMESTEPS):
        raise DriftProtocolError(f"timesteps {timesteps} != {DRIFT_TIMESTEPS}")
    if bool(PATH_EXIT_K3_SHADOW.get()) or bool(PATH_SHAPE_K3_SHADOW.get()):
        raise DriftProtocolError("hooks must stay False")
    pin_train_seed(int(train_seed))
    tape = load_drift_train_split(work)
    train = list(tape["train"])
    if not train:
        raise DriftProtocolError("TRAIN split empty — refuse holdout ticks")
    env = make_mark_eyes_train_env(
        train,
        workspace_root=work,
        reports_dir=art,
        max_steps=max(int(timesteps), len(train)),
        tax_r=0.0,
        train_reward_fn=None,
        force_open=True,
    )
    if not bool(env.env.envelope.get("participation_envelope_enabled")):
        raise DriftProtocolError("FORCE_OPEN train envelope failed to arm")
    if _obs_shape(env) != (int(MARK_EYES_OBS_DIM),):
        raise DriftProtocolError(f"env observation space {_obs_shape(env)} != (46,)")
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
            seed=int(train_seed),
            learning_rate=3e-4,
            n_steps=1024,
            batch_size=256,
            gamma=0.995,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            vf_coef=0.5,
        )
    except DriftProtocolError:
        raise
    except Exception as exc:
        logger.error("awakening.drift.sb3_missing: %s", exc)
        return _fail(error=f"S_MISSING: {exc}")
    setter = getattr(model, "set_random_seed", None)
    if callable(setter):
        setter(int(train_seed))
    engine = _SelectEngine(model)
    trainer = PPOTrainer(engine=engine, model_dir=work / "ppo_out")
    engine.set_rl_policy(model)
    cap = _timestep_cap_callback(int(timesteps))
    try:
        if learn_fn is not None:
            learn_fn(total_timesteps=int(timesteps), reset_num_timesteps=True, callback=cap, progress_bar=False)
        else:
            model.learn(total_timesteps=int(timesteps), reset_num_timesteps=True, callback=cap, progress_bar=False)
    except Exception as exc:
        logger.error("awakening.drift.learn_failed: %s", exc)
        return _fail(error=f"S_MISSING: learn() {exc}")
    actual = int(getattr(model, "num_timesteps", 0) or 0)
    if actual <= 0:
        return _fail(
            learn_called=True, error="S_MISSING: actual_timesteps == 0 — do not relabel a9ffa852 as drift child"
        )
    child = art / CHILD_ZIP_NAME
    trainer.save_weights(str(child))
    if not child.is_file() or child.stat().st_size <= 0:
        return _fail(learn_called=True, actual_timesteps=actual, error="S_MISSING: child zip missing after save")
    child_sha = write_bytes_sha(child)
    if child_sha == BASELINE_SHA256:
        return _fail(
            learn_called=True,
            actual_timesteps=actual,
            child_sha256=child_sha,
            error="S_MISSING: child sha identical to a9ffa852",
        )
    payload = {
        "schema": CHILD_SCHEMA,
        "sha256": child_sha,
        "init_policy": "scratch",
        "baseline_sha256": BASELINE_SHA256,
        "timesteps": int(DRIFT_TIMESTEPS),
        "train_seed": int(train_seed),
        "actual_timesteps": int(actual),
        "optimizer_steps": int(getattr(model, "_n_updates", 0) or 0),
        "obs_dim": int(MARK_EYES_OBS_DIM),
        "extra": list(EXTRA_SLOT_NAMES),
        "evolution_proof": False,
        "train_ticks_sha16": str(tape.get("train_hash") or ""),
        "train_force_open": True,
        "eval_force_open": False,
        "REAL": "no",
    }
    (art / CHILD_META_NAME).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "child_path": str(child),
        "child_sha256": child_sha,
        "init_policy": "scratch",
        "baseline_sha256": BASELINE_SHA256,
        "learn_called": True,
        "actual_timesteps": int(actual),
        "optimizer_steps": payload["optimizer_steps"],
        "obs_dim": int(MARK_EYES_OBS_DIM),
        "train_force_open": True,
        "eval_force_open": False,
        "sidecar": payload,
    }


__all__ = ["pin_train_seed", "run_drift_v1_train"]
