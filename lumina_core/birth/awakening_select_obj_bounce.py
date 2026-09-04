"""Awakening SELECT_OBJ P_BOUNCE_WEAK: recovered-R score at k=3. Measure-only.

Does not flatten. Does not train. Does not call should_path_exit_k3 or
should_path_shape_k3_dead. BOUNCE_WEAK is locked a priori, not a book median.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_path_early_path import opt_float
from lumina_core.birth.awakening_path_exit_k3 import (
    CONTROL_SHA256,
    CONTROL_ZIP_NAME,
    HOLE_TAX_SHA256,
    HOLE_TAX_ZIP_NAME,
    INIT_SHA256,
    INIT_ZIP_NAME,
    K_LOCKED,
    LAW_NONE,
    PATH_A_NAME,
    PATH_B_NAME,
    PATH_EARLY_A_NAME,
    PATH_EARLY_B_NAME,
    PATH_EXIT_K3_SHADOW,
    T_LOCK,
    PathExitK3ProtocolError,
    assert_parent_sha,
    load_close_jsonl,
    path_early_source_path,
    policy_only_rows,
    reports_dir,
    resolve_parent_path,
)
from lumina_core.birth.awakening_path_exit_k3_t025 import T_FP
from lumina_core.birth.awakening_path_shape_k3_dead import (
    EPS_SIT,
    MFE_LIFE,
    PATH_SHAPE_A_NAME,
    PATH_SHAPE_B_NAME,
    PATH_SHAPE_K3_SHADOW,
)
from lumina_core.birth.awakening_select import SelectProtocolError

BOUNCE_WEAK = 0.50
FAMILY = "SELECT_OBJ:P_BOUNCE_WEAK"
P_BOUNCE_WEAK = "P_BOUNCE_WEAK"
SOURCE = "awakening_select_obj_bounce"
FLAGS_NAME = "awakening_select_obj_bounce_flags.json"
PATH_EARLY_FLAGS_NAME = "awakening_path_early_flags.json"
K27_FLAGS_NAME = "awakening_path_exit_k3_flags.json"
T025_A_NAME = "path_exit_k3_t025_A_close_ledger.jsonl"
T025_B_NAME = "path_exit_k3_t025_B_close_ledger.jsonl"
T025_FLAGS_NAME = "awakening_path_exit_k3_t025_flags.json"
SHAPE_FLAGS_NAME = "awakening_path_shape_k3_dead_flags.json"

EPS_SIT_HIST = EPS_SIT
MFE_LIFE_HIST = MFE_LIFE
T_LOCK_HIST = T_LOCK
T_FP_HIST = T_FP

OVERALL_MEASURE = "GRIND_REGRESS_AWAKENING_OPEN SELECT_OBJ_BOUNCE SHADOW_MEASURE"
OVERALL_INCONCLUSIVE = "GRIND_INCONCLUSIVE_AWAKENING_OPEN SELECT_OBJ_BOUNCE S_MISSING"

GATE0_MAIN_SHA = "53daabec73a6a303415c267e38203f77b6805f52"
PARENT_BRANCH = "origin/main"

KNOWN_PATH_EARLY_A_SHA256 = "4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb"
KNOWN_PATH_EARLY_B_SHA256 = "0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356"

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
        PATH_A_NAME,  # path_exit_k3_A_close_ledger.jsonl
        PATH_B_NAME,
        "path_exit_k3_A_close_ledger.sha256",
        "path_exit_k3_B_close_ledger.sha256",
        K27_FLAGS_NAME,
        T025_A_NAME,  # path_exit_k3_t025_A_close_ledger.jsonl
        T025_B_NAME,
        "path_exit_k3_t025_A_close_ledger.sha256",
        "path_exit_k3_t025_B_close_ledger.sha256",
        T025_FLAGS_NAME,
        PATH_SHAPE_A_NAME,  # path_shape_k3_dead_A_close_ledger.jsonl
        PATH_SHAPE_B_NAME,
        "path_shape_k3_dead_A_close_ledger.sha256",
        "path_shape_k3_dead_B_close_ledger.sha256",
        SHAPE_FLAGS_NAME,
        "path_unreal_k3_A_close_ledger.jsonl",
        "path_unreal_k3_B_close_ledger.jsonl",
        "path_unreal_k3_A_close_ledger.sha256",
        "path_unreal_k3_B_close_ledger.sha256",
        "path_unreal_k3_flags.json",
        "awakening_path_unreal_k3_flags.json",
    }
)


class SelectObjBounceProtocolError(SelectProtocolError):
    """Fail-closed SELECT_OBJ P_BOUNCE_WEAK protocol violation."""


def bounce_r(row: dict[str, Any]) -> float | None:
    u = opt_float(row, "path_k3_unreal_r")
    a = opt_float(row, "path_k3_mae_r")
    if u is None or a is None:
        return None
    return float(u) - float(a)


def pred_bounce_weak(row: dict[str, Any]) -> bool:
    b = bounce_r(row)
    if b is None:
        return False
    return b <= BOUNCE_WEAK + 1e-12


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_select_obj_bounce" / "workspace"


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise SelectObjBounceProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise SelectObjBounceProtocolError("forbidden write to gitignored ppo zip")
    return target


def honesty_paragraph(
    *,
    gate1_tag: str = "OBJ_NONE",
    lift_a: float = 0.0,
    lift_b: float = 0.0,
    min_bounce_a: float | None = None,
    min_bounce_b: float | None = None,
    tag: str = "OBJ_NONE",
    licensed_next_family: str = "H_NONE",
) -> str:
    return (
        "#27 T_LOCK A HOLE_MOVED; B mean_r worse. Promoting T_LOCK is forbidden.\n"
        "#28 T_FP=-0.25 TRANSFER_FAIL. k=3 R-threshold family exhausted as a controller.\n"
        "#29 DEAD SHAPE_NONE. n_h_hit=0/0. EPS_SIT=0.05 not widened.\n"
        f"This ticket locks BOUNCE_WEAK={BOUNCE_WEAK:.2f} a priori "
        "(half-R recovery off paper MAE), not A/B-fitted.\n"
        "No flatten. No learn(). Both path hooks stayed False.\n"
        "Median not used as threshold.\n"
        f"Gate 1 tag={gate1_tag} lift A/B={lift_a}/{lift_b}\n"
        f"min_bounce U3 A/B={min_bounce_a}/{min_bounce_b}\n"
        f"Tag: {tag}. Law: NONE.\n"
        f"licensed_next_family: {licensed_next_family}.\n"
        "Playground: no.\n"
        "Evolution Proof stamped: False.\n"
        "REAL: no."
    )


def overall_select_obj_bounce_string(
    *,
    path_early_present: bool = True,
    optimizer_steps: int = 0,
    hook_true: bool = False,
    forbidden_write: bool = False,
    gate1_complete: bool = False,
) -> str:
    if not bool(path_early_present):
        return OVERALL_INCONCLUSIVE
    if int(optimizer_steps) != 0:
        return OVERALL_INCONCLUSIVE
    if bool(hook_true) or bool(forbidden_write):
        return OVERALL_INCONCLUSIVE
    if bool(gate1_complete):
        return OVERALL_MEASURE
    return OVERALL_INCONCLUSIVE


__all__ = [
    "BOUNCE_WEAK",
    "CONTROL_SHA256",
    "CONTROL_ZIP_NAME",
    "EPS_SIT",
    "EPS_SIT_HIST",
    "FAMILY",
    "FLAGS_NAME",
    "FORBIDDEN_WRITE_NAMES",
    "GATE0_MAIN_SHA",
    "HOLE_TAX_SHA256",
    "HOLE_TAX_ZIP_NAME",
    "INIT_SHA256",
    "INIT_ZIP_NAME",
    "K27_FLAGS_NAME",
    "KNOWN_PATH_EARLY_A_SHA256",
    "KNOWN_PATH_EARLY_B_SHA256",
    "K_LOCKED",
    "LAW_NONE",
    "MFE_LIFE",
    "MFE_LIFE_HIST",
    "OVERALL_INCONCLUSIVE",
    "OVERALL_MEASURE",
    "PARENT_BRANCH",
    "PATH_A_NAME",
    "PATH_B_NAME",
    "PATH_EARLY_A_NAME",
    "PATH_EARLY_B_NAME",
    "PATH_EARLY_FLAGS_NAME",
    "PATH_EXIT_K3_SHADOW",
    "PATH_SHAPE_A_NAME",
    "PATH_SHAPE_B_NAME",
    "PATH_SHAPE_K3_SHADOW",
    "P_BOUNCE_WEAK",
    "SHAPE_FLAGS_NAME",
    "SOURCE",
    "T025_A_NAME",
    "T025_B_NAME",
    "T025_FLAGS_NAME",
    "T_FP",
    "T_FP_HIST",
    "T_LOCK",
    "T_LOCK_HIST",
    "PathExitK3ProtocolError",
    "SelectObjBounceProtocolError",
    "assert_isolated_write",
    "assert_parent_sha",
    "bounce_r",
    "honesty_paragraph",
    "isolated_workspace",
    "load_close_jsonl",
    "overall_select_obj_bounce_string",
    "path_early_source_path",
    "policy_only_rows",
    "pred_bounce_weak",
    "reports_dir",
    "resolve_parent_path",
]
