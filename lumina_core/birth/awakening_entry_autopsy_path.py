"""Gate 0 file:line dump for Awakening ENTRY hole autopsy protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTOPSY_REL = "lumina_core/birth/awakening_entry_autopsy.py"
AUTOPSY_RUN_REL = "lumina_core/birth/awakening_entry_autopsy_run.py"
SELECT_ENV_REL = "lumina_core/birth/awakening_select_env.py"
GRIND_REL = "lumina_core/birth/awakening_grind.py"
TRACE_REL = "lumina_core/birth/s5_close_ledger_trace.py"
SIM_REL = "lumina_core/birth/sim_runner.py"
REQ_REL = "requirements-core.txt"


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_entry_autopsy_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = Gate 0 fail."""
    dump: dict[str, Any] = {
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "parent_sha_const": f"{AUTOPSY_REL}:{_line_of(AUTOPSY_REL, 'INIT_SHA256 = \"8cc435c6')}",
        "h_entry_neutral": f"{AUTOPSY_REL}:{_line_of(AUTOPSY_REL, 'def flag_h_entry_neutral')}",
        "h_entry_flip": f"{AUTOPSY_REL}:{_line_of(AUTOPSY_REL, 'def flag_h_entry_flip')}",
        "h_missing_entry": f"{AUTOPSY_REL}:{_line_of(AUTOPSY_REL, 'def flag_h_missing_entry')}",
        "h_first_touch": f"{AUTOPSY_REL}:{_line_of(AUTOPSY_REL, 'def flag_h_first_touch')}",
        "isolated_workspace": f"{AUTOPSY_REL}:{_line_of(AUTOPSY_REL, 'def isolated_workspace')}",
        "forbidden_writes": f"{AUTOPSY_REL}:{_line_of(AUTOPSY_REL, 'FORBIDDEN_WRITE_NAMES')}",
        "select_step_r": f"{SELECT_ENV_REL}:{_line_of(SELECT_ENV_REL, 'info[\"select_step_r\"]')}",
        "close_ledger_row_keys": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"entry_regime\"')}",
        "sim_runner_open_stash": f"{SIM_REL}:{_line_of(SIM_REL, 'open_telem')}",
        "run_evaluate_only_call": (
            f"{AUTOPSY_RUN_REL}:{_line_of(AUTOPSY_RUN_REL, 'run_evaluate_only(')}"
        ),
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
    }
    required = (
        "evaluate_only_learn",
        "parent_sha_const",
        "h_entry_neutral",
        "h_entry_flip",
        "h_missing_entry",
        "h_first_touch",
        "isolated_workspace",
        "forbidden_writes",
        "select_step_r",
        "close_ledger_row_keys",
        "sim_runner_open_stash",
        "run_evaluate_only_call",
        "gitpython_pin",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["inspect_entry_autopsy_protocol"]
