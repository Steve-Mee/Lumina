"""Awakening PATH_EXIT K3 T025: flatten-at-3 at a priori T_FP = -0.25. Evaluate-only.

Does not train. Hook default off. T_FP is a quarter-stop physical dent, not a book median.
Does not change T_LOCK. Does not promote T_LOCK. Does not fit a new T on B.
"""

from __future__ import annotations

from pathlib import Path

from lumina_core.birth.awakening_path_exit_k3 import (
    BASELINE_N_POLICY_A,
    BASELINE_WR_POLICY_A,
    CONTROL_SHA256,
    CONTROL_ZIP_NAME,
    EVAL_A_SEED,
    EVAL_B_SEED,
    EVAL_SEEDS,
    FAMILY,
    HOLE_TAX_SHA256,
    HOLE_TAX_ZIP_NAME,
    INIT_SHA256,
    INIT_ZIP_NAME,
    K_LOCKED,
    LAW_NONE,
    LAW_SHADOW,
    PATH_A_NAME,
    PATH_B_NAME,
    PATH_EARLY_A_NAME,
    PATH_EARLY_B_NAME,
    PATH_EXIT_K3_SHADOW,
    PATH_EXIT_K3_THRESHOLD,
    PathExitK3ProtocolError,
    T_LOCK,
    TRAIN_SEED,
    assert_eval_seed,
    assert_not_evaluated_policy,
    assert_parent_sha,
    assert_wire_vs_path_early_a,
    load_close_jsonl,
    path_early_source_path,
    path_exit_k3_shadow_enabled,
    path_exit_k3_threshold,
    policy_only_rows,
    price_sha16,
    reports_dir,
    resolve_parent_path,
    should_path_exit_k3,
)
from lumina_core.birth.awakening_select import SelectProtocolError

T_FP = -0.25
SOURCE = "awakening_path_exit_k3_t025"
PATH_T025_A_NAME = "path_exit_k3_t025_A_close_ledger.jsonl"
PATH_T025_B_NAME = "path_exit_k3_t025_B_close_ledger.jsonl"
FLAGS_NAME = "awakening_path_exit_k3_t025_flags.json"
K27_FLAGS_NAME = "awakening_path_exit_k3_flags.json"

OVERALL_MEASURE = "GRIND_REGRESS_AWAKENING_OPEN PATH_EXIT_K3_T025 SHADOW_MEASURE"
OVERALL_INCONCLUSIVE = "GRIND_INCONCLUSIVE_AWAKENING_OPEN PATH_EXIT_K3_T025 S_MISSING"

GATE0_MAIN_SHA = "a694f3f55f4bc7f3bb5abf8fecc6d09481ec200e"
PR27_MERGE_SHA = "a694f3f55f4bc7f3bb5abf8fecc6d09481ec200e"

FORBIDDEN_WRITE_NAMES = frozenset(
    {
        "s1_receipt.json",
        "s2_receipt.json",
        "s3_receipt.json",
        "s4_receipt.json",
        "s5_receipt.json",
        "lumina_birth_fitness_vector.json",
        "s5_close_ledger.jsonl",
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
        PATH_EARLY_A_NAME,
        PATH_EARLY_B_NAME,
        "path_early_A_close_ledger.sha256",
        "path_early_B_close_ledger.sha256",
        "awakening_path_early_flags.json",
        "path_exit_k3_A_close_ledger.jsonl",
        "path_exit_k3_B_close_ledger.jsonl",
        "path_exit_k3_A_close_ledger.sha256",
        "path_exit_k3_B_close_ledger.sha256",
        K27_FLAGS_NAME,
        "path_unreal_k3_A_close_ledger.jsonl",
        "path_unreal_k3_B_close_ledger.jsonl",
        "path_unreal_k3_A_close_ledger.sha256",
        "path_unreal_k3_B_close_ledger.sha256",
        "path_unreal_k3_flags.json",
        "awakening_path_unreal_k3_flags.json",
    }
)


class PathExitK3T025ProtocolError(SelectProtocolError):
    """Fail-closed T025 protocol violation."""


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_path_exit_k3_t025" / "workspace"


def path_exit_k3_t025_ledger_path(root: Path | str | None = None, *, leg: str) -> Path:
    name = PATH_T025_A_NAME if str(leg).upper() == "A" else PATH_T025_B_NAME
    base = Path(root) if root is not None else reports_dir()
    if base.name == "workspace" and base.parent.name == "birth_cloud_run":
        return base.parent / "artifacts" / name
    if base.name == "artifacts":
        return base / name
    return base / "artifacts" / name


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise PathExitK3T025ProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise PathExitK3T025ProtocolError("forbidden write to gitignored ppo zip")
    return target


def honesty_paragraph(
    *,
    skip_replay: bool = False,
    n_exit_a: int = 0,
    n_exit_b: int = 0,
    n_h_base_a: int = 0,
    n_h_t025_a: int = 0,
    n_h_base_b: int = 0,
    n_h_t025_b: int = 0,
    mean_r_base_a: float = 0.0,
    mean_r_t025_a: float = 0.0,
    mean_r_base_b: float = 0.0,
    mean_r_t025_b: float = 0.0,
    hole_moved_a: bool = False,
    hole_moved_b: bool = False,
    tag: str = "TRANSFER_FAIL",
) -> str:
    return (
        "#27 T_LOCK A HOLE_MOVED; B mean_r worse. Promoting T_LOCK is forbidden.\n"
        f"This ticket locks T_FP={T_FP} a priori (quarter-stop), not B-fitted.\n"
        "ContextVar PATH_EXIT_K3_THRESHOLD armed. Median not recomputed.\n"
        f"Replay skip_replay={str(bool(skip_replay)).lower()} "
        f"n_exit A/B={n_exit_a}/{n_exit_b} "
        f"n_H A base→t025={n_h_base_a}→{n_h_t025_a} "
        f"B {n_h_base_b}→{n_h_t025_b}.\n"
        f"mean_r A base→t025={mean_r_base_a}→{mean_r_t025_a} "
        f"B {mean_r_base_b}→{mean_r_t025_b}.\n"
        f"HOLE_MOVED A/B={str(bool(hole_moved_a)).lower()}/{str(bool(hole_moved_b)).lower()}.\n"
        f"Tag: {tag}.\n"
        "Law: SHADOW default off.\n"
        "Playground: no.\n"
        "Evolution Proof stamped: False.\n"
        "REAL: no."
    )


def overall_path_exit_k3_t025_string(
    *,
    parent_loaded: bool = True,
    skip_replay: bool = False,
    optimizer_steps: int = 0,
    replay_ran: bool = False,
    s_missing_hook: bool = False,
    fixture_compare: bool = False,
    tlock_clone: bool = False,
) -> str:
    if bool(skip_replay) and not bool(fixture_compare):
        return OVERALL_INCONCLUSIVE
    if not bool(replay_ran) and not bool(fixture_compare):
        return OVERALL_INCONCLUSIVE
    if bool(replay_ran) and not bool(parent_loaded):
        return OVERALL_INCONCLUSIVE
    if int(optimizer_steps) != 0:
        return OVERALL_INCONCLUSIVE
    if bool(s_missing_hook):
        return OVERALL_INCONCLUSIVE
    if bool(tlock_clone):
        return OVERALL_INCONCLUSIVE
    return OVERALL_MEASURE


__all__ = [
    "BASELINE_N_POLICY_A",
    "BASELINE_WR_POLICY_A",
    "CONTROL_SHA256",
    "CONTROL_ZIP_NAME",
    "EVAL_A_SEED",
    "EVAL_B_SEED",
    "EVAL_SEEDS",
    "FAMILY",
    "FLAGS_NAME",
    "FORBIDDEN_WRITE_NAMES",
    "GATE0_MAIN_SHA",
    "HOLE_TAX_SHA256",
    "HOLE_TAX_ZIP_NAME",
    "INIT_SHA256",
    "INIT_ZIP_NAME",
    "K27_FLAGS_NAME",
    "K_LOCKED",
    "LAW_NONE",
    "LAW_SHADOW",
    "OVERALL_INCONCLUSIVE",
    "OVERALL_MEASURE",
    "PATH_A_NAME",
    "PATH_B_NAME",
    "PATH_EARLY_A_NAME",
    "PATH_EARLY_B_NAME",
    "PATH_EXIT_K3_SHADOW",
    "PATH_EXIT_K3_THRESHOLD",
    "PATH_T025_A_NAME",
    "PATH_T025_B_NAME",
    "PR27_MERGE_SHA",
    "SOURCE",
    "TRAIN_SEED",
    "T_FP",
    "T_LOCK",
    "PathExitK3ProtocolError",
    "PathExitK3T025ProtocolError",
    "assert_eval_seed",
    "assert_isolated_write",
    "assert_not_evaluated_policy",
    "assert_parent_sha",
    "assert_wire_vs_path_early_a",
    "honesty_paragraph",
    "isolated_workspace",
    "load_close_jsonl",
    "overall_path_exit_k3_t025_string",
    "path_early_source_path",
    "path_exit_k3_shadow_enabled",
    "path_exit_k3_t025_ledger_path",
    "path_exit_k3_threshold",
    "policy_only_rows",
    "price_sha16",
    "reports_dir",
    "resolve_parent_path",
    "should_path_exit_k3",
]
