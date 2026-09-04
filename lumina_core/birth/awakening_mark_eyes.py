"""Awakening MARK_EYES birth window: new body, mark-path eyes, one 10k shot.

Does not load parent weights. Does not change OBSERVATION_DIM. Hooks stay off.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_path_exit_k3 import (
    CONTROL_ZIP_NAME,
    HOLE_TAX_ZIP_NAME,
    INIT_SHA256,
    INIT_ZIP_NAME,
    PATH_A_NAME as PATH_EXIT_A_NAME,
    PATH_B_NAME as PATH_EXIT_B_NAME,
    PATH_EARLY_A_NAME,
    PATH_EARLY_B_NAME,
    reports_dir,
)
from lumina_core.birth.awakening_path_exit_k3_t025 import (
    FLAGS_NAME as T025_FLAGS_NAME,
    PATH_T025_A_NAME as T025_A_NAME,
    PATH_T025_B_NAME as T025_B_NAME,
)
from lumina_core.birth.awakening_path_shape_k3_dead import (
    FLAGS_NAME as SHAPE_FLAGS_NAME,
    PATH_SHAPE_A_NAME,
    PATH_SHAPE_B_NAME,
)
from lumina_core.birth.awakening_select import SelectProtocolError
from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip

FAMILY = "AWAKENING_MARK_EYES"
MARK_EYES_OBS_DIM = 46
MARK_EYES_EXTRA = 3
MARK_EYES_PPO_TIMESTEPS = 10_000
HOLD_NORM = 120.0
CHILD_ZIP_NAME = "awakening_mark_eyes_pi_star.zip"
CHILD_META_NAME = "awakening_mark_eyes_pi_star.json"
CHILD_SCHEMA = "awakening_mark_eyes_pi_star_v1"
SOURCE = "awakening_mark_eyes"
PATH_A_NAME = "mark_eyes_A_close_ledger.jsonl"
PATH_B_NAME = "mark_eyes_B_close_ledger.jsonl"
FLAGS_NAME = "awakening_mark_eyes_flags.json"

TRAIN_SEED = 20260901
EVAL_A_SEED = 20260902
EVAL_B_SEED = 20260903
FORBIDDEN_TRAIN_SEEDS = frozenset({EVAL_A_SEED, EVAL_B_SEED})
BUDGET_MIN = 1_000
BUDGET_MAX = 50_000
DELTA_H_MIN = 15
DELTA_MEAN_R_MIN = 0.05

PATH_EARLY_A_N_H = 78
PATH_EARLY_A_MEAN_R = -0.3093
PATH_EARLY_B_N_H = 83
PATH_EARLY_B_MEAN_R = -0.1797
KNOWN_PATH_EARLY_A_SHA256 = "4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb"
KNOWN_PATH_EARLY_B_SHA256 = "0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356"
FIXTURE_TICKS_SHA16 = "7e86c2bb1c71d514"
GATE0_MAIN_SHA = "7bcdaa079e60c92c03b256ff49d7f9a7f1534876"
PARENT_BRANCH = "origin/main"

OVERALL_MEASURE = "GRIND_REGRESS_AWAKENING_OPEN MARK_EYES_WINDOW EYES_MEASURE"
OVERALL_INCONCLUSIVE = "GRIND_INCONCLUSIVE_AWAKENING_OPEN MARK_EYES_WINDOW S_MISSING"

TAG_EYES_OK = "EYES_OK"
TAG_EYES_FAIL = "EYES_FAIL"
TAG_S_MISSING = "S_MISSING"
TAG_S_HARM = "S_HARM"
LAW_SHADOW = "SHADOW"
LAW_NONE = "NONE"

FORBIDDEN_INIT_NAMES = frozenset(
    {
        "birth_exit_pi_star.zip",
        "awakening_select_pi_star.zip",
        "awakening_hole_tax_pi_star.zip",
    }
)
EXTRA_SLOT_NAMES = ("mark_unreal_r", "mark_mae_r", "bars_held_norm")

FORBIDDEN_WRITE_NAMES = frozenset(
    {
        "s1_receipt.json",
        "s2_receipt.json",
        "s3_receipt.json",
        "s4_receipt.json",
        "s5_receipt.json",
        "lumina_birth_fitness_vector.json",
        "s5_close_ledger.jsonl",
        "birth_exit_pi_star.zip",
        INIT_ZIP_NAME,
        CONTROL_ZIP_NAME,
        HOLE_TAX_ZIP_NAME,
        "grind_A_close_ledger.jsonl",
        "grind_B_close_ledger.jsonl",
        "select_A_close_ledger.jsonl",
        "select_B_close_ledger.jsonl",
        "hole_tax_A_close_ledger.jsonl",
        "hole_tax_B_close_ledger.jsonl",
        "entry_autopsy_A_close_ledger.jsonl",
        "entry_autopsy_B_close_ledger.jsonl",
        "open_split_A_close_ledger.jsonl",
        "open_split_B_close_ledger.jsonl",
        "policy_signal_A_close_ledger.jsonl",
        "policy_signal_B_close_ledger.jsonl",
        PATH_EARLY_A_NAME,  # path_early_A_close_ledger.jsonl
        PATH_EARLY_B_NAME,
        "path_early_A_close_ledger.sha256",
        "path_early_B_close_ledger.sha256",
        "awakening_path_early_flags.json",
        PATH_EXIT_A_NAME,
        PATH_EXIT_B_NAME,
        "path_exit_k3_A_close_ledger.jsonl",
        "path_exit_k3_B_close_ledger.jsonl",
        "path_exit_k3_A_close_ledger.sha256",
        "path_exit_k3_B_close_ledger.sha256",
        "awakening_path_exit_k3_flags.json",
        T025_A_NAME,
        T025_B_NAME,
        "path_exit_k3_t025_A_close_ledger.sha256",
        "path_exit_k3_t025_B_close_ledger.sha256",
        T025_FLAGS_NAME,
        PATH_SHAPE_A_NAME,
        PATH_SHAPE_B_NAME,
        "path_shape_k3_dead_A_close_ledger.sha256",
        "path_shape_k3_dead_B_close_ledger.sha256",
        SHAPE_FLAGS_NAME,
        "awakening_select_obj_bounce_flags.json",
        "path_unreal_k3_A_close_ledger.jsonl",
        "path_unreal_k3_B_close_ledger.jsonl",
        "awakening_path_unreal_k3_flags.json",
    }
)


class MarkEyesProtocolError(SelectProtocolError):
    """Fail-closed MARK_EYES protocol violation."""


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_mark_eyes" / "workspace"


def child_zip_path(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "artifacts" / CHILD_ZIP_NAME


def child_meta_path(root: Path | str | None = None) -> Path:
    return child_zip_path(root).with_name(CHILD_META_NAME)


def mark_eyes_ledger_path(root: Path | str | None = None, *, leg: str) -> Path:
    name = PATH_A_NAME if str(leg).upper() == "A" else PATH_B_NAME
    base = Path(root) if root is not None else reports_dir()
    if base.name == "artifacts":
        return base / name
    return base / "artifacts" / name


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise MarkEyesProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise MarkEyesProtocolError("forbidden write to gitignored ppo zip")
    return target


def assert_train_seed(seed: int) -> int:
    n = int(seed)
    if n in FORBIDDEN_TRAIN_SEEDS:
        raise MarkEyesProtocolError(f"train refuses holdout seed {n}")
    if n != TRAIN_SEED:
        raise MarkEyesProtocolError(f"train seed must be {TRAIN_SEED}, got {n}")
    return n


def assert_budget(timesteps: int) -> int:
    n = int(timesteps)
    if n < BUDGET_MIN or n > BUDGET_MAX:
        raise MarkEyesProtocolError(f"timesteps {n} outside pin window [{BUDGET_MIN}, {BUDGET_MAX}]")
    if n != MARK_EYES_PPO_TIMESTEPS:
        raise MarkEyesProtocolError(
            f"timesteps {n} != pinned MARK_EYES_PPO_TIMESTEPS {MARK_EYES_PPO_TIMESTEPS}"
        )
    return n


def assert_forbidden_init(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_INIT_NAMES:
        raise MarkEyesProtocolError(f"refused {target.name} as init")
    if is_gitignored_ppo_zip(target):
        raise MarkEyesProtocolError("refused gitignored ppo zip as init")
    return target


def assert_not_holdout_b_path(path: Path | str | None) -> None:
    if path is None:
        return
    text = Path(path).as_posix().lower()
    if "20260903" in text or "holdout_b" in text or "workspace_grind_b" in text:
        raise MarkEyesProtocolError(f"train refuses holdout B path {path}")


def child_sidecar_payload(
    *,
    zip_path: Path,
    train_ticks_sha16: str,
    timesteps: int = MARK_EYES_PPO_TIMESTEPS,
    train_seed: int = TRAIN_SEED,
    actual_timesteps: int = 0,
    optimizer_steps: int = 0,
) -> dict[str, Any]:
    target = Path(zip_path)
    return {
        "schema": CHILD_SCHEMA,
        "sha256": file_sha256(target) if target.is_file() else "",
        "bytes": int(target.stat().st_size) if target.is_file() else 0,
        "timesteps": int(timesteps),
        "train_seed": int(train_seed),
        "init_policy": "scratch",
        "parent_baseline_sha256": INIT_SHA256,
        "obs_dim": MARK_EYES_OBS_DIM,
        "extra": list(EXTRA_SLOT_NAMES),
        "optimizer_steps": int(optimizer_steps),
        "actual_timesteps": int(actual_timesteps),
        "hole_tax_r": 0.0,
        "gitignored_ppo_fallback": False,
        "evolution_proof": False,
        "train_ticks_sha16": str(train_ticks_sha16),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def honesty_paragraph(
    *,
    tag: str = TAG_S_MISSING,
    law: str = LAW_NONE,
    licensed_next_family: str = "H_NONE",
    actual_timesteps: int = 0,
) -> str:
    return (
        "Parent 8cc435c6 is the frozen Birth-exit baseline, not the init of this window.\n"
        "#27 T_LOCK A HOLE_MOVED; B mean_r worse. Promoting T_LOCK is forbidden.\n"
        "#28 T_FP=-0.25 TRANSFER_FAIL. k=3 R-threshold family exhausted.\n"
        "#29 DEAD SHAPE_NONE. EPS_SIT=0.05 not widened.\n"
        "#33 BOUNCE OBJ_NONE. BOUNCE_WEAK=0.50 not widened.\n"
        "This window locks mark-path eyes a priori (unreal_r, close-to-close mae_r, "
        "bars_held_norm/120).\n"
        "Paper high/low MAE is not an eye.\n"
        "PPO.init = scratch. Parent weights not loaded.\n"
        f"One shot timesteps=10000 seed=20260901 actual={int(actual_timesteps)}.\n"
        f"Tag: {tag}.\n"
        f"Law: {law}.\n"
        f"licensed_next_family: {licensed_next_family}.\n"
        "Playground: no.\n"
        "Evolution Proof stamped: False.\n"
        "REAL: no."
    )


def overall_mark_eyes_string(
    *,
    parent_ok: bool,
    path_early_present: bool,
    optimizer_steps: int,
    actual_timesteps: int,
    train_seed: int,
    obs_dim_global: int,
    init_policy: str,
    hook_true: bool,
    forbidden_write: bool,
    gate2_complete: bool,
) -> str:
    if not bool(parent_ok) or not bool(path_early_present):
        return OVERALL_INCONCLUSIVE
    if int(obs_dim_global) != 43:
        return OVERALL_INCONCLUSIVE
    if str(init_policy) != "scratch":
        return OVERALL_INCONCLUSIVE
    if int(train_seed) != TRAIN_SEED:
        return OVERALL_INCONCLUSIVE
    if bool(hook_true) or bool(forbidden_write):
        return OVERALL_INCONCLUSIVE
    if int(optimizer_steps) < 0:
        return OVERALL_INCONCLUSIVE
    if bool(gate2_complete) and int(actual_timesteps) <= 0:
        return OVERALL_INCONCLUSIVE
    if bool(gate2_complete):
        return OVERALL_MEASURE
    return OVERALL_INCONCLUSIVE

