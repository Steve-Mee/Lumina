"""Awakening selection protocol: one pinned PPO continuation from Birth-exit π*.

Gate 1 law only. Does not move Birth floors, does not train on holdout B,
does not overwrite birth_exit_pi_star.zip. SYNTHETIC ≡ LIVE physics.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_exit_policy_export import (
    file_sha256,
    is_gitignored_ppo_zip,
    resolve_pi_star_path,
)

# Pinned BEFORE learn(). Polish cap in foundation_complete is min(10_000, polish).
# 10_000 is the trainer's Birth-polish quantum. n_steps of the loaded zip may
# be 1024; a TimestepCapCallback stops learn() at exactly this many env steps.
AWAKENING_SELECT_PPO_TIMESTEPS = 10_000
BUDGET_MIN = 1_000
BUDGET_MAX = 50_000

TRAIN_SEED = 20260901
EVAL_A_SEED = 20260902
EVAL_B_SEED = 20260903
FORBIDDEN_TRAIN_SEEDS = frozenset({EVAL_A_SEED, EVAL_B_SEED})

INIT_SHA256 = "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03"
INIT_ZIP_NAME = "birth_exit_pi_star.zip"
CHILD_ZIP_NAME = "awakening_select_pi_star.zip"
CHILD_META_NAME = "awakening_select_pi_star.json"
CHILD_SCHEMA = "awakening_select_pi_star_v1"
SELECT_A_NAME = "select_A_close_ledger.jsonl"
SELECT_B_NAME = "select_B_close_ledger.jsonl"

BASELINE_WR_POLICY_A = 0.34
BASELINE_WR_POLICY_B = 0.28
BIRTH_EXIT_WINRATE = 0.395349
OVERFIT_DA_MIN = 0.05
OVERFIT_DB_MAX = 0.02

STATUS_INCONCLUSIVE = "SELECT_INCONCLUSIVE_AWAKENING_OPEN"
TAG_SHOT = "SELECT_SHOT"

FORBIDDEN_WRITE_NAMES = frozenset(
    {
        "s1_receipt.json",
        "s2_receipt.json",
        "s3_receipt.json",
        "s4_receipt.json",
        "s5_receipt.json",
        "lumina_birth_fitness_vector.json",
        INIT_ZIP_NAME,
        "grind_A_close_ledger.jsonl",
        "grind_B_close_ledger.jsonl",
    }
)


class SelectProtocolError(RuntimeError):
    """Fail-closed protocol violation (budget, split, init, or isolated write)."""


def reports_dir() -> Path:
    return Path("reports") / "birth_cloud_run"


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_select" / "workspace"


def child_zip_path(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "artifacts" / CHILD_ZIP_NAME


def child_meta_path(root: Path | str | None = None) -> Path:
    return child_zip_path(root).with_name(CHILD_META_NAME)


def select_ledger_path(root: Path | str | None = None, *, leg: str) -> Path:
    name = SELECT_A_NAME if str(leg).upper() == "A" else SELECT_B_NAME
    base = Path(root) if root is not None else reports_dir()
    if base.name == "workspace" and base.parent.name == "birth_cloud_run":
        return base.parent / "artifacts" / name
    if base.name == "artifacts":
        return base / name
    return base / "artifacts" / name


def assert_train_seed(seed: int) -> int:
    n = int(seed)
    if n in FORBIDDEN_TRAIN_SEEDS:
        raise SelectProtocolError(f"train refuses holdout seed {n}")
    if n != TRAIN_SEED:
        raise SelectProtocolError(f"train seed must be {TRAIN_SEED}, got {n}")
    return n


def assert_not_holdout_b_path(path: Path | str | None) -> None:
    if path is None:
        return
    text = Path(path).as_posix().lower()
    if "20260903" in text or "holdout_b" in text or "workspace_grind_b" in text:
        raise SelectProtocolError(f"train refuses holdout B path {path}")


def assert_budget(timesteps: int) -> int:
    n = int(timesteps)
    if n < BUDGET_MIN or n > BUDGET_MAX:
        raise SelectProtocolError(
            f"timesteps {n} outside pin window [{BUDGET_MIN}, {BUDGET_MAX}]"
        )
    if n != AWAKENING_SELECT_PPO_TIMESTEPS:
        raise SelectProtocolError(
            f"timesteps {n} != pinned AWAKENING_SELECT_PPO_TIMESTEPS "
            f"{AWAKENING_SELECT_PPO_TIMESTEPS}"
        )
    return n


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise SelectProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise SelectProtocolError("forbidden write to gitignored ppo zip")
    return target


def resolve_select_init_path(workspace_root: Path | str | None = None) -> Path:
    """Birth-exit zip only. Workspace-sibling geometry matches resolve_pi_star_path."""
    path = resolve_pi_star_path(workspace_root)
    if is_gitignored_ppo_zip(path):
        raise SelectProtocolError("refused gitignored ppo zip as init")
    if path.name != INIT_ZIP_NAME:
        raise SelectProtocolError(f"init must be {INIT_ZIP_NAME}, got {path.name}")
    return path


def assert_init_sha(path: Path | str) -> str:
    target = Path(path)
    if is_gitignored_ppo_zip(target):
        raise SelectProtocolError("refused gitignored ppo zip as init")
    if not target.is_file():
        raise SelectProtocolError(f"init zip missing: {target}")
    sha = file_sha256(target)
    if sha != INIT_SHA256:
        raise SelectProtocolError(f"init sha256 mismatch {sha} != {INIT_SHA256}")
    return sha


def price_sha16(ticks: list[dict[str, Any]]) -> str:
    payload = ",".join(str(row.get("last") or row.get("close") or "") for row in ticks)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def select_overfit(*, wr_policy_a: float, wr_policy_b: float) -> bool:
    d_a = float(wr_policy_a) - BASELINE_WR_POLICY_A
    d_b = float(wr_policy_b) - BASELINE_WR_POLICY_B
    return bool(d_a >= OVERFIT_DA_MIN and d_b < OVERFIT_DB_MAX)


def overall_select_string(
    class_a: str,
    class_b: str,
    *,
    overfit: bool,
    noop: bool,
) -> str:
    from lumina_core.birth.awakening_grind import classify_overall

    overall = classify_overall(str(class_a), str(class_b))
    return (
        f"{overall} {TAG_SHOT} "
        f"SELECT_OVERFIT={str(bool(overfit)).lower()} "
        f"SELECT_NOOP={str(bool(noop)).lower()}"
    )


def child_sidecar_payload(
    *,
    zip_path: Path,
    init_path: Path,
    train_ticks_sha16: str,
    train_price_sha16: str,
    timesteps: int = AWAKENING_SELECT_PPO_TIMESTEPS,
    train_seed: int = TRAIN_SEED,
) -> dict[str, Any]:
    target = Path(zip_path)
    return {
        "schema": CHILD_SCHEMA,
        "sha256": file_sha256(target) if target.is_file() else "",
        "bytes": int(target.stat().st_size) if target.is_file() else 0,
        "init_path": str(init_path),
        "init_sha256": INIT_SHA256,
        "timesteps": int(timesteps),
        "train_seed": int(train_seed),
        "train_ticks_sha16": str(train_ticks_sha16),
        "train_price_sha16": str(train_price_sha16),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "pre_polish_parent": True,
        "gitignored_ppo_fallback": False,
    }


__all__ = [
    "AWAKENING_SELECT_PPO_TIMESTEPS",
    "BASELINE_WR_POLICY_A",
    "BASELINE_WR_POLICY_B",
    "BIRTH_EXIT_WINRATE",
    "BUDGET_MAX",
    "BUDGET_MIN",
    "CHILD_SCHEMA",
    "CHILD_ZIP_NAME",
    "EVAL_A_SEED",
    "EVAL_B_SEED",
    "FORBIDDEN_TRAIN_SEEDS",
    "FORBIDDEN_WRITE_NAMES",
    "INIT_SHA256",
    "SELECT_A_NAME",
    "SELECT_B_NAME",
    "STATUS_INCONCLUSIVE",
    "TAG_SHOT",
    "TRAIN_SEED",
    "SelectProtocolError",
    "assert_budget",
    "assert_init_sha",
    "assert_isolated_write",
    "assert_not_holdout_b_path",
    "assert_train_seed",
    "child_meta_path",
    "child_sidecar_payload",
    "child_zip_path",
    "isolated_workspace",
    "overall_select_string",
    "price_sha16",
    "resolve_select_init_path",
    "select_ledger_path",
    "select_overfit",
]
