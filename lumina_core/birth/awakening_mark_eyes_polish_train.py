"""G3: one continue-learn of 10_000 env steps from frozen a9ffa852. TRAIN only."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_mark_eyes_env import make_mark_eyes_train_env
from lumina_core.birth.awakening_mark_eyes_polish import (
    CHILD_META_NAME,
    CHILD_ZIP_NAME,
    INIT_SHA256,
    INIT_ZIP_NAME,
    POLISH_TIMESTEPS,
    POLISH_TRAIN_SEED,
    PolishProtocolError,
    assert_init_sha,
    load_polish_train_split,
    refuse_old_baseline,
    refuse_scratch_init,
    write_bytes_sha,
)
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_select_run import _SelectEngine
from lumina_core.logging_utils import get_logger
from lumina_core.rl.ppo_trainer import PPOTrainer

logger = get_logger("lumina.birth.awakening_mark_eyes_polish_train")


class TimestepCapCallback:
    """Cap THIS window at 10_000 additional env steps while continue counters run."""

    def __init__(self, max_steps: int) -> None:
        self.max_steps = int(max_steps)
        self.n_calls = 0
        self.num_timesteps = 0
        self._origin = 0
        self.model: Any = None

    def __call__(self) -> bool:
        return self._on_step()

    def init_callback(self, model: Any) -> None:
        self.model = model

    def on_training_start(self, _locals: dict[str, Any], _globals: dict[str, Any]) -> None:
        self._origin = int(getattr(self.model, "num_timesteps", 0) or 0)

    def on_rollout_start(self) -> None:
        return None

    def on_rollout_end(self) -> None:
        return None

    def on_training_end(self) -> None:
        return None

    def update_locals(self, _locals: dict[str, Any]) -> None:
        return None

    def update_child_locals(self, _locals: dict[str, Any]) -> None:
        return None

    def _on_step(self) -> bool:
        current = int(getattr(self.model, "num_timesteps", self.num_timesteps) or 0)
        self.num_timesteps = current
        self.n_calls += 1
        return int(current) - int(self._origin) < int(self.max_steps)


def _sb3_cap(cap: int) -> Any:
    try:
        from stable_baselines3.common.callbacks import BaseCallback
    except Exception:
        return TimestepCapCallback(cap)

    class _Cap(BaseCallback):
        def __init__(self, max_steps: int) -> None:
            super().__init__()
            self.max_steps = int(max_steps)
            self._origin = 0

        def _on_training_start(self) -> None:
            self._origin = int(self.num_timesteps)

        def _on_step(self) -> bool:
            return int(self.num_timesteps) - int(self._origin) < int(self.max_steps)

    return _Cap(cap)


def pin_train_seed(seed: int) -> None:
    if int(seed) != int(POLISH_TRAIN_SEED):
        raise PolishProtocolError(f"train seed {seed} != {POLISH_TRAIN_SEED}")
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
    if not shape:
        return ()
    return tuple(int(x) for x in shape)


def run_polish_train(
    *,
    work: Path,
    art: Path,
    init_zip: Path | None = None,
    timesteps: int = POLISH_TIMESTEPS,
    learn_fn: Any | None = None,
    ppo_load_fn: Any | None = None,
) -> dict[str, Any]:
    if int(timesteps) != int(POLISH_TIMESTEPS):
        raise PolishProtocolError(f"timesteps {timesteps} != {POLISH_TIMESTEPS}")
    if bool(PATH_EXIT_K3_SHADOW.get()) or bool(PATH_SHAPE_K3_SHADOW.get()):
        raise PolishProtocolError("hooks must stay False")
    pin_train_seed(POLISH_TRAIN_SEED)
    zip_path = Path(init_zip) if init_zip is not None else art / INIT_ZIP_NAME
    refuse_scratch_init(zip_path)
    refuse_old_baseline(zip_path)
    init_sha = assert_init_sha(zip_path)
    if init_sha != INIT_SHA256:
        raise PolishProtocolError("refuse if loaded zip sha != a9ffa852")
    tape = load_polish_train_split(work)
    train = list(tape["train"])
    if not train:
        raise PolishProtocolError("TRAIN split empty — refuse holdout ticks")
    env = make_mark_eyes_train_env(
        train,
        workspace_root=work,
        reports_dir=art,
        max_steps=max(int(timesteps), len(train)),
        tax_r=0.0,
        train_reward_fn=None,
    )
    if _obs_shape(env) != (int(MARK_EYES_OBS_DIM),):
        raise PolishProtocolError(f"env observation space {_obs_shape(env)} != (46,)")
    try:
        if ppo_load_fn is not None:
            model = ppo_load_fn(str(zip_path), env=env, device="cpu")
        else:
            from stable_baselines3 import PPO

            model = PPO.load(str(zip_path), env=env, device="cpu")
    except PolishProtocolError:
        raise
    except Exception as exc:
        logger.error("awakening.mark_eyes.polish.sb3_missing: %s", exc)
        return {
            "status": "S_MISSING",
            "learn_called": False,
            "actual_timesteps": 0,
            "optimizer_steps": 0,
            "child_sha256": "",
            "init_sha256": init_sha,
            "init_policy": f"a9ffa852{INIT_SHA256[8:]}",
            "error": f"S_MISSING: {exc}",
        }
    if _obs_shape(model) != (int(MARK_EYES_OBS_DIM),):
        return {
            "status": "S_MISSING",
            "learn_called": False,
            "actual_timesteps": 0,
            "child_sha256": "",
            "init_sha256": init_sha,
            "error": "S_MISSING: loaded obs_dim != 46",
        }
    setter = getattr(model, "set_random_seed", None)
    if callable(setter):
        setter(int(POLISH_TRAIN_SEED))
    before = int(getattr(model, "num_timesteps", 0) or 0)
    engine = _SelectEngine(model)
    trainer = PPOTrainer(engine=engine, model_dir=work / "ppo_out")
    engine.set_rl_policy(model)
    cap = _sb3_cap(int(timesteps))
    try:
        if learn_fn is not None:
            learn_fn(total_timesteps=int(timesteps), reset_num_timesteps=False, callback=cap, progress_bar=False)
        else:
            model.learn(total_timesteps=int(timesteps), reset_num_timesteps=False, callback=cap, progress_bar=False)
    except Exception as exc:
        logger.error("awakening.mark_eyes.polish.learn_failed: %s", exc)
        return {
            "status": "S_MISSING",
            "learn_called": False,
            "actual_timesteps": 0,
            "child_sha256": "",
            "init_sha256": init_sha,
            "error": f"S_MISSING: learn() {exc}",
        }
    after = int(getattr(model, "num_timesteps", 0) or 0)
    actual = max(0, after - before)
    if actual <= 0:
        return {
            "status": "S_MISSING",
            "learn_called": True,
            "actual_timesteps": 0,
            "child_sha256": "",
            "init_sha256": init_sha,
            "error": "S_MISSING: actual_timesteps == 0 — do not copy init zip and label it polish",
        }
    child = art / CHILD_ZIP_NAME
    trainer.save_weights(str(child))
    if not child.is_file() or child.stat().st_size <= 0:
        return {
            "status": "S_MISSING",
            "learn_called": True,
            "actual_timesteps": actual,
            "child_sha256": "",
            "error": "S_MISSING: child zip missing after save",
        }
    child_sha = write_bytes_sha(child)
    if child_sha == init_sha:
        return {
            "status": "S_MISSING",
            "learn_called": True,
            "actual_timesteps": actual,
            "child_sha256": child_sha,
            "init_sha256": init_sha,
            "error": "S_MISSING: child sha identical to init — do not label copy as polish",
        }
    payload = {
        "schema": "awakening_mark_eyes_polish_pi_star_v1",
        "sha256": child_sha,
        "init_policy": INIT_SHA256,
        "init_sha256": init_sha,
        "timesteps": int(POLISH_TIMESTEPS),
        "train_seed": int(POLISH_TRAIN_SEED),
        "actual_timesteps": int(actual),
        "optimizer_steps": int(getattr(model, "_n_updates", 0) or 0),
        "obs_dim": int(MARK_EYES_OBS_DIM),
        "evolution_proof": False,
        "train_ticks_sha16": str(tape.get("train_hash") or ""),
        "REAL": "no",
    }
    meta = art / CHILD_META_NAME
    meta.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "child_path": str(child),
        "child_sha256": child_sha,
        "init_sha256": init_sha,
        "init_policy": INIT_SHA256,
        "learn_called": True,
        "actual_timesteps": int(actual),
        "optimizer_steps": payload["optimizer_steps"],
        "obs_dim": int(MARK_EYES_OBS_DIM),
        "sidecar": payload,
    }


__all__ = ["TimestepCapCallback", "pin_train_seed", "run_polish_train"]
