"""Gate 0 file:line dump for Awakening PATH_EXIT K3 shadow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_REL = "lumina_core/birth/awakening_path_exit_k3.py"
FLAGS_REL = "lumina_core/birth/awakening_path_exit_k3_flags.py"
EVAL_REL = "lumina_core/birth/awakening_path_exit_k3_eval.py"
GRIND_REL = "lumina_core/birth/awakening_grind.py"
GRIND_RUN_REL = "lumina_core/birth/awakening_grind_run.py"
TELEM_REL = "lumina_core/birth/sim_runner_entry_telem.py"
SIM_REL = "lumina_core/birth/sim_runner.py"
LEDGER_REL = "lumina_core/birth/s5_close_ledger_trace.py"
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


def inspect_path_exit_k3_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = do not run Gate 1."""
    dump: dict[str, Any] = {
        "t_lock": f"{CORE_REL}:{_line_of(CORE_REL, 'T_LOCK = -0.04787176712367987')}",
        "should_path_exit_k3": f"{CORE_REL}:{_line_of(CORE_REL, 'def should_path_exit_k3')}",
        "hook_default_false": (
            f"{GRIND_RUN_REL}:{_line_of(GRIND_RUN_REL, 'path_exit_k3_shadow: bool = False')}"
        ),
        "snapshot_unreal_key": f"{TELEM_REL}:{_line_of(TELEM_REL, 'path_k3_unreal_r')}",
        "flatten_request_site": f"{SIM_REL}:{_line_of(SIM_REL, '_path_exit_k3_request')}",
        "path_exit_k3_ledger_key": f"{LEDGER_REL}:{_line_of(LEDGER_REL, 'path_exit_k3')}",
        "hole_moved_def": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_hole_moved')}",
        "s_harm_def": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_harm')}",
        "parent_sha_const": f"{CORE_REL}:{_line_of(CORE_REL, 'INIT_SHA256 = \"8cc435c6')}",
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "forbidden_write_path_early_jsonl": (
            f"{CORE_REL}:{_line_of(CORE_REL, 'path_early_A_close_ledger.jsonl')}"
        ),
        "run_evaluate_only_hook_true": (
            f"{EVAL_REL}:{_line_of(EVAL_REL, 'path_exit_k3_shadow=True')}"
        ),
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
    }
    required = (
        "t_lock",
        "should_path_exit_k3",
        "hook_default_false",
        "snapshot_unreal_key",
        "flatten_request_site",
        "path_exit_k3_ledger_key",
        "hole_moved_def",
        "s_harm_def",
        "parent_sha_const",
        "evaluate_only_learn",
        "forbidden_write_path_early_jsonl",
        "run_evaluate_only_hook_true",
        "gitpython_pin",
        "codecov_patch_50",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["inspect_path_exit_k3_protocol"]
