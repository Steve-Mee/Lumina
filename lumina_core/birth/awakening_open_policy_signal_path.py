"""Gate 0 file:line dump for Awakening OPEN_POLICY_SIGNAL protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SIGNAL_REL = "lumina_core/birth/awakening_open_policy_signal.py"
FLAGS_REL = "lumina_core/birth/awakening_open_policy_signal_flags.py"
SIGNAL_RUN_REL = "lumina_core/birth/awakening_open_policy_signal_run.py"
EXTRACT_REL = "lumina_core/birth/policy_signal_extract.py"
SELECT_ENV_REL = "lumina_core/birth/awakening_select_env.py"
GRIND_REL = "lumina_core/birth/awakening_grind.py"
TRACE_REL = "lumina_core/birth/s5_close_ledger_trace.py"
TELEM_REL = "lumina_core/birth/sim_runner_entry_telem.py"
SIM_REL = "lumina_core/birth/sim_runner.py"
REQ_REL = "requirements-core.txt"
CODECOV_REL = "codecov.yml"

POLICY_SIGNAL_STASH_ATTR_PATHS = {
    "open_policy_value": "policy.predict_values(obs) via extract_policy_signals",
    "open_policy_entropy": "dist.entropy() via extract_policy_signals",
    "open_policy_action_margin": "sorted(probs)[0]-sorted(probs)[1] via extract_policy_signals",
}


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_open_policy_signal_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = Gate 0 fail."""
    dump: dict[str, Any] = {
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "parent_sha_const": f"{SIGNAL_REL}:{_line_of(SIGNAL_REL, 'INIT_SHA256 = ')}",
        "p_value": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_VALUE')}",
        "p_entropy": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_ENTROPY')}",
        "p_action_margin": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_ACTION_MARGIN')}",
        "extract_policy_signals": f"{EXTRACT_REL}:{_line_of(EXTRACT_REL, 'def extract_policy_signals')}",
        "sim_runner_extract_call": f"{SIM_REL}:{_line_of(SIM_REL, 'extract_policy_signals(policy')}",
        "s_split": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_split')}",
        "s_harm": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_harm')}",
        "isolated_workspace": f"{SIGNAL_REL}:{_line_of(SIGNAL_REL, 'def isolated_workspace')}",
        "forbidden_writes": f"{SIGNAL_REL}:{_line_of(SIGNAL_REL, 'FORBIDDEN_WRITE_NAMES')}",
        "select_step_r": f"{SELECT_ENV_REL}:{_line_of(SELECT_ENV_REL, 'info[\"select_step_r\"]')}",
        "close_ledger_open_policy_value": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"open_policy_value\"')}",
        "close_ledger_open_policy_entropy": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"open_policy_entropy\"')}",
        "close_ledger_open_policy_action_margin": (
            f"{TRACE_REL}:{_line_of(TRACE_REL, '\"open_policy_action_margin\"')}"
        ),
        "telem_open_policy_value": f"{TELEM_REL}:{_line_of(TELEM_REL, '\"open_policy_value\"')}",
        "telem_open_policy_entropy": f"{TELEM_REL}:{_line_of(TELEM_REL, '\"open_policy_entropy\"')}",
        "telem_open_policy_action_margin": f"{TELEM_REL}:{_line_of(TELEM_REL, '\"open_policy_action_margin\"')}",
        "run_evaluate_only_call": (
            f"{SIGNAL_RUN_REL}:{_line_of(SIGNAL_RUN_REL, 'run_evaluate_only(')}"
        ),
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
        "live_policy_signal_stash_attr_paths": dict(POLICY_SIGNAL_STASH_ATTR_PATHS),
    }
    required = (
        "evaluate_only_learn",
        "parent_sha_const",
        "p_value",
        "p_entropy",
        "p_action_margin",
        "extract_policy_signals",
        "sim_runner_extract_call",
        "s_split",
        "s_harm",
        "isolated_workspace",
        "forbidden_writes",
        "select_step_r",
        "close_ledger_open_policy_value",
        "close_ledger_open_policy_entropy",
        "close_ledger_open_policy_action_margin",
        "telem_open_policy_value",
        "telem_open_policy_entropy",
        "telem_open_policy_action_margin",
        "run_evaluate_only_call",
        "gitpython_pin",
        "codecov_patch_50",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["POLICY_SIGNAL_STASH_ATTR_PATHS", "inspect_open_policy_signal_protocol"]
