"""Genesis MARK_EYES train adapter: seed 20260904, G1 train split, scratch 10k.

Does not call locked assert_train_seed (20260901). Does not load 53df2d78 / 8cc435c6.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from lumina_core.birth.awakening_mark_eyes import MARK_EYES_PPO_TIMESTEPS, MarkEyesProtocolError
from lumina_core.birth.awakening_mark_eyes_env import make_mark_eyes_train_env
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_select_run import _timestep_cap_callback
from lumina_core.birth.genesis_cloud_const import (
    EYES_META_NAME,
    EYES_ZIP_NAME,
    G5_S_MISSING,
    GENESIS_FIXTURE_SEED,
    GENESIS_HOLDOUT_PCT,
)
from lumina_core.birth.genesis_cloud_protocol import (
    GenesisProtocolError,
    assert_genesis_seed,
    refuse_old_parent_as_input,
    refuse_old_ticks_sha,
)
from lumina_core.birth.genesis_cloud_workspace import file_sha256
from lumina_core.birth.tick_cache_persist import load_cache_manifest, load_split_cache
from lumina_core.logging_utils import get_logger
from lumina_core.rl.ppo_trainer import PPOTrainer

logger = get_logger("lumina.birth.genesis_mark_eyes_train")

GENESIS_TRAIN_SEED = GENESIS_FIXTURE_SEED


class _SelectEngine:
    def __init__(self, model: Any) -> None:
        self.rl_policy_model = model
        self.config = SimpleNamespace(trade_mode="sim", instrument="MES", risk_controller={})

    def set_rl_policy(self, model: Any) -> None:
        self.rl_policy_model = model


def load_genesis_train_split(work: Path) -> dict[str, Any]:
    split = load_split_cache(work, holdout_pct=GENESIS_HOLDOUT_PCT)
    if split is None or not split.train:
        raise GenesisProtocolError("genesis train split missing — do not regenerate old seeds")
    manifest = load_cache_manifest(work) or {}
    train_hash = str(manifest.get("train_hash") or "")
    refuse_old_ticks_sha(train_hash)
    return {
        "train": list(split.train),
        "holdout": list(split.holdout),
        "train_hash": train_hash,
        "raw_ticks_hash": str(manifest.get("raw_ticks_hash") or ""),
    }


def run_genesis_mark_eyes_train(
    *,
    work: Path,
    art: Path,
    init_zip: Path | str | None = None,
    timesteps: int = MARK_EYES_PPO_TIMESTEPS,
    learn_fn: Any | None = None,
    ppo_cls: Any | None = None,
) -> dict[str, Any]:
    assert_genesis_seed(GENESIS_TRAIN_SEED)
    if bool(PATH_EXIT_K3_SHADOW.get()) or bool(PATH_SHAPE_K3_SHADOW.get()):
        raise GenesisProtocolError("hooks must stay False")
    if init_zip is not None:
        refuse_old_parent_as_input(init_zip)
        raise GenesisProtocolError("init_policy must be scratch")
    if int(timesteps) != MARK_EYES_PPO_TIMESTEPS:
        raise MarkEyesProtocolError(f"timesteps {timesteps} != {MARK_EYES_PPO_TIMESTEPS}")
    tape = load_genesis_train_split(work)
    child = art / EYES_ZIP_NAME
    meta = art / EYES_META_NAME
    if child.is_file() and meta.is_file():
        payload = json.loads(meta.read_text(encoding="utf-8"))
        if int(payload.get("actual_timesteps") or 0) == MARK_EYES_PPO_TIMESTEPS:
            logger.info("genesis.mark_eyes.reuse_first_shot path=%s", child)
            return {
                "status": "reused",
                "child_path": str(child),
                "child_sha256": str(payload.get("sha256") or ""),
                "learn_called": True,
                "actual_timesteps": int(payload.get("actual_timesteps") or 0),
                "init_policy": "scratch",
            }
    env = make_mark_eyes_train_env(
        list(tape["train"]),
        workspace_root=work,
        reports_dir=art,
        max_steps=max(int(timesteps), len(tape["train"])),
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
    except GenesisProtocolError:
        raise
    except Exception as exc:
        logger.error("genesis.mark_eyes.sb3_missing: %s", exc)
        return {
            "status": G5_S_MISSING,
            "child_path": "",
            "child_sha256": "",
            "learn_called": False,
            "actual_timesteps": 0,
            "init_policy": "scratch",
            "error": f"S_MISSING: {exc}",
        }
    engine = _SelectEngine(model)
    trainer = PPOTrainer(engine=engine, model_dir=work / "ppo_out")
    engine.set_rl_policy(model)
    cap = _timestep_cap_callback(int(timesteps))
    try:
        if learn_fn is not None:
            learn_fn(
                total_timesteps=int(timesteps),
                reset_num_timesteps=True,
                callback=cap,
                progress_bar=False,
            )
        else:
            model.learn(
                total_timesteps=int(timesteps),
                reset_num_timesteps=True,
                callback=cap,
                progress_bar=False,
            )
    except Exception as exc:
        logger.error("genesis.mark_eyes.learn_failed: %s", exc)
        return {
            "status": G5_S_MISSING,
            "child_path": "",
            "child_sha256": "",
            "learn_called": False,
            "actual_timesteps": 0,
            "init_policy": "scratch",
            "error": f"S_MISSING: learn() {exc}",
        }
    actual = int(getattr(model, "num_timesteps", 0) or 0)
    if actual <= 0:
        return {
            "status": G5_S_MISSING,
            "learn_called": True,
            "actual_timesteps": 0,
            "child_sha256": "",
            "init_policy": "scratch",
            "error": "S_MISSING: actual_timesteps == 0",
        }
    trainer.save_weights(str(child))
    child_sha = file_sha256(child) if child.is_file() else ""
    payload = {
        "schema": "genesis_mark_eyes_pi_star_v1",
        "sha256": child_sha,
        "bytes": int(child.stat().st_size) if child.is_file() else 0,
        "timesteps": int(timesteps),
        "train_seed": GENESIS_TRAIN_SEED,
        "init_policy": "scratch",
        "obs_dim": 46,
        "actual_timesteps": actual,
        "optimizer_steps": int(getattr(model, "_n_updates", 0) or 0),
        "hole_tax_r": 0.0,
        "evolution_proof": False,
        "train_ticks_sha16": tape["train_hash"],
        "REAL": "no",
    }
    meta.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "child_path": str(child),
        "child_sha256": child_sha,
        "learn_called": True,
        "actual_timesteps": actual,
        "optimizer_steps": payload["optimizer_steps"],
        "init_policy": "scratch",
        "train_hash": tape["train_hash"],
    }


__all__ = ["GENESIS_TRAIN_SEED", "load_genesis_train_split", "run_genesis_mark_eyes_train"]
