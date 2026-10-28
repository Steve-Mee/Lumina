"""Awakening PATH_UNREAL_K3: single locked candidate P_K3_UNREAL_RED. Measure-only.

Does not train. Does not implement PATH_EXIT. Gate 1 law is always NONE.
k=3 is locked a priori. Candidate set size is 1 so S_MULTI cannot fire.
"""

from __future__ import annotations

from pathlib import Path

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_mech import load_close_jsonl
from lumina_core.birth.awakening_open_split_flags import universe_rows, winners_from_u
from lumina_core.birth.awakening_path_early_flags import (
    FAMILY_H_NONE,
    P_K3_UNREAL_RED,
    TAG_S_AB_DISAGREE,
    TAG_S_MISSING,
    TAG_S_MISSING_PATH,
    TAG_S_MULTI,
    TAG_S_NONE,
    TAG_S_SPLIT,
    TAG_S_THIN,
)
from lumina_core.birth.awakening_select import SelectProtocolError, price_sha16, reports_dir

TRAIN_SEED = 20260901
EVAL_A_SEED = 20260902
EVAL_B_SEED = 20260903
EVAL_SEEDS = frozenset({EVAL_A_SEED, EVAL_B_SEED})

INIT_SHA256 = "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03"
CONTROL_SHA256 = "db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029"
HOLE_TAX_SHA256 = "ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325"
INIT_ZIP_NAME = "birth_exit_pi_star.zip"
CONTROL_ZIP_NAME = "awakening_select_pi_star.zip"
HOLE_TAX_ZIP_NAME = "awakening_hole_tax_pi_star.zip"

PATH_EARLY_A_NAME = "path_early_A_close_ledger.jsonl"
PATH_EARLY_B_NAME = "path_early_B_close_ledger.jsonl"
PATH_A_NAME = "path_unreal_k3_A_close_ledger.jsonl"
PATH_B_NAME = "path_unreal_k3_B_close_ledger.jsonl"
SOURCE = "awakening_path_unreal_k3"
SOURCE_PATH_EARLY_JSONL = "path_early_jsonl"
SOURCE_NEW_REPLAY = "new_replay"

BASELINE_WR_POLICY_A = 0.307
BASELINE_N_POLICY_A = 150
WR_WIRE_DELTA = 0.03
N_WIRE_DELTA = 15

OVERALL_MEASURE = "GRIND_REGRESS_AWAKENING_OPEN PATH_UNREAL_K3_AUTOPSY PATH_MEASURE_ONLY"
OVERALL_INCONCLUSIVE = "GRIND_INCONCLUSIVE_AWAKENING_OPEN PATH_UNREAL_K3_AUTOPSY S_MISSING"

GATE0_MAIN_SHA = "5079d66af8dfd74933989bac459e97d3fbb0daca"
PR25_MERGE_SHA = "5079d66af8dfd74933989bac459e97d3fbb0daca"
WORKER_TEST_TOUCHED = False

LOCKED_PATH_EARLY_A = {
    "n_U": 126,
    "n_H": 78,
    "n_W": 39,
    "n_Uk3": 117,
    "n_Hk3": 71,
    "n_Wk3": 37,
}
LOCKED_LIFT_A = 0.28130947849257704
LOCKED_COV_H_A = 0.6056338028169014
LOCKED_COV_W_A = 0.32432432432432434
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
        PATH_EARLY_A_NAME,
        PATH_EARLY_B_NAME,
        "path_early_A_close_ledger.sha256",
        "path_early_B_close_ledger.sha256",
        "awakening_path_early_flags.json",
    }
)


class PathUnrealK3ProtocolError(SelectProtocolError):
    """Fail-closed protocol violation."""


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_path_unreal_k3" / "workspace"


def path_unreal_k3_ledger_path(root: Path | str | None = None, *, leg: str) -> Path:
    name = PATH_A_NAME if str(leg).upper() == "A" else PATH_B_NAME
    base = Path(root) if root is not None else reports_dir()
    if base.name == "workspace" and base.parent.name == "birth_cloud_run":
        return base.parent / "artifacts" / name
    if base.name == "artifacts":
        return base / name
    return base / "artifacts" / name


def path_early_source_path(root: Path | str | None = None, *, leg: str) -> Path:
    name = PATH_EARLY_A_NAME if str(leg).upper() == "A" else PATH_EARLY_B_NAME
    base = Path(root) if root is not None else reports_dir()
    if base.name == "artifacts":
        return base / name
    return base / "artifacts" / name


def assert_eval_seed(seed: int) -> int:
    n = int(seed)
    if n == TRAIN_SEED:
        raise PathUnrealK3ProtocolError(f"eval refuses train seed {n}")
    if n not in EVAL_SEEDS:
        raise PathUnrealK3ProtocolError(f"eval seed must be A/B only, got {n}")
    return n


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise PathUnrealK3ProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise PathUnrealK3ProtocolError("forbidden write to gitignored ppo zip")
    return target


def assert_not_evaluated_policy(path: Path | str) -> Path:
    from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip

    target = Path(path)
    if is_gitignored_ppo_zip(target):
        raise PathUnrealK3ProtocolError("refused gitignored ppo zip as evaluated policy")
    if target.name in {CONTROL_ZIP_NAME, HOLE_TAX_ZIP_NAME}:
        raise PathUnrealK3ProtocolError(f"refused {target.name} as evaluated policy")
    if target.is_file():
        sha = file_sha256(target)
        if sha == CONTROL_SHA256:
            raise PathUnrealK3ProtocolError("refused control sha db7daf3b as evaluated policy")
        if sha == HOLE_TAX_SHA256:
            raise PathUnrealK3ProtocolError("refused hole-tax sha ca2ae0e5 as evaluated policy")
    return target


def assert_parent_sha(path: Path | str) -> str:
    from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip

    target = Path(path)
    assert_not_evaluated_policy(target)
    if is_gitignored_ppo_zip(target):
        raise PathUnrealK3ProtocolError("refused gitignored ppo zip as init")
    if not target.is_file():
        raise PathUnrealK3ProtocolError(f"parent zip missing: {target}")
    sha = file_sha256(target)
    if sha != INIT_SHA256:
        raise PathUnrealK3ProtocolError(f"parent sha256 mismatch {sha} != {INIT_SHA256}")
    return sha


def resolve_parent_path(workspace_root: Path | str | None = None) -> Path:
    from lumina_core.birth.awakening_select import resolve_select_init_path

    path = resolve_select_init_path(workspace_root)
    assert_not_evaluated_policy(path)
    if path.name != INIT_ZIP_NAME:
        raise PathUnrealK3ProtocolError(f"evaluated zip must be {INIT_ZIP_NAME}, got {path.name}")
    return path


def assert_wire_vs_path_early_a(*, wr_policy: float, n_policy: int) -> None:
    wr_off = abs(float(wr_policy) - BASELINE_WR_POLICY_A) > WR_WIRE_DELTA + 1e-12
    n_off = abs(int(n_policy) - BASELINE_N_POLICY_A) > N_WIRE_DELTA
    if wr_off and n_off:
        raise PathUnrealK3ProtocolError(
            f"wire change: wr_policy={wr_policy} vs {BASELINE_WR_POLICY_A} "
            f"and n_policy={n_policy} vs {BASELINE_N_POLICY_A}"
        )


def identity_counts(flags: dict[str, object]) -> dict[str, int]:
    u3 = flags.get("U_3") if isinstance(flags.get("U_3"), dict) else {}
    slice_u3 = u3 if isinstance(u3, dict) else {}
    return {
        "n_U": int(flags.get("n_U") or 0),
        "n_H": int(flags.get("n_H") or 0),
        "n_W": int(flags.get("n_W") or 0),
        "n_Uk3": int(slice_u3.get("n_Uk") or 0),
        "n_Hk3": int(slice_u3.get("n_Hk") or 0),
        "n_Wk3": int(slice_u3.get("n_Wk") or 0),
    }


def assert_rescore_identity(flags_a: dict[str, object], *, source_a_sha256: str) -> None:
    if str(source_a_sha256) != KNOWN_PATH_EARLY_A_SHA256:
        return
    got = identity_counts(flags_a)
    if got != LOCKED_PATH_EARLY_A:
        raise PathUnrealK3ProtocolError(
            f"rescore algebra mismatch expected={LOCKED_PATH_EARLY_A} got={got}"
        )
    cand = flags_a.get("candidates") if isinstance(flags_a.get("candidates"), dict) else {}
    row = cand.get(P_K3_UNREAL_RED) if isinstance(cand, dict) else None
    if not isinstance(row, dict):
        raise PathUnrealK3ProtocolError(
            f"rescore algebra mismatch expected candidates[{P_K3_UNREAL_RED}] got={cand}"
        )
    lift = float(row.get("lift") or 0.0)
    cov_h = float(row.get("cov_H") or 0.0)
    if abs(lift - LOCKED_LIFT_A) > 1e-9 or abs(cov_h - LOCKED_COV_H_A) > 1e-9:
        raise PathUnrealK3ProtocolError(
            f"rescore predicate mismatch expected lift={LOCKED_LIFT_A} cov_H={LOCKED_COV_H_A} "
            f"got lift={lift} cov_H={cov_h}"
        )


def honesty_paragraph(
    *,
    source: str,
    skip_replay: bool = False,
    replay_ran: bool = False,
    n_u_a: int = 0,
    n_u_b: int = 0,
    n_u3_a: int = 0,
    n_u3_b: int = 0,
    tag: str = TAG_S_NONE,
    family: str = FAMILY_H_NONE,
) -> str:
    return (
        "PATH_EARLY S_MULTI because P_K3_UNREAL_RED and P_K5_UNREAL_RED both split. Paper MAE did not.\n"
        "This ticket locks k=3 a priori and candidate set size 1: P_K3_UNREAL_RED.\n"
        "k=5 is not a candidate.\n"
        f"Source: {source}. skip_replay={str(bool(skip_replay)).lower()}. "
        f"replay_ran={str(bool(replay_ran)).lower()}.\n"
        f"n_U A/B = {n_u_a}/{n_u_b}  U_3 A/B = {n_u3_a}/{n_u3_b}\n"
        f"Winning tag: {tag}.\n"
        f"Licensed next family: {family}.\n"
        "Law shipped: NONE.\n"
        "Flatten-at-3 shipped: no.\n"
        "Playground: no.\n"
        "Evolution Proof stamped: False.\n"
        "REAL: no."
    )


def overall_path_unreal_k3_string(
    *,
    parent_loaded: bool = True,
    skip_replay: bool = False,
    n_u_a: int = 0,
    s_missing_path: bool = False,
    optimizer_steps: int = 0,
    source_jsonl_present: bool = False,
    replay_ran: bool = False,
) -> str:
    """MEASURE after complete path_early re-score or real replay. Else INCONCLUSIVE."""
    if bool(skip_replay) and not bool(source_jsonl_present):
        return OVERALL_INCONCLUSIVE
    if not bool(source_jsonl_present) and not bool(replay_ran):
        return OVERALL_INCONCLUSIVE
    if bool(replay_ran) and not bool(parent_loaded):
        return OVERALL_INCONCLUSIVE
    if int(n_u_a) < 60:
        return OVERALL_INCONCLUSIVE
    if bool(s_missing_path):
        return OVERALL_INCONCLUSIVE
    if int(optimizer_steps) != 0:
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
    "FAMILY_H_NONE",
    "FORBIDDEN_WRITE_NAMES",
    "GATE0_MAIN_SHA",
    "HOLE_TAX_SHA256",
    "HOLE_TAX_ZIP_NAME",
    "INIT_SHA256",
    "INIT_ZIP_NAME",
    "KNOWN_PATH_EARLY_A_SHA256",
    "KNOWN_PATH_EARLY_B_SHA256",
    "LOCKED_COV_H_A",
    "LOCKED_COV_W_A",
    "LOCKED_LIFT_A",
    "LOCKED_PATH_EARLY_A",
    "OVERALL_INCONCLUSIVE",
    "OVERALL_MEASURE",
    "PATH_A_NAME",
    "PATH_B_NAME",
    "PATH_EARLY_A_NAME",
    "PATH_EARLY_B_NAME",
    "PR25_MERGE_SHA",
    "P_K3_UNREAL_RED",
    "PathUnrealK3ProtocolError",
    "SOURCE",
    "SOURCE_NEW_REPLAY",
    "SOURCE_PATH_EARLY_JSONL",
    "TAG_S_AB_DISAGREE",
    "TAG_S_MISSING",
    "TAG_S_MISSING_PATH",
    "TAG_S_MULTI",
    "TAG_S_NONE",
    "TAG_S_SPLIT",
    "TAG_S_THIN",
    "TRAIN_SEED",
    "WORKER_TEST_TOUCHED",
    "assert_eval_seed",
    "assert_isolated_write",
    "assert_not_evaluated_policy",
    "assert_parent_sha",
    "assert_rescore_identity",
    "assert_wire_vs_path_early_a",
    "honesty_paragraph",
    "identity_counts",
    "isolated_workspace",
    "load_close_jsonl",
    "overall_path_unreal_k3_string",
    "path_early_source_path",
    "path_unreal_k3_ledger_path",
    "policy_only_rows",
    "price_sha16",
    "reports_dir",
    "resolve_parent_path",
    "universe_rows",
    "winners_from_u",
]
