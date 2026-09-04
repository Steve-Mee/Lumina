"""Awakening PATH_EXIT K3 shadow: flatten-at-3 at locked T_LOCK. Evaluate-only.

Does not train. Hook default off. T_LOCK is a prior measurement, not this book's median.
"""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_mech import load_close_jsonl
from lumina_core.birth.awakening_open_split_flags import universe_rows, winners_from_u
from lumina_core.birth.awakening_select import SelectProtocolError, price_sha16, reports_dir

T_LOCK = -0.04787176712367987
FAMILY = "PATH_EXIT:P_K3_UNREAL_RED"
K_LOCKED = 3
LAW_SHADOW = "SHADOW"
LAW_NONE = "NONE"

PATH_EXIT_K3_SHADOW: ContextVar[bool] = ContextVar("path_exit_k3_shadow", default=False)
PATH_EXIT_K3_THRESHOLD: ContextVar[float] = ContextVar("path_exit_k3_threshold", default=T_LOCK)

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
PATH_UNREAL_FLAGS_NAME = "path_unreal_k3_flags.json"
PATH_UNREAL_A_NAME = "path_unreal_k3_A_close_ledger.jsonl"
PATH_UNREAL_B_NAME = "path_unreal_k3_B_close_ledger.jsonl"
PATH_A_NAME = "path_exit_k3_A_close_ledger.jsonl"
PATH_B_NAME = "path_exit_k3_B_close_ledger.jsonl"
SOURCE = "awakening_path_exit_k3"

BASELINE_WR_POLICY_A = 0.307
BASELINE_N_POLICY_A = 150
WR_WIRE_DELTA = 0.03
N_WIRE_DELTA = 15
PAPER_DROP_H_A = 43
PAPER_DROP_W_A = 12
PAPER_N_EXIT_SCALE_A = 55

OVERALL_MEASURE = "GRIND_REGRESS_AWAKENING_OPEN PATH_EXIT_K3_SHADOW SHADOW_MEASURE"
OVERALL_INCONCLUSIVE = "GRIND_INCONCLUSIVE_AWAKENING_OPEN PATH_EXIT_K3_SHADOW S_MISSING"

GATE0_MAIN_SHA = "334e367ffeec8fecf01b70f86b1dd84952064ebf"
PR26_MERGE_SHA = "334e367ffeec8fecf01b70f86b1dd84952064ebf"

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
        PATH_UNREAL_A_NAME,
        PATH_UNREAL_B_NAME,
        "path_unreal_k3_A_close_ledger.sha256",
        "path_unreal_k3_B_close_ledger.sha256",
        PATH_UNREAL_FLAGS_NAME,
        "awakening_path_unreal_k3_flags.json",
    }
)


class PathExitK3ProtocolError(SelectProtocolError):
    """Fail-closed protocol violation."""


def path_exit_k3_shadow_enabled() -> bool:
    return bool(PATH_EXIT_K3_SHADOW.get())


def path_exit_k3_threshold() -> float:
    return float(PATH_EXIT_K3_THRESHOLD.get())


def should_path_exit_k3(
    *,
    enabled: bool,
    is_policy: bool,
    entry_regime: str | None,
    bars_from_entry: int,
    unreal_r: float | None,
    threshold: float | None = None,
) -> bool:
    """Causal flatten predicate. Missing unreal or unknown regime → do not flatten."""
    if not bool(enabled):
        return False
    if not bool(is_policy):
        return False
    if entry_regime is None or str(entry_regime).upper() != "NEUTRAL":
        return False
    if int(bars_from_entry) != K_LOCKED:
        return False
    if unreal_r is None:
        return False
    try:
        mark = float(unreal_r)
    except (TypeError, ValueError):
        return False
    if threshold is None:
        thr = path_exit_k3_threshold()
    else:
        thr = float(threshold)
    return mark <= thr


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_path_exit_k3" / "workspace"


def path_exit_k3_ledger_path(root: Path | str | None = None, *, leg: str) -> Path:
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
        raise PathExitK3ProtocolError(f"eval refuses train seed {n}")
    if n not in EVAL_SEEDS:
        raise PathExitK3ProtocolError(f"eval seed must be A/B only, got {n}")
    return n


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise PathExitK3ProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise PathExitK3ProtocolError("forbidden write to gitignored ppo zip")
    return target


def assert_not_evaluated_policy(path: Path | str) -> Path:
    from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip

    target = Path(path)
    if is_gitignored_ppo_zip(target):
        raise PathExitK3ProtocolError("refused gitignored ppo zip as evaluated policy")
    if target.name in {CONTROL_ZIP_NAME, HOLE_TAX_ZIP_NAME}:
        raise PathExitK3ProtocolError(f"refused {target.name} as evaluated policy")
    if target.is_file():
        sha = file_sha256(target)
        if sha == CONTROL_SHA256:
            raise PathExitK3ProtocolError("refused control sha db7daf3b as evaluated policy")
        if sha == HOLE_TAX_SHA256:
            raise PathExitK3ProtocolError("refused hole-tax sha ca2ae0e5 as evaluated policy")
    return target


def assert_parent_sha(path: Path | str) -> str:
    from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip

    target = Path(path)
    assert_not_evaluated_policy(target)
    if is_gitignored_ppo_zip(target):
        raise PathExitK3ProtocolError("refused gitignored ppo zip as init")
    if not target.is_file():
        raise PathExitK3ProtocolError(f"parent zip missing: {target}")
    sha = file_sha256(target)
    if sha != INIT_SHA256:
        raise PathExitK3ProtocolError(f"parent sha256 mismatch {sha} != {INIT_SHA256}")
    return sha


def resolve_parent_path(workspace_root: Path | str | None = None) -> Path:
    from lumina_core.birth.awakening_select import resolve_select_init_path

    path = resolve_select_init_path(workspace_root)
    assert_not_evaluated_policy(path)
    if path.name != INIT_ZIP_NAME:
        raise PathExitK3ProtocolError(f"evaluated zip must be {INIT_ZIP_NAME}, got {path.name}")
    return path


def assert_wire_vs_path_early_a(*, wr_policy: float, n_policy: int) -> None:
    """AND-stop: wr off AND n_policy off. wr-only move is the experiment."""
    wr_off = abs(float(wr_policy) - BASELINE_WR_POLICY_A) > WR_WIRE_DELTA + 1e-12
    n_off = abs(int(n_policy) - BASELINE_N_POLICY_A) > N_WIRE_DELTA
    if wr_off and n_off:
        raise PathExitK3ProtocolError(
            f"wire change: wr_policy={wr_policy} vs {BASELINE_WR_POLICY_A} "
            f"and n_policy={n_policy} vs {BASELINE_N_POLICY_A}"
        )


def honesty_paragraph(
    *,
    skip_replay: bool = False,
    n_exit_a: int = 0,
    n_exit_b: int = 0,
    n_h_base_a: int = 0,
    n_h_shadow_a: int = 0,
    tag: str = "HOLE_INTACT",
) -> str:
    return (
        "PR #26 licensed PATH_EXIT:P_K3_UNREAL_RED with law NONE.\n"
        f"This ticket shadows flatten-at-3 at T_LOCK={T_LOCK}.\n"
        "k=5 not used. Median not recomputed on this book.\n"
        f"Replay skip_replay={str(bool(skip_replay)).lower()} "
        f"n_exit A/B={n_exit_a}/{n_exit_b} "
        f"n_H A base→shadow={n_h_base_a}→{n_h_shadow_a}.\n"
        f"Tag: {tag}.\n"
        "Law shipped: SHADOW (default off).\n"
        "Playground: no.\n"
        "Evolution Proof stamped: False.\n"
        "REAL: no."
    )


def overall_path_exit_k3_string(
    *,
    parent_loaded: bool = True,
    skip_replay: bool = False,
    optimizer_steps: int = 0,
    replay_ran: bool = False,
    s_missing_hook: bool = False,
    fixture_compare: bool = False,
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
    "FORBIDDEN_WRITE_NAMES",
    "GATE0_MAIN_SHA",
    "HOLE_TAX_SHA256",
    "HOLE_TAX_ZIP_NAME",
    "INIT_SHA256",
    "INIT_ZIP_NAME",
    "K_LOCKED",
    "LAW_NONE",
    "LAW_SHADOW",
    "OVERALL_INCONCLUSIVE",
    "OVERALL_MEASURE",
    "PAPER_DROP_H_A",
    "PAPER_DROP_W_A",
    "PAPER_N_EXIT_SCALE_A",
    "PATH_A_NAME",
    "PATH_B_NAME",
    "PATH_EARLY_A_NAME",
    "PATH_EARLY_B_NAME",
    "PATH_EXIT_K3_SHADOW",
    "PATH_EXIT_K3_THRESHOLD",
    "PATH_UNREAL_A_NAME",
    "PATH_UNREAL_B_NAME",
    "PATH_UNREAL_FLAGS_NAME",
    "PR26_MERGE_SHA",
    "SOURCE",
    "T_LOCK",
    "TRAIN_SEED",
    "PathExitK3ProtocolError",
    "assert_eval_seed",
    "assert_isolated_write",
    "assert_not_evaluated_policy",
    "assert_parent_sha",
    "assert_wire_vs_path_early_a",
    "honesty_paragraph",
    "isolated_workspace",
    "load_close_jsonl",
    "overall_path_exit_k3_string",
    "path_early_source_path",
    "path_exit_k3_ledger_path",
    "path_exit_k3_shadow_enabled",
    "path_exit_k3_threshold",
    "policy_only_rows",
    "price_sha16",
    "reports_dir",
    "resolve_parent_path",
    "should_path_exit_k3",
    "universe_rows",
    "winners_from_u",
]
