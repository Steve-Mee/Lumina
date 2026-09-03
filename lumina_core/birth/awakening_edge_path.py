"""Live geometry dump for Awakening E_EDGE (file:line). Measurement only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GRIND_RUN_REL = "lumina_core/birth/awakening_grind_run.py"
SIM_RUNNER_REL = "lumina_core/birth/sim_runner.py"
GEO_REL = "lumina_core/birth/birth_trade_geometry.py"
STOP_FILL_REL = "lumina_core/rl/gym_stop_fill.py"
GYM_STEP_REL = "lumina_core/rl/gym_environment_step.py"
GYM_ENV_REL = "lumina_core/rl/gym_environment.py"
GYM_CLOSE_REL = "lumina_core/rl/gym_birth_close.py"
NOTIONAL_REL = "lumina_core/birth/notional_cap.py"
METRICS_REL = "lumina_core/birth/foundation_metrics.py"
BIRTH_INIT_REL = "lumina_core/birth/stage_loop_session_phase_prepare_init.py"
BIRTH_CYCLE_REL = "lumina_core/birth/stage_loop_rollout_cycle.py"
ENVELOPE_REL = "lumina_core/birth/stage2_participation_envelope.py"


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def _src(rel: str) -> str:
    path = REPO_ROOT / rel
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def inspect_grind_geometry_path() -> dict[str, Any]:
    """File:line dump of grind vs Birth gym stop/target/time-stop/fill."""
    grind = _src(GRIND_RUN_REL)
    sim = _src(SIM_RUNNER_REL)
    gym_step = _src(GYM_STEP_REL)
    gym_env = _src(GYM_ENV_REL)
    gym_close = _src(GYM_CLOSE_REL)
    notional = _src(NOTIONAL_REL)
    stop_fill = _src(STOP_FILL_REL)
    geo = _src(GEO_REL)
    birth_init = _src(BIRTH_INIT_REL)
    birth_cycle = _src(BIRTH_CYCLE_REL)
    same_calibrate = (
        "calibrate_birth_stops(holdout)" in grind
        and "def calibrate_birth_stops" in geo
        and "calibrate_birth_stops(pool, max_hold_bars=hold)" in birth_init
    )
    same_trade_geo = '"trade_geometry": geometry' in grind and "trade_geometry=getattr(self" in birth_cycle
    same_fill = "plan_birth_exit_fill" in gym_step and "def plan_birth_exit_fill" in stop_fill
    same_pnl = "birth_fill_pnl_usd" in gym_step and "def birth_fill_pnl_usd" in notional
    same_clip = "book_birth_close_net_usd" in gym_step and "clip_birth_exam_pnl" in gym_close
    qty_one = "qty=1" in gym_close and "def birth_force_qty_one" in stop_fill
    mes5 = "birth_gym_point_value" in gym_env and "MES $5" in notional
    time_stop = "force_time_stop_this_step" in sim and 'BirthExitFill("time_stop"' in stop_fill
    clip_gap_shared = same_fill and same_clip and "row_is_segment_gap" in gym_step
    dump: dict[str, Any] = {
        "calibrate_grind": f"{GRIND_RUN_REL}:{_line_of(GRIND_RUN_REL, 'geometry = calibrate_birth_stops(holdout)')}",
        "calibrate_def": f"{GEO_REL}:{_line_of(GEO_REL, 'def calibrate_birth_stops')}",
        "calibrate_birth_s5": (
            f"{BIRTH_INIT_REL}:{_line_of(BIRTH_INIT_REL, 'geo = calibrate_birth_stops(pool, max_hold_bars=hold)')}"
        ),
        "trade_geometry_grind": f"{GRIND_RUN_REL}:{_line_of(GRIND_RUN_REL, '"trade_geometry": geometry')}",
        "trade_geometry_birth": (
            f"{BIRTH_CYCLE_REL}:{_line_of(BIRTH_CYCLE_REL, 'trade_geometry=getattr(self, "_birth_trade_geometry"')}"
        ),
        "stop_pct_sim": f"{SIM_RUNNER_REL}:{_line_of(SIM_RUNNER_REL, 'default_stop_pct=float(geometry.stop_pct)')}",
        "target_pct_sim": f"{SIM_RUNNER_REL}:{_line_of(SIM_RUNNER_REL, 'default_target_pct=float(geometry.target_pct)')}",
        "net_rr_field": f"{GEO_REL}:{_line_of(GEO_REL, 'net_rr_after_cost: float = 0.0')}",
        "finalize_geometry": f"{GEO_REL}:{_line_of(GEO_REL, 'def _finalize_geometry')}",
        "hold_bars_sim": (
            f"{SIM_RUNNER_REL}:{_line_of(SIM_RUNNER_REL, 'max_hold_bars = int(getattr(geometry, "hold_bars"')}"
        ),
        "force_time_sim": (
            f"{SIM_RUNNER_REL}:{_line_of(SIM_RUNNER_REL, 'env.config.force_time_stop_this_step = bool')}"
        ),
        "force_time_gym": f"{GYM_STEP_REL}:{_line_of(GYM_STEP_REL, 'force_time_now = bool')}",
        "force_time_envelope": f"{ENVELOPE_REL}:{_line_of(ENVELOPE_REL, 'force_time_stop=True')}",
        "plan_birth_exit_fill": f"{STOP_FILL_REL}:{_line_of(STOP_FILL_REL, 'def plan_birth_exit_fill')}",
        "plan_call_gym": f"{GYM_STEP_REL}:{_line_of(GYM_STEP_REL, 'fill_plan = plan_birth_exit_fill(')}",
        "birth_fill_pnl_usd": f"{NOTIONAL_REL}:{_line_of(NOTIONAL_REL, 'def birth_fill_pnl_usd')}",
        "fill_call_gym": f"{GYM_STEP_REL}:{_line_of(GYM_STEP_REL, 'realized_pnl = birth_fill_pnl_usd(')}",
        "clip": f"{GYM_CLOSE_REL}:{_line_of(GYM_CLOSE_REL, 'return clip_birth_exam_pnl')}",
        "qty_one": f"{GYM_CLOSE_REL}:{_line_of(GYM_CLOSE_REL, 'qty=1')}",
        "mes5": f"{GYM_ENV_REL}:{_line_of(GYM_ENV_REL, 'return birth_gym_point_value()')}",
        "intended_risk": f"{METRICS_REL}:{_line_of(METRICS_REL, 'def intended_risk_usd')}",
        "trade_r": f"{GYM_CLOSE_REL}:{_line_of(GYM_CLOSE_REL, 'trade_r =')}",
        "same_calibrate": same_calibrate,
        "same_trade_geo": same_trade_geo,
        "same_fill": same_fill,
        "same_pnl": same_pnl,
        "same_clip": same_clip,
        "qty_one_live": qty_one,
        "mes5_live": mes5,
        "time_stop_live": time_stop,
        "clip_gap_shared": clip_gap_shared,
    }
    dump["G_MISWIRE"] = not (
        same_calibrate and same_trade_geo and same_fill and same_pnl and same_clip and qty_one and mes5 and time_stop
    )
    return dump


__all__ = ["inspect_grind_geometry_path"]
