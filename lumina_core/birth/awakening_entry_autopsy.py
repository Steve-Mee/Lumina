"""Awakening ENTRY hole autopsy: flags, tables, JSONL readers. Measure-only.

Does not train. Does not implement OPEN_DECISION or REGIME_FLIP_EXIT.
Gate 1 law is always NONE. SYNTHETIC ≡ LIVE: same splitter, same fill physics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_mech import load_close_jsonl
from lumina_core.birth.awakening_select import SelectProtocolError, price_sha16, reports_dir
from lumina_core.birth.awakening_entry_autopsy_tables import (
    FIRST_TOUCH_BARS,
    TREND_LABELS,
    cell_entry_stats,
    entry_label,
    hole_rows,
    missing_entry,
    optional_float,
    policy_only_rows,
    read_existing_hole_contrast,
    share,
    table_t0,
    table_t1,
    table_t2,
    table_t3,
    table_t4,
    target_rows,
)

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

ENTRY_A_NAME = "entry_autopsy_A_close_ledger.jsonl"
ENTRY_B_NAME = "entry_autopsy_B_close_ledger.jsonl"
SOURCE = "awakening_entry_autopsy"

HOLE_N_MIN = 40
MISSING_SHARE = 0.20
NEUTRAL_SHARE = 0.70
FLIP_SHARE = 0.50
FIRST_TOUCH_SHARE = 0.50

BASELINE_WR_POLICY_A = 0.34
BASELINE_N_POLICY_A = 150
WR_WIRE_DELTA = 0.03
N_WIRE_DELTA = 15

FAMILY_OPEN_DECISION = "OPEN_DECISION"
FAMILY_REGIME_FLIP_EXIT = "REGIME_FLIP_EXIT"
FAMILY_H_MIXED = "H_MIXED"
FAMILY_H_NONE = "H_NONE"
FAMILY_H_MISSING_ENTRY = "H_MISSING_ENTRY"
FAMILY_H_AB_DISAGREE = "H_AB_DISAGREE"

OVERALL_MEASURE = "GRIND_REGRESS_AWAKENING_OPEN ENTRY_HOLE_AUTOPSY ENTRY_MEASURE_ONLY"
OVERALL_INCONCLUSIVE = "GRIND_INCONCLUSIVE_AWAKENING_OPEN ENTRY_HOLE_AUTOPSY H_MISSING_ENTRY"

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
    }
)


class EntryAutopsyProtocolError(SelectProtocolError):
    """Fail-closed protocol violation (eval seed, isolated write, init)."""


def isolated_workspace(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else reports_dir()
    return base / "awakening_entry_autopsy" / "workspace"


def entry_ledger_path(root: Path | str | None = None, *, leg: str) -> Path:
    name = ENTRY_A_NAME if str(leg).upper() == "A" else ENTRY_B_NAME
    base = Path(root) if root is not None else reports_dir()
    if base.name == "workspace" and base.parent.name == "birth_cloud_run":
        return base.parent / "artifacts" / name
    if base.name == "artifacts":
        return base / name
    return base / "artifacts" / name


def assert_eval_seed(seed: int) -> int:
    n = int(seed)
    if n == TRAIN_SEED:
        raise EntryAutopsyProtocolError(f"eval refuses train seed {n}")
    if n not in EVAL_SEEDS:
        raise EntryAutopsyProtocolError(f"eval seed must be A/B only, got {n}")
    return n


def assert_isolated_write(path: Path | str) -> Path:
    target = Path(path)
    if target.name in FORBIDDEN_WRITE_NAMES:
        raise EntryAutopsyProtocolError(f"forbidden write {target.name}")
    posix = target.as_posix()
    if "/lumina_agents/ppo/" in posix and posix.endswith(".zip"):
        raise EntryAutopsyProtocolError("forbidden write to gitignored ppo zip")
    return target


def assert_not_evaluated_policy(path: Path | str) -> Path:
    """Refuse control / hole-tax / gitignored PPO as the evaluated zip."""
    from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip

    target = Path(path)
    if is_gitignored_ppo_zip(target):
        raise EntryAutopsyProtocolError("refused gitignored ppo zip as evaluated policy")
    if target.name in {CONTROL_ZIP_NAME, HOLE_TAX_ZIP_NAME}:
        raise EntryAutopsyProtocolError(f"refused {target.name} as evaluated policy")
    if target.is_file():
        sha = file_sha256(target)
        if sha == CONTROL_SHA256:
            raise EntryAutopsyProtocolError("refused control sha db7daf3b as evaluated policy")
        if sha == HOLE_TAX_SHA256:
            raise EntryAutopsyProtocolError("refused hole-tax sha ca2ae0e5 as evaluated policy")
    return target


def assert_parent_sha(path: Path | str) -> str:
    from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip

    target = Path(path)
    assert_not_evaluated_policy(target)
    if is_gitignored_ppo_zip(target):
        raise EntryAutopsyProtocolError("refused gitignored ppo zip as init")
    if not target.is_file():
        raise EntryAutopsyProtocolError(f"parent zip missing: {target}")
    sha = file_sha256(target)
    if sha != INIT_SHA256:
        raise EntryAutopsyProtocolError(f"parent sha256 mismatch {sha} != {INIT_SHA256}")
    return sha


def resolve_parent_path(workspace_root: Path | str | None = None) -> Path:
    from lumina_core.birth.awakening_select import resolve_select_init_path

    path = resolve_select_init_path(workspace_root)
    assert_not_evaluated_policy(path)
    if path.name != INIT_ZIP_NAME:
        raise EntryAutopsyProtocolError(f"evaluated zip must be {INIT_ZIP_NAME}, got {path.name}")
    return path


def flag_h_missing_entry(
    *,
    n_h: int,
    missing_entry: float,
    missing_mae: float = 0.0,
) -> bool:
    return (
        int(n_h) < HOLE_N_MIN
        or float(missing_entry) >= MISSING_SHARE - 1e-12
        or float(missing_mae) >= MISSING_SHARE - 1e-12
    )


def flag_h_entry_neutral(*, h_missing: bool, frac_neu: float) -> bool:
    return (not bool(h_missing)) and float(frac_neu) >= NEUTRAL_SHARE - 1e-12


def flag_h_entry_flip(*, h_missing: bool, frac_tr: float) -> bool:
    return (not bool(h_missing)) and float(frac_tr) >= FLIP_SHARE - 1e-12


def flag_h_first_touch(*, h_missing: bool, h_neutral: bool, frac_ft: float) -> bool:
    return (not bool(h_missing)) and bool(h_neutral) and float(frac_ft) >= FIRST_TOUCH_SHARE - 1e-12


def licensed_future_family(
    *,
    h_missing: bool,
    h_neutral: bool,
    h_flip: bool,
) -> str:
    """Licensing string only. Does not implement a controller."""
    if bool(h_missing):
        return FAMILY_H_MISSING_ENTRY
    if bool(h_neutral) and bool(h_flip):
        return FAMILY_H_MIXED
    if bool(h_neutral) and not bool(h_flip):
        return FAMILY_OPEN_DECISION
    if bool(h_flip) and not bool(h_neutral):
        return FAMILY_REGIME_FLIP_EXIT
    return FAMILY_H_NONE


def compute_entry_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    hole = hole_rows(policy)
    n_h = len(hole)
    n_neu = sum(1 for r in hole if entry_label(r) == "NEUTRAL")
    n_tr = sum(1 for r in hole if (entry_label(r) or "") in TREND_LABELS)
    n_miss = sum(1 for r in hole if missing_entry(r))
    n_mae_miss = sum(1 for r in hole if optional_float(r, "mae_r") is None)
    n_ft = sum(
        1
        for r in hole
        if r.get("bars_held") is not None and int(r.get("bars_held") or 0) <= FIRST_TOUCH_BARS
    )
    frac_neu = share(n_neu, n_h)
    frac_tr = share(n_tr, n_h)
    frac_ft = share(n_ft, n_h)
    missing_entry_frac = share(n_miss, n_h)
    missing_mae = share(n_mae_miss, n_h)
    h_missing = flag_h_missing_entry(
        n_h=n_h, missing_entry=missing_entry_frac, missing_mae=missing_mae
    )
    h_neutral = flag_h_entry_neutral(h_missing=h_missing, frac_neu=frac_neu)
    h_flip = flag_h_entry_flip(h_missing=h_missing, frac_tr=frac_tr)
    h_ft = flag_h_first_touch(h_missing=h_missing, h_neutral=h_neutral, frac_ft=frac_ft)
    missing_fields: list[str] = []
    if n_h > 0 and missing_entry_frac >= MISSING_SHARE - 1e-12:
        missing_fields.append("entry_regime")
    if n_h > 0 and missing_mae >= MISSING_SHARE - 1e-12:
        missing_fields.append("mae_r")
    if n_h < HOLE_N_MIN:
        missing_fields.append("n_H")
    return {
        "n_H": n_h,
        "frac_neu": frac_neu,
        "frac_tr": frac_tr,
        "frac_ft": frac_ft,
        "missing_entry": missing_entry_frac,
        "missing_mae": missing_mae,
        "H_MISSING_ENTRY": h_missing,
        "H_ENTRY_NEUTRAL": h_neutral,
        "H_ENTRY_FLIP": h_flip,
        "H_FIRST_TOUCH": h_ft,
        "licensed_family": licensed_future_family(
            h_missing=h_missing, h_neutral=h_neutral, h_flip=h_flip
        ),
        "missing_fields": missing_fields,
        "gate1": "NONE",
    }


def assert_wire_vs_grind_a(*, wr_policy: float, n_policy: int) -> None:
    wr_off = abs(float(wr_policy) - BASELINE_WR_POLICY_A) > WR_WIRE_DELTA + 1e-12
    n_off = abs(int(n_policy) - BASELINE_N_POLICY_A) > N_WIRE_DELTA
    if wr_off and n_off:
        raise EntryAutopsyProtocolError(
            f"wire change: wr_policy={wr_policy} vs {BASELINE_WR_POLICY_A} "
            f"and n_policy={n_policy} vs {BASELINE_N_POLICY_A}"
        )


def honesty_paragraph(family: str) -> str:
    if family == FAMILY_OPEN_DECISION:
        return (
            "Hole entries are already NEUTRAL. Next ticket may tax or refuse the open, "
            "not the close. Exam still grades NEUTRAL."
        )
    if family == FAMILY_REGIME_FLIP_EXIT:
        return (
            "Hole closes NEUTRAL after a TREND entry. Next ticket is flip-exit, "
            "not another close-tax."
        )
    return "No train law licensed."


def overall_entry_string(*, parent_loaded: bool) -> str:
    if not parent_loaded:
        return OVERALL_INCONCLUSIVE
    return OVERALL_MEASURE


__all__ = [
    "BASELINE_N_POLICY_A",
    "BASELINE_WR_POLICY_A",
    "CONTROL_SHA256",
    "CONTROL_ZIP_NAME",
    "ENTRY_A_NAME",
    "ENTRY_B_NAME",
    "EVAL_A_SEED",
    "EVAL_B_SEED",
    "EVAL_SEEDS",
    "EntryAutopsyProtocolError",
    "FAMILY_H_AB_DISAGREE",
    "FAMILY_H_MISSING_ENTRY",
    "FAMILY_H_MIXED",
    "FAMILY_H_NONE",
    "FAMILY_OPEN_DECISION",
    "FAMILY_REGIME_FLIP_EXIT",
    "FORBIDDEN_WRITE_NAMES",
    "HOLE_TAX_SHA256",
    "HOLE_TAX_ZIP_NAME",
    "INIT_SHA256",
    "INIT_ZIP_NAME",
    "OVERALL_INCONCLUSIVE",
    "OVERALL_MEASURE",
    "SOURCE",
    "TRAIN_SEED",
    "assert_eval_seed",
    "assert_isolated_write",
    "assert_not_evaluated_policy",
    "assert_parent_sha",
    "assert_wire_vs_grind_a",
    "cell_entry_stats",
    "compute_entry_flags",
    "entry_ledger_path",
    "flag_h_entry_flip",
    "flag_h_entry_neutral",
    "flag_h_first_touch",
    "flag_h_missing_entry",
    "honesty_paragraph",
    "hole_rows",
    "isolated_workspace",
    "licensed_future_family",
    "load_close_jsonl",
    "overall_entry_string",
    "policy_only_rows",
    "price_sha16",
    "read_existing_hole_contrast",
    "reports_dir",
    "resolve_parent_path",
    "table_t0",
    "table_t1",
    "table_t2",
    "table_t3",
    "table_t4",
    "target_rows",
]
