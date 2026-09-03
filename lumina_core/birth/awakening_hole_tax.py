"""Awakening hole-tax law: train-only −1 R on stop × NEUTRAL.

Gate 0/1 protocol. Does not move Birth floors, does not tax exam dollars,
does not overwrite birth_exit or PR #20 select zips. SYNTHETIC ≡ LIVE physics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind import classify_overall
from lumina_core.birth.awakening_select import SelectProtocolError, price_sha16, reports_dir
from lumina_core.birth.birth_exit_policy_export import (
    file_sha256,
    is_gitignored_ppo_zip,
)

TRAIN_SEED = 20260901
EVAL_A_SEED = 20260902
EVAL_B_SEED = 20260903
INIT_SHA256 = "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03"

# THE LAW — pinned before learn(). Train reward only.
AWAKENING_HOLE_TAX_R = 1.0
AWAKENING_HOLE_TAX_PPO_TIMESTEPS = 10_000
HOLE_REASON = "stop"
HOLE_REGIME = "NEUTRAL"

BUDGET_MIN = 1_000
BUDGET_MAX = 50_000
FORBIDDEN_TRAIN_SEEDS = frozenset({EVAL_A_SEED, EVAL_B_SEED})

CONTROL_SHA256 = "db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029"
CONTROL_ZIP_NAME = "awakening_select_pi_star.zip"
INIT_ZIP_NAME = "birth_exit_pi_star.zip"
CHILD_ZIP_NAME = "awakening_hole_tax_pi_star.zip"
CHILD_META_NAME = "awakening_hole_tax_pi_star.json"
CHILD_SCHEMA = "awakening_hole_tax_pi_star_v1"
HOLE_TAX_A_NAME = "hole_tax_A_close_ledger.jsonl"
HOLE_TAX_B_NAME = "hole_tax_B_close_ledger.jsonl"

STATUS_INCONCLUSIVE = "HOLE_TAX_INCONCLUSIVE_AWAKENING_OPEN"
TAG_SHOT = "HOLE_TAX_SHOT"

BASELINE_WR_POLICY_A = 0.34
BASELINE_WR_POLICY_B = 0.28
BIRTH_EXIT_WINRATE = 0.395349
OVERFIT_DA_MIN = 0.05
OVERFIT_DB_MAX = 0.02

# Parent grind (PR #17/#19). A from ticket. B from grind_B JSONL policy stop×NEUTRAL.
PARENT_A_HOLE_N = 83
PARENT_A_PLANT_FO = 68
PARENT_B_HOLE_N = 94
PARENT_B_PLANT_FO = 21

FORBIDDEN_WRITE_NAMES = frozenset(
    {
        "s1_receipt.json",
        "s2_receipt.json",
        "s3_receipt.json",
        "s4_receipt.json",
        "s5_receipt.json",
        "lumina_birth_fitness_vector.json",
        INIT_ZIP_NAME,
        CONTROL_ZIP_NAME,
        "grind_A_close_ledger.jsonl",
        "grind_B_close_ledger.jsonl",
        "select_A_close_ledger.jsonl",
        "select_B_close_ledger.jsonl",
    }
)


class HoleTaxProtocolError(SelectProtocolError):
    """Fail-closed protocol violation (init, split, isolated write, budget)."""


def apply_hole_tax(process_r: float, close_reason: str, regime: str) -> float:
    if str(close_reason) == "stop" and str(regime).upper() == "NEUTRAL":
        return float(process_r) - AWAKENING_HOLE_TAX_R
    return float(process_r)


def hole_substitution(
    *,
    parent_hole_n: int,
    child_hole_n: int,
    parent_plant_fo: int,
    child_plant_fo: int,
) -> bool:
    return (int(parent_hole_n) - int(child_hole_n)) >= 20 and (
        int(child_plant_fo) - int(parent_plant_fo)
    ) >= 15


def select_overfit(*, wr_policy_a: float, wr_policy_b: float) -> bool:
    return (float(wr_policy_a) - 0.34) >= 0.05 and (float(wr_policy_b) - 0.28) < 0.02


def hole_moved(*, hole_n_a: int, mean_r_policy_a: float) -> bool:
    return int(hole_n_a) <= 60 or float(mean_r_policy_a) >= -0.05


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_hole_tax" / "workspace"


def child_zip_path(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "artifacts" / CHILD_ZIP_NAME


def child_meta_path(root: Path | str | None = None) -> Path:
    return child_zip_path(root).with_name(CHILD_META_NAME)


def hole_tax_ledger_path(root: Path | str | None = None, *, leg: str) -> Path:
    name = HOLE_TAX_A_NAME if str(leg).upper() == "A" else HOLE_TAX_B_NAME
    base = Path(root) if root is not None else reports_dir()
    if base.name == "workspace" and base.parent.name == "birth_cloud_run":
        return base.parent / "artifacts" / name
    if base.name == "artifacts":
        return base / name
    return base / "artifacts" / name


def assert_train_seed(seed: int) -> int:
    n = int(seed)
    if n in FORBIDDEN_TRAIN_SEEDS:
        raise HoleTaxProtocolError(f"train refuses holdout seed {n}")
    if n != TRAIN_SEED:
        raise HoleTaxProtocolError(f"train seed must be {TRAIN_SEED}, got {n}")
    return n


def assert_not_holdout_b_path(path: Path | str | None) -> None:
    if path is None:
        return
    text = Path(path).as_posix().lower()
    if "20260903" in text or "holdout_b" in text or "workspace_grind_b" in text:
        raise HoleTaxProtocolError(f"train refuses holdout B path {path}")


def assert_budget(timesteps: int) -> int:
    n = int(timesteps)
    if n < BUDGET_MIN or n > BUDGET_MAX:
        raise HoleTaxProtocolError(
            f"timesteps {n} outside pin window [{BUDGET_MIN}, {BUDGET_MAX}]"
        )
    if n != AWAKENING_HOLE_TAX_PPO_TIMESTEPS:
        raise HoleTaxProtocolError(
            f"timesteps {n} != pinned AWAKENING_HOLE_TAX_PPO_TIMESTEPS "
            f"{AWAKENING_HOLE_TAX_PPO_TIMESTEPS}"
        )
    return n


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise HoleTaxProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise HoleTaxProtocolError("forbidden write to gitignored ppo zip")
    return target


def assert_not_control_init(path: Path | str) -> Path:
    """Refuse PR #20 child as init — that would confound tax with SELECT weights."""
    target = Path(path)
    if target.name == CONTROL_ZIP_NAME:
        raise HoleTaxProtocolError("refused PR #20 control zip as hole-tax init")
    if is_gitignored_ppo_zip(target):
        raise HoleTaxProtocolError("refused gitignored ppo zip as init")
    if target.is_file() and file_sha256(target) == CONTROL_SHA256:
        raise HoleTaxProtocolError("refused control sha db7daf3b as hole-tax init")
    return target


def resolve_hole_tax_init_path(workspace_root: Path | str | None = None) -> Path:
    from lumina_core.birth.awakening_select import resolve_select_init_path

    path = resolve_select_init_path(workspace_root)
    assert_not_control_init(path)
    if path.name != INIT_ZIP_NAME:
        raise HoleTaxProtocolError(f"init must be {INIT_ZIP_NAME}, got {path.name}")
    return path


def assert_init_sha(path: Path | str) -> str:
    target = Path(path)
    assert_not_control_init(target)
    if is_gitignored_ppo_zip(target):
        raise HoleTaxProtocolError("refused gitignored ppo zip as init")
    if not target.is_file():
        raise HoleTaxProtocolError(f"init zip missing: {target}")
    sha = file_sha256(target)
    if sha != INIT_SHA256:
        raise HoleTaxProtocolError(f"init sha256 mismatch {sha} != {INIT_SHA256}")
    return sha


def overall_hole_tax_string(
    class_a: str,
    class_b: str,
    *,
    overfit: bool,
    substitution: bool,
    moved: bool,
) -> str:
    overall = classify_overall(str(class_a), str(class_b))
    return (
        f"{overall} {TAG_SHOT} "
        f"SELECT_OVERFIT={str(bool(overfit)).lower()} "
        f"HOLE_SUBSTITUTION={str(bool(substitution)).lower()} "
        f"HOLE_MOVED={str(bool(moved)).lower()}"
    )


def child_sidecar_payload(
    *,
    zip_path: Path,
    init_path: Path,
    train_ticks_sha16: str,
    train_price_sha16: str,
    timesteps: int = AWAKENING_HOLE_TAX_PPO_TIMESTEPS,
    train_seed: int = TRAIN_SEED,
    actual_timesteps: int = 0,
    optimizer_steps: int = 0,
    select_noop: bool = False,
    hole_tax_r: float = AWAKENING_HOLE_TAX_R,
) -> dict[str, Any]:
    target = Path(zip_path)
    return {
        "schema": CHILD_SCHEMA,
        "sha256": file_sha256(target) if target.is_file() else "",
        "bytes": int(target.stat().st_size) if target.is_file() else 0,
        "init_path": str(init_path),
        "init_sha256": INIT_SHA256,
        "control_sha256": CONTROL_SHA256,
        "timesteps": int(timesteps),
        "hole_tax_r": float(hole_tax_r),
        "train_seed": int(train_seed),
        "train_ticks_sha16": str(train_ticks_sha16),
        "train_price_sha16": str(train_price_sha16),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "gitignored_ppo_fallback": False,
        "actual_timesteps": int(actual_timesteps),
        "optimizer_steps": int(optimizer_steps),
        "select_noop": bool(select_noop),
    }


__all__ = [
    "AWAKENING_HOLE_TAX_PPO_TIMESTEPS",
    "AWAKENING_HOLE_TAX_R",
    "BASELINE_WR_POLICY_A",
    "BASELINE_WR_POLICY_B",
    "BIRTH_EXIT_WINRATE",
    "BUDGET_MAX",
    "BUDGET_MIN",
    "CHILD_SCHEMA",
    "CHILD_ZIP_NAME",
    "CONTROL_SHA256",
    "CONTROL_ZIP_NAME",
    "EVAL_A_SEED",
    "EVAL_B_SEED",
    "FORBIDDEN_TRAIN_SEEDS",
    "FORBIDDEN_WRITE_NAMES",
    "HOLE_REASON",
    "HOLE_REGIME",
    "HOLE_TAX_A_NAME",
    "HOLE_TAX_B_NAME",
    "HoleTaxProtocolError",
    "INIT_SHA256",
    "PARENT_A_HOLE_N",
    "PARENT_A_PLANT_FO",
    "PARENT_B_HOLE_N",
    "PARENT_B_PLANT_FO",
    "STATUS_INCONCLUSIVE",
    "TAG_SHOT",
    "TRAIN_SEED",
    "apply_hole_tax",
    "assert_budget",
    "assert_init_sha",
    "assert_isolated_write",
    "assert_not_control_init",
    "assert_not_holdout_b_path",
    "assert_train_seed",
    "child_meta_path",
    "child_sidecar_payload",
    "child_zip_path",
    "hole_moved",
    "hole_substitution",
    "hole_tax_ledger_path",
    "isolated_workspace",
    "overall_hole_tax_string",
    "price_sha16",
    "reports_dir",
    "resolve_hole_tax_init_path",
    "select_overfit",
]
