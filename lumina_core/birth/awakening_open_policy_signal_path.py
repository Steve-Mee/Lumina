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
    "open_policy_p_chosen": "P(taken action) via extract_policy_signals",
    "open_policy_action_margin": "p_chosen - max(p_other) via extract_policy_signals",
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
    flags_text = (REPO_ROOT / FLAGS_REL).read_text(encoding="utf-8") if (REPO_ROOT / FLAGS_REL).is_file() else ""
    dump: dict[str, Any] = {
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "last_open_signal": f"{GRIND_REL}:{_line_of(GRIND_REL, 'self.last_open_signal = extract_policy_signals')}",
        "parent_sha_const": f"{SIGNAL_REL}:{_line_of(SIGNAL_REL, 'INIT_SHA256 = \"8cc435c6')}",
        "p_value": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_VALUE = \"P_VALUE\"')}",
        "p_entropy": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_ENTROPY = \"P_ENTROPY\"')}",
        "p_action_margin": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'P_ACTION_MARGIN = \"P_ACTION_MARGIN\"')}",
        "extract_policy_signals": f"{EXTRACT_REL}:{_line_of(EXTRACT_REL, 'def extract_policy_signals')}",
        "s_split": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_split')}",
        "s_missing_signal": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_missing_signal')}",
        "s_missing_u": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'flag_s_missing_u')}",
        "licensed_next_family_h_none": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'FAMILY_H_NONE = \"H_NONE\"')}",
        "license_never_open_decision": (
            f"{FLAGS_REL}:ok" if "OPEN_DECISION" not in flags_text else f"{FLAGS_REL}:-1"
        ),
        "overall_inconclusive": (
            f"{SIGNAL_REL}:{_line_of(SIGNAL_REL, 'return OVERALL_INCONCLUSIVE')}"
        ),
        "isolated_workspace": f"{SIGNAL_REL}:{_line_of(SIGNAL_REL, 'def isolated_workspace')}",
        "forbidden_writes": f"{SIGNAL_REL}:{_line_of(SIGNAL_REL, 'FORBIDDEN_WRITE_NAMES')}",
        "forbidden_open_split_jsonl": (
            f"{SIGNAL_REL}:{_line_of(SIGNAL_REL, 'open_split_A_close_ledger.jsonl')}"
        ),
        "select_step_r": f"{SELECT_ENV_REL}:{_line_of(SELECT_ENV_REL, 'info[\"select_step_r\"]')}",
        "close_ledger_open_policy_value": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"open_policy_value\"')}",
        "close_ledger_open_policy_entropy": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"open_policy_entropy\"')}",
        "close_ledger_open_policy_action_margin": (
            f"{TRACE_REL}:{_line_of(TRACE_REL, '\"open_policy_action_margin\"')}"
        ),
        "close_ledger_open_policy_p_chosen": f"{TRACE_REL}:{_line_of(TRACE_REL, '\"open_policy_p_chosen\"')}",
        "telem_open_policy_value": f"{TELEM_REL}:{_line_of(TELEM_REL, 'open_policy_value: float | None = None')}",
        "telem_open_policy_entropy": f"{TELEM_REL}:{_line_of(TELEM_REL, 'open_policy_entropy: float | None = None')}",
        "telem_open_policy_action_margin": (
            f"{TELEM_REL}:{_line_of(TELEM_REL, 'open_policy_action_margin: float | None = None')}"
        ),
        "telem_open_policy_p_chosen": (
            f"{TELEM_REL}:{_line_of(TELEM_REL, 'open_policy_p_chosen: float | None = None')}"
        ),
        "sim_runner_last_open_signal": (
            f"{SIM_REL}:{_line_of(SIM_REL, 'last_open_signal')}"
        ),
        "run_evaluate_only_call": (
            f"{SIGNAL_RUN_REL}:{_line_of(SIGNAL_RUN_REL, 'run_evaluate_only(')}"
        ),
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
        "live_policy_signal_stash_attr_paths": dict(POLICY_SIGNAL_STASH_ATTR_PATHS),
    }
    required = (
        "evaluate_only_learn",
        "last_open_signal",
        "parent_sha_const",
        "p_value",
        "p_entropy",
        "p_action_margin",
        "extract_policy_signals",
        "s_split",
        "s_missing_signal",
        "s_missing_u",
        "licensed_next_family_h_none",
        "license_never_open_decision",
        "overall_inconclusive",
        "isolated_workspace",
        "forbidden_writes",
        "forbidden_open_split_jsonl",
        "select_step_r",
        "close_ledger_open_policy_value",
        "close_ledger_open_policy_entropy",
        "close_ledger_open_policy_action_margin",
        "close_ledger_open_policy_p_chosen",
        "telem_open_policy_value",
        "telem_open_policy_entropy",
        "telem_open_policy_action_margin",
        "telem_open_policy_p_chosen",
        "sim_runner_last_open_signal",
        "run_evaluate_only_call",
        "gitpython_pin",
        "codecov_patch_50",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["POLICY_SIGNAL_STASH_ATTR_PATHS", "inspect_open_policy_signal_protocol"]
