"""Gate 0 file:line dump for Awakening OPEN_SPLIT protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SPLIT_REL = "lumina_core/birth/awakening_open_split.py"
FLAGS_REL = "lumina_core/birth/awakening_open_split_flags.py"
SPLIT_RUN_REL = "lumina_core/birth/awakening_open_split_run.py"
SELECT_ENV_REL = "lumina_core/birth/awakening_select_env.py"
GRIND_REL = "lumina_core/birth/awakening_grind.py"
TRACE_REL = "lumina_core/birth/s5_close_ledger_trace.py"
TELEM_REL = "lumina_core/birth/sim_runner_entry_telem.py"
SIM_REL = "lumina_core/birth/sim_runner.py"
REQ_REL = "requirements-core.txt"
CODECOV_REL = "codecov.yml"

STASH_ATTR_PATHS = {
    "open_occ_flat": "host.occupancy_control_flat | info.get('occupancy_control_flat')",
    "open_cum_flat": (
        "host.stage_range_flat_bars/stage_range_total_signals | host.range_flat_bars/range_total_signals"
    ),
    "open_in_band_seen": "host.occupancy_in_band_seen | info.get('occupancy_in_band_seen')",
    "open_session_phase": "tick['bible_session_phase'] if key present",
    "open_confluence": "tick['bible_confluence'] if key present",
    "open_news_proximity": "tick['bible_news_proximity'] if key present",
    "open_imbalance": "tick['imbalance'] iff key present and value is not None",
    "open_range_stop_frac": (
        "(high-low)/entry / stop_pct via host.geometry.stop_pct | envelope.participation_stop_pct | info.stop_pct"
    ),
    "open_side": "stash.side from start_open_telem",
    "bars_since_prev_policy_stop": "entry_bar - host._last_policy_stop_bar (omit if none)",
    "open_participation_mode": ("host.config.participation_mode | info.participation_mode | host.participation_mode"),
}


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_open_split_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = Gate 0 fail."""
    dump: dict[str, Any] = {
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "parent_sha_const": f"{SPLIT_REL}:{_line_of(SPLIT_REL, 'INIT_SHA256 = "8cc435c6')}",
        "f_occ_floor": f"{SPLIT_REL}:{_line_of(SPLIT_REL, 'F_OCC_FLOOR')}",
        "f_session_early": f"{SPLIT_REL}:{_line_of(SPLIT_REL, 'F_SESSION_EARLY')}",
        "f_tight_range": f"{SPLIT_REL}:{_line_of(SPLIT_REL, 'F_TIGHT_RANGE')}",
        "f_after_stop": f"{SPLIT_REL}:{_line_of(SPLIT_REL, 'F_AFTER_STOP')}",
        "f_imbal_flat": f"{SPLIT_REL}:{_line_of(SPLIT_REL, 'F_IMBAL_FLAT')}",
        "occupancy_floor_neighborhood": (f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'occupancy_floor_neighborhood')}"),
        "s_split": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_split')}",
        "s_harm": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_harm')}",
        "s_missing_u": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'def flag_s_missing_u')}",
        "isolated_workspace": f"{SPLIT_REL}:{_line_of(SPLIT_REL, 'def isolated_workspace')}",
        "forbidden_writes": f"{SPLIT_REL}:{_line_of(SPLIT_REL, 'FORBIDDEN_WRITE_NAMES')}",
        "select_step_r": f"{SELECT_ENV_REL}:{_line_of(SELECT_ENV_REL, 'info["select_step_r"]')}",
        "close_ledger_open_occ_flat": f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_occ_flat"')}",
        "close_ledger_open_cum_flat": f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_cum_flat"')}",
        "close_ledger_open_in_band_seen": (f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_in_band_seen"')}"),
        "close_ledger_open_session_phase": (f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_session_phase"')}"),
        "close_ledger_open_confluence": f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_confluence"')}",
        "close_ledger_open_news_proximity": (f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_news_proximity"')}"),
        "close_ledger_open_imbalance": f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_imbalance"')}",
        "close_ledger_open_range_stop_frac": (f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_range_stop_frac"')}"),
        "close_ledger_open_side": f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_side"')}",
        "close_ledger_bars_since": (f"{TRACE_REL}:{_line_of(TRACE_REL, '"bars_since_prev_policy_stop"')}"),
        "close_ledger_open_participation_mode": (f"{TRACE_REL}:{_line_of(TRACE_REL, '"open_participation_mode"')}"),
        "start_open_telem_optional": (f"{TELEM_REL}:{_line_of(TELEM_REL, 'open_occ_flat: float | None = None')}"),
        "gather_open_features": f"{TELEM_REL}:{_line_of(TELEM_REL, 'def gather_open_features')}",
        "update_open_telem_gather": f"{TELEM_REL}:{_line_of(TELEM_REL, 'gather_open_features(')}",
        "stamp_open_host": f"{SIM_REL}:{_line_of(SIM_REL, 'stamp_open_host(')}",
        "run_evaluate_only_call": (f"{SPLIT_RUN_REL}:{_line_of(SPLIT_RUN_REL, 'run_evaluate_only(')}"),
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
        "live_stash_attr_paths": dict(STASH_ATTR_PATHS),
        "live_stash_gather_site": (f"{TELEM_REL}:{_line_of(TELEM_REL, 'def gather_open_features')}"),
    }
    required = (
        "evaluate_only_learn",
        "parent_sha_const",
        "f_occ_floor",
        "f_session_early",
        "f_tight_range",
        "f_after_stop",
        "f_imbal_flat",
        "occupancy_floor_neighborhood",
        "s_split",
        "s_harm",
        "s_missing_u",
        "isolated_workspace",
        "forbidden_writes",
        "select_step_r",
        "close_ledger_open_occ_flat",
        "close_ledger_open_cum_flat",
        "close_ledger_open_in_band_seen",
        "close_ledger_open_session_phase",
        "close_ledger_open_confluence",
        "close_ledger_open_news_proximity",
        "close_ledger_open_imbalance",
        "close_ledger_open_range_stop_frac",
        "close_ledger_open_side",
        "close_ledger_bars_since",
        "close_ledger_open_participation_mode",
        "start_open_telem_optional",
        "gather_open_features",
        "update_open_telem_gather",
        "run_evaluate_only_call",
        "gitpython_pin",
        "codecov_patch_50",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["STASH_ATTR_PATHS", "inspect_open_split_protocol"]
