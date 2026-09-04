"""Awakening PATH_SHAPE K3 DEAD: sitting-at-MAE and lifeless at k=3. Evaluate-only.

Does not train. Hook default off. EPS_SIT and MFE_LIFE are locked a priori, not fitted.
Does not flatten on a scalar unreal_r threshold. Does not call should_path_exit_k3.
"""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path

from lumina_core.birth.awakening_path_exit_k3 import (
    CONTROL_SHA256,
    CONTROL_ZIP_NAME,
    EVAL_A_SEED,
    EVAL_B_SEED,
    EVAL_SEEDS,
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
    TRAIN_SEED,
    PathExitK3ProtocolError,
    assert_eval_seed,
    assert_not_evaluated_policy,
    assert_parent_sha,
    assert_wire_vs_path_early_a,
    load_close_jsonl,
    path_early_source_path,
    policy_only_rows,
    price_sha16,
    reports_dir,
    resolve_parent_path,
)
from lumina_core.birth.awakening_select import SelectProtocolError

EPS_SIT = 0.05
MFE_LIFE = 0.25
FAMILY = "PATH_SHAPE:P_K3_DEAD"
SOURCE = "awakening_path_shape_k3_dead"
PATH_SHAPE_A_NAME = "path_shape_k3_dead_A_close_ledger.jsonl"
PATH_SHAPE_B_NAME = "path_shape_k3_dead_B_close_ledger.jsonl"
FLAGS_NAME = "awakening_path_shape_k3_dead_flags.json"
K27_FLAGS_NAME = "awakening_path_exit_k3_flags.json"
T025_FLAGS_NAME = "awakening_path_exit_k3_t025_flags.json"
T025_A_NAME = "path_exit_k3_t025_A_close_ledger.jsonl"
T025_B_NAME = "path_exit_k3_t025_B_close_ledger.jsonl"
PATH_EARLY_FLAGS_NAME = "awakening_path_early_flags.json"

PATH_SHAPE_K3_SHADOW: ContextVar[bool] = ContextVar("path_shape_k3_shadow", default=False)

OVERALL_MEASURE = "GRIND_REGRESS_AWAKENING_OPEN PATH_SHAPE_K3_DEAD SHADOW_MEASURE"
OVERALL_INCONCLUSIVE = "GRIND_INCONCLUSIVE_AWAKENING_OPEN PATH_SHAPE_K3_DEAD S_MISSING"

GATE0_MAIN_SHA = "eb3184db8a7931991752e0e3eef3f1149269d20f"
PARENT_BRANCH = "origin/cursor/awakening-path-exit-k3-t025-821a"

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
        PATH_EARLY_A_NAME,  # path_early_A_close_ledger.jsonl
        PATH_EARLY_B_NAME,  # path_early_B_close_ledger.jsonl
        "path_early_A_close_ledger.sha256",
        "path_early_B_close_ledger.sha256",
        PATH_EARLY_FLAGS_NAME,
        PATH_A_NAME,
        PATH_B_NAME,
        "path_exit_k3_A_close_ledger.sha256",
        "path_exit_k3_B_close_ledger.sha256",
        K27_FLAGS_NAME,
        T025_A_NAME,
        T025_B_NAME,
        "path_exit_k3_t025_A_close_ledger.sha256",
        "path_exit_k3_t025_B_close_ledger.sha256",
        T025_FLAGS_NAME,
        "path_unreal_k3_A_close_ledger.jsonl",
        "path_unreal_k3_B_close_ledger.jsonl",
        "path_unreal_k3_A_close_ledger.sha256",
        "path_unreal_k3_B_close_ledger.sha256",
        "path_unreal_k3_flags.json",
        "awakening_path_unreal_k3_flags.json",
    }
)


class PathShapeK3DeadProtocolError(SelectProtocolError):
    """Fail-closed PATH_SHAPE K3 DEAD protocol violation."""


def path_shape_k3_shadow_enabled() -> bool:
    return bool(PATH_SHAPE_K3_SHADOW.get())


def should_path_shape_k3_dead(
    *,
    enabled: bool,
    is_policy: bool,
    entry_regime: str | None,
    bars_from_entry: int,
    unreal_r: float | None,
    mae_r: float | None,
    mfe_r: float | None,
) -> bool:
    if not bool(enabled):
        return False
    if not bool(is_policy):
        return False
    if entry_regime is None or str(entry_regime).upper() != "NEUTRAL":
        return False
    if int(bars_from_entry) != 3:
        return False
    if unreal_r is None or mae_r is None or mfe_r is None:
        return False
    try:
        u = float(unreal_r)
        a = float(mae_r)
        m = float(mfe_r)
    except (TypeError, ValueError):
        return False
    sitting = (u - a) <= EPS_SIT + 1e-12
    lifeless = m <= MFE_LIFE + 1e-12
    return sitting and lifeless


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_path_shape_k3_dead" / "workspace"


def path_shape_k3_dead_ledger_path(root: Path | str | None = None, *, leg: str) -> Path:
    name = PATH_SHAPE_A_NAME if str(leg).upper() == "A" else PATH_SHAPE_B_NAME
    base = Path(root) if root is not None else reports_dir()
    if base.name == "workspace" and base.parent.name == "birth_cloud_run":
        return base.parent / "artifacts" / name
    if base.name == "artifacts":
        return base / name
    return base / "artifacts" / name


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise PathShapeK3DeadProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise PathShapeK3DeadProtocolError("forbidden write to gitignored ppo zip")
    return target


def honesty_paragraph(
    *,
    gate1_tag: str = "SHAPE_NONE",
    lift_a: float = 0.0,
    lift_b: float = 0.0,
    skip_replay: bool = False,
    replay_ran: bool = False,
    n_exit_a: int = 0,
    n_exit_b: int = 0,
    n_h_base_a: int = 0,
    n_h_shape_a: int = 0,
    n_h_base_b: int = 0,
    n_h_shape_b: int = 0,
    mean_r_base_a: float = 0.0,
    mean_r_shape_a: float = 0.0,
    mean_r_base_b: float = 0.0,
    mean_r_shape_b: float = 0.0,
    hole_moved_a: bool = False,
    hole_moved_b: bool = False,
    tag: str = "SHAPE_NONE",
    law: str = "NONE",
) -> str:
    _ = law
    return (
        "#27 T_LOCK A HOLE_MOVED; B mean_r worse. Promoting T_LOCK is forbidden.\n"
        "#28 T_FP=-0.25 TRANSFER_FAIL. k=3 R-threshold family exhausted as a controller.\n"
        f"This ticket locks EPS_SIT={EPS_SIT} and MFE_LIFE={MFE_LIFE} a priori "
        "(parking + quarter-life), not A/B-fitted.\n"
        "ContextVar PATH_SHAPE_K3_SHADOW armed only on Gate 2. PATH_EXIT_K3_SHADOW stayed False.\n"
        "Median not recomputed. No T compare in should_path_shape_k3_dead.\n"
        f"Gate 1 tag={gate1_tag} lift A/B={lift_a}/{lift_b}\n"
        f"Gate 2 skip_replay={str(bool(skip_replay)).lower()} ran={str(bool(replay_ran)).lower()} "
        f"n_exit A/B={n_exit_a}/{n_exit_b}\n"
        f"n_H A base→shape={n_h_base_a}→{n_h_shape_a} B {n_h_base_b}→{n_h_shape_b}\n"
        f"mean_r A base→shape={mean_r_base_a}→{mean_r_shape_a} B {mean_r_base_b}→{mean_r_shape_b}\n"
        f"HOLE_MOVED A/B={str(bool(hole_moved_a)).lower()}/{str(bool(hole_moved_b)).lower()}.\n"
        f"Tag: {tag}.\n"
        "Law: SHADOW default off | NONE.\n"
        "Playground: no.\n"
        "Evolution Proof stamped: False.\n"
        "REAL: no."
    )


def overall_path_shape_k3_dead_string(
    *,
    parent_loaded: bool = True,
    skip_replay: bool = False,
    optimizer_steps: int = 0,
    replay_ran: bool = False,
    s_missing_hook: bool = False,
    fixture_compare: bool = False,
    tfamily_clone: bool = False,
    both_shadows: bool = False,
    gate2_attempted: bool = False,
    gate1_complete: bool = False,
) -> str:
    if bool(both_shadows):
        return OVERALL_INCONCLUSIVE
    if bool(gate2_attempted):
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
        if bool(tfamily_clone):
            return OVERALL_INCONCLUSIVE
        return OVERALL_MEASURE
    if bool(gate1_complete):
        return OVERALL_MEASURE
    return OVERALL_INCONCLUSIVE


__all__ = [
    "CONTROL_SHA256",
    "CONTROL_ZIP_NAME",
    "EPS_SIT",
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
    "MFE_LIFE",
    "OVERALL_INCONCLUSIVE",
    "OVERALL_MEASURE",
    "PARENT_BRANCH",
    "PATH_A_NAME",
    "PATH_B_NAME",
    "PATH_EARLY_A_NAME",
    "PATH_EARLY_B_NAME",
    "PATH_EARLY_FLAGS_NAME",
    "PATH_SHAPE_A_NAME",
    "PATH_SHAPE_B_NAME",
    "PATH_SHAPE_K3_SHADOW",
    "SOURCE",
    "T025_A_NAME",
    "T025_B_NAME",
    "T025_FLAGS_NAME",
    "TRAIN_SEED",
    "PathExitK3ProtocolError",
    "PathShapeK3DeadProtocolError",
    "assert_eval_seed",
    "assert_isolated_write",
    "assert_not_evaluated_policy",
    "assert_parent_sha",
    "assert_wire_vs_path_early_a",
    "honesty_paragraph",
    "isolated_workspace",
    "load_close_jsonl",
    "overall_path_shape_k3_dead_string",
    "path_early_source_path",
    "path_shape_k3_dead_ledger_path",
    "path_shape_k3_shadow_enabled",
    "policy_only_rows",
    "price_sha16",
    "reports_dir",
    "resolve_parent_path",
    "should_path_shape_k3_dead",
]
