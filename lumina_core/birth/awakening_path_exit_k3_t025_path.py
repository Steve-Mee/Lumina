"""Gate 0 file:line dump for Awakening PATH_EXIT K3 T025 transfer shadow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_REL = "lumina_core/birth/awakening_path_exit_k3.py"
T025_REL = "lumina_core/birth/awakening_path_exit_k3_t025.py"
HOOK_REL = "lumina_core/birth/awakening_path_exit_k3_hook.py"
FLAGS_REL = "lumina_core/birth/awakening_path_exit_k3_t025_flags.py"
EVAL_REL = "lumina_core/birth/awakening_path_exit_k3_t025_eval.py"
RUN_REL = "lumina_core/birth/awakening_path_exit_k3_t025_run.py"
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


def inspect_path_exit_k3_t025_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = do not run Gate 1."""
    dump: dict[str, Any] = {
        "t_fp": f"{T025_REL}:{_line_of(T025_REL, 'T_FP = -0.25')}",
        "t_lock": f"{CORE_REL}:{_line_of(CORE_REL, 'T_LOCK = -0.04787176712367987')}",
        "threshold_var": f"{CORE_REL}:{_line_of(CORE_REL, 'PATH_EXIT_K3_THRESHOLD')}",
        "should_reads_threshold": (
            f"{CORE_REL}:{_line_of(CORE_REL, 'thr = path_exit_k3_threshold()')}"
        ),
        "after_open_telem": (
            f"{HOOK_REL}:{_line_of(HOOK_REL, 'def after_open_telem_path_exit_k3')}"
        ),
        "shadow_set": f"{EVAL_REL}:{_line_of(EVAL_REL, 'PATH_EXIT_K3_SHADOW.set')}",
        "threshold_set": f"{EVAL_REL}:{_line_of(EVAL_REL, 'PATH_EXIT_K3_THRESHOLD.set')}",
        "license_transfer": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def license_transfer')}",
        "transfer_ok_requires_a_and_b": (
            f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'moved_a and moved_b')}"
        ),
        "forbidden_write_path_exit_k3_jsonl": (
            f"{T025_REL}:{_line_of(T025_REL, 'path_exit_k3_A_close_ledger.jsonl')}"
        ),
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "parent_sha_const": f"{CORE_REL}:{_line_of(CORE_REL, 'INIT_SHA256 = \"8cc435c6')}",
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
        "run_shadow_set": f"{RUN_REL}:{_line_of(RUN_REL, 'PATH_EXIT_K3_SHADOW.set')}",
        "run_threshold_set": f"{RUN_REL}:{_line_of(RUN_REL, 'PATH_EXIT_K3_THRESHOLD.set')}",
    }
    required = (
        "t_fp",
        "t_lock",
        "threshold_var",
        "should_reads_threshold",
        "after_open_telem",
        "shadow_set",
        "threshold_set",
        "license_transfer",
        "transfer_ok_requires_a_and_b",
        "forbidden_write_path_exit_k3_jsonl",
        "evaluate_only_learn",
        "parent_sha_const",
        "gitpython_pin",
        "codecov_patch_50",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["inspect_path_exit_k3_t025_protocol"]
