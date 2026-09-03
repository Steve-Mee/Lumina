"""Awakening OPEN_POLICY_SIGNAL: frozen π* internal signals at NEUTRAL-open. Measure-only.

Does not train. Does not implement OPEN_FILTER. Gate 1 law is always NONE.
SYNTHETIC ≡ LIVE: same splitter, same fill physics.

Science question: does the frozen policy's value-head / entropy / action-margin
knowable on the open bar separate stop×close-NEUTRAL (hole H) from +R closes (winners W)?
"""

from __future__ import annotations

from pathlib import Path

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_mech import load_close_jsonl
from lumina_core.birth.awakening_open_policy_signal_flags import (
    FAMILY_H_NONE,
    POLICY_CANDIDATE_NAMES,
    P_ACTION_MARGIN,
    P_ENTROPY,
    P_VALUE,
    TAG_S_AB_DISAGREE,
    TAG_S_MISSING,
    TAG_S_MISSING_SIGNAL,
    TAG_S_MULTI,
    TAG_S_NONE,
    TAG_S_SPLIT,
    TAG_S_THIN,
    compute_open_policy_signal_flags,
    license_from_ab,
    policy_candidate_grid_row,
)
from lumina_core.birth.awakening_open_split_flags import universe_rows, winners_from_u
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

SIGNAL_A_NAME = "policy_signal_A_close_ledger.jsonl"
SIGNAL_B_NAME = "policy_signal_B_close_ledger.jsonl"
SOURCE = "awakening_open_policy_signal"

BASELINE_WR_POLICY_A = 0.34
BASELINE_N_POLICY_A = 150
WR_WIRE_DELTA = 0.03
N_WIRE_DELTA = 15

OVERALL_MEASURE = "GRIND_REGRESS_AWAKENING_OPEN OPEN_POLICY_SIGNAL_AUTOPSY OPEN_MEASURE_ONLY"
OVERALL_INCONCLUSIVE = "GRIND_INCONCLUSIVE_AWAKENING_OPEN OPEN_POLICY_SIGNAL_AUTOPSY S_MISSING"

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
    }
)


class OpenPolicySignalProtocolError(SelectProtocolError):
    """Fail-closed protocol violation."""


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_open_policy_signal" / "workspace"


def policy_signal_ledger_path(root: Path | str | None = None, *, leg: str) -> Path:
    name = SIGNAL_A_NAME if str(leg).upper() == "A" else SIGNAL_B_NAME
    base = Path(root) if root is not None else reports_dir()
    if base.name == "workspace" and base.parent.name == "birth_cloud_run":
        return base.parent / "artifacts" / name
    if base.name == "artifacts":
        return base / name
    return base / "artifacts" / name


def assert_eval_seed(seed: int) -> int:
    n = int(seed)
    if n == TRAIN_SEED:
        raise OpenPolicySignalProtocolError(f"eval refuses train seed {n}")
    if n not in EVAL_SEEDS:
        raise OpenPolicySignalProtocolError(f"eval seed must be A/B only, got {n}")
    return n


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise OpenPolicySignalProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise OpenPolicySignalProtocolError("forbidden write to gitignored ppo zip")
    return target


def assert_not_evaluated_policy(path: Path | str) -> Path:
    from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip

    target = Path(path)
    if is_gitignored_ppo_zip(target):
        raise OpenPolicySignalProtocolError("refused gitignored ppo zip as evaluated policy")
    if target.name in {CONTROL_ZIP_NAME, HOLE_TAX_ZIP_NAME}:
        raise OpenPolicySignalProtocolError(f"refused {target.name} as evaluated policy")
    if target.is_file():
        sha = file_sha256(target)
        if sha == CONTROL_SHA256:
            raise OpenPolicySignalProtocolError("refused control sha db7daf3b as evaluated policy")
        if sha == HOLE_TAX_SHA256:
            raise OpenPolicySignalProtocolError("refused hole-tax sha ca2ae0e5 as evaluated policy")
    return target


def assert_parent_sha(path: Path | str) -> str:
    from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip

    target = Path(path)
    assert_not_evaluated_policy(target)
    if is_gitignored_ppo_zip(target):
        raise OpenPolicySignalProtocolError("refused gitignored ppo zip as init")
    if not target.is_file():
        raise OpenPolicySignalProtocolError(f"parent zip missing: {target}")
    sha = file_sha256(target)
    if sha != INIT_SHA256:
        raise OpenPolicySignalProtocolError(f"parent sha256 mismatch {sha} != {INIT_SHA256}")
    return sha


def resolve_parent_path(workspace_root: Path | str | None = None) -> Path:
    from lumina_core.birth.awakening_select import resolve_select_init_path

    path = resolve_select_init_path(workspace_root)
    assert_not_evaluated_policy(path)
    if path.name != INIT_ZIP_NAME:
        raise OpenPolicySignalProtocolError(f"evaluated zip must be {INIT_ZIP_NAME}, got {path.name}")
    return path


def assert_wire_vs_autopsy_a(*, wr_policy: float, n_policy: int) -> None:
    wr_off = abs(float(wr_policy) - BASELINE_WR_POLICY_A) > WR_WIRE_DELTA + 1e-12
    n_off = abs(int(n_policy) - BASELINE_N_POLICY_A) > N_WIRE_DELTA
    if wr_off and n_off:
        raise OpenPolicySignalProtocolError(
            f"wire change: wr_policy={wr_policy} vs {BASELINE_WR_POLICY_A} "
            f"and n_policy={n_policy} vs {BASELINE_N_POLICY_A}"
        )


def honesty_paragraph(
    tag: str,
    winning_p: str,
    lift: float | None = None,
    *,
    skip_replay: bool = False,
    n_u_a: int = 0,
    n_u_b: int = 0,
    family: str = FAMILY_H_NONE,
) -> str:
    _ = winning_p, lift
    return (
        "External OPEN_SPLIT bits did not separate H from W (PR #23 S_NONE).\n"
        "This ticket asked whether frozen π* internals at OPEN do.\n"
        f"Replay: skip_replay={str(bool(skip_replay)).lower()}. n_U A/B = {n_u_a}/{n_u_b}.\n"
        f"Winning tag: {tag}.\n"
        f"Licensed next family: {family}.\n"
        "Law shipped: NONE.\n"
        "Playground: no.\n"
        "Evolution Proof stamped: False.\n"
        "REAL: no."
    )


def overall_policy_signal_string(
    *,
    parent_loaded: bool,
    skip_replay: bool = False,
    n_u_a: int = 0,
    s_missing_signal: bool = False,
    optimizer_steps: int = 0,
) -> str:
    """MEASURE only after a real A+B replay with parent, n_U(A)>=60, signals present."""
    if not parent_loaded:
        return OVERALL_INCONCLUSIVE
    if skip_replay:
        return OVERALL_INCONCLUSIVE
    if int(n_u_a) < 60:
        return OVERALL_INCONCLUSIVE
    if s_missing_signal:
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
    "HOLE_TAX_SHA256",
    "HOLE_TAX_ZIP_NAME",
    "INIT_SHA256",
    "INIT_ZIP_NAME",
    "OVERALL_INCONCLUSIVE",
    "OVERALL_MEASURE",
    "OpenPolicySignalProtocolError",
    "POLICY_CANDIDATE_NAMES",
    "P_ACTION_MARGIN",
    "P_ENTROPY",
    "P_VALUE",
    "SIGNAL_A_NAME",
    "SIGNAL_B_NAME",
    "SOURCE",
    "TAG_S_AB_DISAGREE",
    "TAG_S_MISSING",
    "TAG_S_MISSING_SIGNAL",
    "TAG_S_MULTI",
    "TAG_S_NONE",
    "TAG_S_SPLIT",
    "TAG_S_THIN",
    "TRAIN_SEED",
    "assert_eval_seed",
    "assert_isolated_write",
    "assert_not_evaluated_policy",
    "assert_parent_sha",
    "assert_wire_vs_autopsy_a",
    "compute_open_policy_signal_flags",
    "honesty_paragraph",
    "isolated_workspace",
    "license_from_ab",
    "load_close_jsonl",
    "overall_policy_signal_string",
    "policy_candidate_grid_row",
    "policy_only_rows",
    "policy_signal_ledger_path",
    "price_sha16",
    "reports_dir",
    "resolve_parent_path",
    "universe_rows",
    "winners_from_u",
]
