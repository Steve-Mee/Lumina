"""Gate 0 file:line dump plus U_k helpers for Awakening PATH_EARLY."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PATH_K_KEYS = {
    3: ("path_k3_mae_r", "path_k3_mfe_r", "path_k3_unreal_r"),
    5: ("path_k5_mae_r", "path_k5_mfe_r", "path_k5_unreal_r"),
}


def field_present(row: dict[str, Any], key: str) -> bool:
    return key in row and row.get(key) is not None


def opt_float(row: dict[str, Any], key: str) -> float | None:
    if not field_present(row, key):
        return None
    try:
        return float(row.get(key))
    except (TypeError, ValueError):
        return None


def bars_held(row: dict[str, Any]) -> int | None:
    if not field_present(row, "bars_held"):
        return None
    try:
        return int(row.get("bars_held"))
    except (TypeError, ValueError):
        return None


def median_values(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def snapshot_present(row: dict[str, Any], k: int) -> bool:
    return any(field_present(row, key) for key in PATH_K_KEYS[int(k)])


def still_open_at_k(universe: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in universe:
        held = bars_held(row)
        if held is not None and held >= int(k):
            out.append(row)
    return out


def universe_k(universe: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    """U_k = still-open-at-k AND path snapshot at k present. Died-before-k stay out."""
    return [r for r in still_open_at_k(universe, k) if snapshot_present(r, k)]


def compute_k_medians(u_k: list[dict[str, Any]], k: int) -> dict[str, float | None]:
    """Median per-k on U_k where the field is present. Does not use H/W labels."""
    mae_vals = [v for r in u_k for v in [opt_float(r, f"path_k{k}_mae_r")] if v is not None]
    unreal_vals = [v for r in u_k for v in [opt_float(r, f"path_k{k}_unreal_r")] if v is not None]
    return {"mae_r": median_values(mae_vals), "unreal_r": median_values(unreal_vals)}


def pred_mae_deep(row: dict[str, Any], *, k: int, threshold: float | None) -> bool:
    if threshold is None:
        return False
    value = opt_float(row, f"path_k{k}_mae_r")
    return value is not None and float(value) <= float(threshold)


def pred_unreal_red(row: dict[str, Any], *, k: int, threshold: float | None) -> bool:
    if threshold is None:
        return False
    value = opt_float(row, f"path_k{k}_unreal_r")
    return value is not None and float(value) <= float(threshold)


def pred_mae_flip(row: dict[str, Any], *, k: int, threshold: float | None) -> bool:
    if threshold is None:
        return False
    value = opt_float(row, f"path_k{k}_mae_r")
    return value is not None and float(value) > float(threshold)


def pred_unreal_flip(row: dict[str, Any], *, k: int, threshold: float | None) -> bool:
    if threshold is None:
        return False
    value = opt_float(row, f"path_k{k}_unreal_r")
    return value is not None and float(value) > float(threshold)

REPO_ROOT = Path(__file__).resolve().parents[2]
PATH_EARLY_REL = "lumina_core/birth/awakening_path_early.py"
FLAGS_REL = "lumina_core/birth/awakening_path_early_flags.py"
PATH_RUN_REL = "lumina_core/birth/awakening_path_early_run.py"
GRIND_REL = "lumina_core/birth/awakening_grind.py"
TRACE_REL = "lumina_core/birth/s5_close_ledger_trace.py"
TELEM_REL = "lumina_core/birth/sim_runner_entry_telem.py"
REQ_REL = "requirements-core.txt"
CODECOV_REL = "codecov.yml"

PATH_STASH_ATTR_PATHS = {
    "path_k3_mae_r": "snapshot_path_at_k mae_usd / intended_risk at bars_from_entry==3",
    "path_k3_mfe_r": "snapshot_path_at_k mfe_usd / intended_risk at bars_from_entry==3",
    "path_k3_unreal_r": "mark-to-close unreal_usd / intended_risk at bars_from_entry==3",
    "path_k5_mae_r": "snapshot_path_at_k mae_usd / intended_risk at bars_from_entry==5",
    "path_k5_mfe_r": "snapshot_path_at_k mfe_usd / intended_risk at bars_from_entry==5",
    "path_k5_unreal_r": "mark-to-close unreal_usd / intended_risk at bars_from_entry==5",
}


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_path_early_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = Gate 0 fail."""
    flags_text = (REPO_ROOT / FLAGS_REL).read_text(encoding="utf-8") if (REPO_ROOT / FLAGS_REL).is_file() else ""
    dump: dict[str, Any] = {
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "parent_sha_const": f"{PATH_EARLY_REL}:{_line_of(PATH_EARLY_REL, 'INIT_SHA256 = \"8cc435c6')}",
        "k_locked": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'K_LOCKED = (3, 5)')}",
        "p_k3_mae_deep": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_K3_MAE_DEEP = \"P_K3_MAE_DEEP\"')}",
        "p_k3_unreal_red": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_K3_UNREAL_RED = \"P_K3_UNREAL_RED\"')}",
        "p_k5_mae_deep": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_K5_MAE_DEEP = \"P_K5_MAE_DEEP\"')}",
        "p_k5_unreal_red": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_K5_UNREAL_RED = \"P_K5_UNREAL_RED\"')}",
        "s_split": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_split')}",
        "s_missing_path": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_missing_path')}",
        "licensed_next_family_h_none": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'FAMILY_H_NONE = \"H_NONE\"')}",
        "license_never_open_decision": (
            f"{FLAGS_REL}:ok" if "OPEN_DECISION" not in flags_text else f"{FLAGS_REL}:-1"
        ),
        "isolated_workspace": f"{PATH_EARLY_REL}:{_line_of(PATH_EARLY_REL, 'def isolated_workspace')}",
        "forbidden_writes": f"{PATH_EARLY_REL}:{_line_of(PATH_EARLY_REL, 'FORBIDDEN_WRITE_NAMES')}",
        "forbidden_policy_signal_jsonl": (
            f"{PATH_EARLY_REL}:{_line_of(PATH_EARLY_REL, 'policy_signal_A_close_ledger.jsonl')}"
        ),
        "forbidden_open_split_jsonl": (
            f"{PATH_EARLY_REL}:{_line_of(PATH_EARLY_REL, 'open_split_A_close_ledger.jsonl')}"
        ),
        "close_ledger_path_k3_mae_r": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"path_k3_mae_r\"')}",
        "close_ledger_path_k3_mfe_r": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"path_k3_mfe_r\"')}",
        "close_ledger_path_k3_unreal_r": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"path_k3_unreal_r\"')}",
        "close_ledger_path_k5_mae_r": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"path_k5_mae_r\"')}",
        "close_ledger_path_k5_mfe_r": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"path_k5_mfe_r\"')}",
        "close_ledger_path_k5_unreal_r": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"path_k5_unreal_r\"')}",
        "snapshot_site": f"{TELEM_REL}:{_line_of(TELEM_REL, 'def snapshot_path_at_k')}",
        "run_evaluate_only_call": f"{PATH_RUN_REL}:{_line_of(PATH_RUN_REL, 'run_evaluate_only(')}",
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
        "live_path_stash_attr_paths": dict(PATH_STASH_ATTR_PATHS),
    }
    required = (
        "evaluate_only_learn",
        "parent_sha_const",
        "k_locked",
        "p_k3_mae_deep",
        "p_k3_unreal_red",
        "p_k5_mae_deep",
        "p_k5_unreal_red",
        "s_split",
        "s_missing_path",
        "licensed_next_family_h_none",
        "license_never_open_decision",
        "isolated_workspace",
        "forbidden_writes",
        "forbidden_policy_signal_jsonl",
        "forbidden_open_split_jsonl",
        "close_ledger_path_k3_mae_r",
        "close_ledger_path_k3_mfe_r",
        "close_ledger_path_k3_unreal_r",
        "close_ledger_path_k5_mae_r",
        "close_ledger_path_k5_mfe_r",
        "close_ledger_path_k5_unreal_r",
        "snapshot_site",
        "run_evaluate_only_call",
        "gitpython_pin",
        "codecov_patch_50",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = [
    "PATH_STASH_ATTR_PATHS",
    "compute_k_medians",
    "inspect_path_early_protocol",
    "pred_mae_deep",
    "pred_mae_flip",
    "pred_unreal_flip",
    "pred_unreal_red",
    "snapshot_present",
    "still_open_at_k",
    "universe_k",
]
