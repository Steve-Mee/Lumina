"""MARK_EYES tables T0 identity, T1 train, T2 eval vs path_early, T3 license."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_mark_eyes import (
    CHILD_ZIP_NAME,
    FAMILY,
    FIXTURE_TICKS_SHA16,
    GATE0_MAIN_SHA,
    INIT_SHA256,
    MARK_EYES_OBS_DIM,
    MARK_EYES_PPO_TIMESTEPS,
    SOURCE,
    TRAIN_SEED,
)
from lumina_core.rl.observation_builder import OBSERVATION_DIM


def table_t0(
    *,
    origin_sha: str,
    parent_sha: str,
    child_sha: str,
    init_policy: str,
    actual_timesteps: int,
    optimizer_steps: int,
    ticks_sha16: str,
) -> dict[str, Any]:
    return {
        "origin_main_sha": str(origin_sha or GATE0_MAIN_SHA),
        "OBSERVATION_DIM": int(OBSERVATION_DIM),
        "MARK_EYES_OBS_DIM": int(MARK_EYES_OBS_DIM),
        "parent_sha256": str(parent_sha or INIT_SHA256),
        "child_sha256": str(child_sha),
        "init_policy": str(init_policy),
        "timesteps": int(MARK_EYES_PPO_TIMESTEPS),
        "train_seed": int(TRAIN_SEED),
        "ticks_sha16": str(ticks_sha16 or FIXTURE_TICKS_SHA16),
        "optimizer_steps": int(optimizer_steps),
        "actual_timesteps": int(actual_timesteps),
        "child_zip": CHILD_ZIP_NAME,
        "source": SOURCE,
    }


def table_t1(
    *,
    actual_timesteps: int,
    optimizer_steps: int,
    workspace_isolated: bool,
    forbidden_init_refused: bool,
) -> dict[str, Any]:
    return {
        "actual_timesteps": int(actual_timesteps),
        "n_updates": int(optimizer_steps),
        "workspace_isolated": bool(workspace_isolated),
        "forbidden_init_refused": bool(forbidden_init_refused),
        "init_policy": "scratch",
    }


def table_t2(leg_a: dict[str, Any], leg_b: dict[str, Any]) -> dict[str, Any]:
    return {"A": dict(leg_a), "B": dict(leg_b)}


def table_t3(licensed: dict[str, Any], *, overall: str) -> dict[str, Any]:
    return {
        "tag": str(licensed.get("tag") or ""),
        "law": str(licensed.get("law") or ""),
        "licensed_next_family": str(licensed.get("licensed_next_family") or "H_NONE"),
        "family": FAMILY,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "playground": False,
        "hook_default": False,
        "shape_default": False,
        "overall": str(overall),
    }


__all__ = ["table_t0", "table_t1", "table_t2", "table_t3"]
