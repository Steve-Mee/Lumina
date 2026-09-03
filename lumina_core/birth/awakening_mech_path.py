"""Live-path dump for Awakening grind vs Birth S5 participation (file:line)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GRIND_RUN_REL = "lumina_core/birth/awakening_grind_run.py"
SIM_RUNNER_REL = "lumina_core/birth/sim_runner.py"
TRACE_REL = "lumina_core/birth/s5_close_ledger_trace.py"
IDLE_REL = "lumina_core/birth/stage3_inband_idle.py"
CLOCK_REL = "lumina_core/birth/foundation_skill_clock.py"


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_grind_live_path() -> dict[str, Any]:
    """File:line dump of grind evaluate-only vs Birth S5 participation pieces."""
    grind_src = (REPO_ROOT / GRIND_RUN_REL).read_text(encoding="utf-8")
    sim_src = (REPO_ROOT / SIM_RUNNER_REL).read_text(encoding="utf-8")
    trace_src = (REPO_ROOT / TRACE_REL).read_text(encoding="utf-8")
    envelope_enabled = (
        "participation_envelope_enabled" in grind_src
        and "foundation_occupancy_envelope_enabled" in grind_src
    )
    min_dwell = "participation_min_dwell_bars" in grind_src
    chatter_live = "chatter = ForceOpenChatterBound()" in sim_src
    refractory_live = "force_open_refractory=chatter.blocks" in sim_src
    plant_tag = '"plant":' in trace_src or "'plant':" in trace_src
    force_col = '"force_open"' in trace_src or "'force_open'" in trace_src
    clock_in_grind = "skill_clock_keeps_stage_open" in grind_src
    dump: dict[str, Any] = {
        "envelope_enabled_kwarg": envelope_enabled,
        "envelope_site": f"{GRIND_RUN_REL}:{_line_of(GRIND_RUN_REL, 'participation_envelope_enabled')}",
        "min_dwell_in_kwargs": min_dwell,
        "min_dwell_site": f"{GRIND_RUN_REL}:{_line_of(GRIND_RUN_REL, 'participation_min_dwell_bars')}",
        "occupancy_seed_site": f"{GRIND_RUN_REL}:{_line_of(GRIND_RUN_REL, 'def occupancy_seed_kwargs')}",
        "chatter_bound_constructed": chatter_live,
        "chatter_site": f"{SIM_RUNNER_REL}:{_line_of(SIM_RUNNER_REL, 'chatter = ForceOpenChatterBound()')}",
        "refractory_passed_to_decide": refractory_live,
        "refractory_site": f"{SIM_RUNNER_REL}:{_line_of(SIM_RUNNER_REL, 'force_open_refractory=chatter.blocks')}",
        "plant_tag_for_entry_site": f"{IDLE_REL}:{_line_of(IDLE_REL, 'def plant_tag_for_entry')}",
        "plant_column_on_close_row": plant_tag,
        "force_open_column_on_close_row": force_col,
        "close_ledger_row_site": f"{TRACE_REL}:{_line_of(TRACE_REL, 'def close_ledger_row')}",
        "skill_clock_in_grind_kwargs": clock_in_grind,
        "skill_clock_site": f"{CLOCK_REL}:{_line_of(CLOCK_REL, 'def skill_clock_keeps_stage_open')}",
        "rolling_occupancy_window_in_grind_kwargs": (
            "occupancy_control_window=" in grind_src and "occupancy_control_window_bars" in grind_src
        ),
        "jsonl_columns_expected": (
            "plant",
            "force_open",
            "close_reason",
            "gap",
            "regime",
            "trade_r",
            "pnl",
            "cap_hit",
        ),
    }
    dump["W_WIRE"] = (
        (not bool(envelope_enabled))
        or (not bool(chatter_live))
        or (not bool(refractory_live))
        or (not bool(min_dwell))
        or (not bool(plant_tag))
    )
    return dump


__all__ = ["inspect_grind_live_path"]
