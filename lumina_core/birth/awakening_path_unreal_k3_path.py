"""Gate 0 file:line dump for Awakening PATH_UNREAL_K3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_REL = "lumina_core/birth/awakening_path_unreal_k3.py"
FLAGS_REL = "lumina_core/birth/awakening_path_unreal_k3_flags.py"
GRIND_REL = "lumina_core/birth/awakening_grind.py"
REQ_REL = "requirements-core.txt"
CODECOV_REL = "codecov.yml"


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_path_unreal_k3_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = do not run Gate 1."""
    dump: dict[str, Any] = {
        "k_locked": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'K_LOCKED = 3')}",
        "candidate_names_only_k3_unreal": (
            f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'CANDIDATE_NAMES = (P_K3_UNREAL_RED,)')}"
        ),
        "pred_unreal_red": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'pred_unreal_red')}",
        "universe_k_reuse": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'universe_k')}",
        "still_open_at_k_reuse": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'still_open_at_k')}",
        "flag_s_split": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'flag_s_split')}",
        "split_lift_import": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'SPLIT_LIFT')}",
        "license_path_exit_p_k3_unreal_red": (
            f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'PATH_EXIT:P_K3_UNREAL_RED')}"
        ),
        "h_none_on_miss_none": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'licensed_next_family\": FAMILY_H_NONE')}",
        "forbidden_write_path_early_jsonl": (
            f"{CORE_REL}:{_line_of(CORE_REL, 'path_early_A_close_ledger.jsonl')}"
        ),
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "parent_sha_const": f"{CORE_REL}:{_line_of(CORE_REL, 'INIT_SHA256 = \"8cc435c6')}",
        "overall_inconclusive_branch": (
            f"{CORE_REL}:{_line_of(CORE_REL, 'return OVERALL_INCONCLUSIVE')}"
        ),
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
    }
    required = (
        "k_locked",
        "candidate_names_only_k3_unreal",
        "pred_unreal_red",
        "universe_k_reuse",
        "still_open_at_k_reuse",
        "flag_s_split",
        "split_lift_import",
        "license_path_exit_p_k3_unreal_red",
        "h_none_on_miss_none",
        "forbidden_write_path_early_jsonl",
        "evaluate_only_learn",
        "parent_sha_const",
        "overall_inconclusive_branch",
        "gitpython_pin",
        "codecov_patch_50",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["inspect_path_unreal_k3_protocol"]
