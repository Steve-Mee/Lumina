"""T0–T3 tables for AWAKENING_GEOMETRY_REWARD. Measure only."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_geom_reward import GEOM_LOSS_R, GEOM_WIN_R
from lumina_core.birth.awakening_geom_tape import DRIFT_RTH, GEOM_TIMESTEPS
from lumina_core.birth.awakening_geom_touch import TARGET_FRAC_MIN
from lumina_core.birth.awakening_scale_enrich import PHYSICS_SLOPE_ABS, PROD_SLOPE_ABS
from lumina_core.birth.awakening_scale_tape import NQ_MAX, NQ_MIN, PHASE_BLOCKS
from lumina_core.birth.data_source_honesty import real_data_percentage, synthetic_source_reasons
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM

HONESTY_PARAGRAPH = (
    "LAW: last world knob was SCALE. This window is the Awakening payoff. "
    "First-touch gate 0.10. Policy goal 0.46 is not the gate. "
    "Train close reward is +1.21 / −1.04 / 0.0. Eval still scores ledger mean_r. "
    "a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. "
    "GENESIS_EYES_OK stays false. GEOM_OK is not Evolution Proof. REAL=no. "
    "Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape."
)


def table_t0_identity(
    *,
    origin_main: str,
    train_hash: str,
    baseline_sha: str,
    child_sha: str,
    seed_used: int,
) -> dict[str, Any]:
    return {
        "origin_main": str(origin_main),
        "seed_used": int(seed_used),
        "fixture_train_hash": str(train_hash),
        "baseline_sha256": str(baseline_sha),
        "child_sha256": str(child_sha),
        "init_policy": "scratch",
        "obs_dim": 46,
        "OBSERVATION_DIM": int(OBSERVATION_DIM),
        "POLICY_EDGE_MIN_TRADES": int(POLICY_EDGE_MIN_TRADES),
        "timesteps": int(GEOM_TIMESTEPS),
        "drift_rth": float(DRIFT_RTH),
        "phase_blocks": int(PHASE_BLOCKS),
        "nq_min": float(NQ_MIN),
        "nq_max": float(NQ_MAX),
        "splitter": "per_phase_60_40",
        "slope_abs_used": float(PHYSICS_SLOPE_ABS),
        "prod_slope_abs": float(PROD_SLOPE_ABS),
        "target_frac_min": float(TARGET_FRAC_MIN),
        "geom_win_r": float(GEOM_WIN_R),
        "geom_loss_r": float(GEOM_LOSS_R),
        "train_force_open": True,
        "eval_force_open": False,
        "floor_waived": False,
        "guard_bypassed": False,
        "world_engineering_closed": True,
        "prod_enricher_default_changed": False,
    }


def table_t1_honesty() -> dict[str, Any]:
    syn = [{"source": "synthetic_cloud_fixture"}]
    return {
        "pct_synthetic_cloud_fixture": real_data_percentage(syn),
        "pct_real_historical": real_data_percentage([{"source": "real_historical"}]),
        "pct_real": real_data_percentage([{"source": "real"}]),
        "synthetic_source_reasons": synthetic_source_reasons(syn),
        "min_real_data_pct": 95.0,
        "G6_tag": "REAL_DOOR_LOCKED",
    }


def table_t2_leg(leg: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "leg": str(leg),
        "n_policy_base": int(payload.get("n_policy_base") or 0),
        "n_policy_child": int(payload.get("n_policy_child") or 0),
        "wr_base": payload.get("wr_base"),
        "wr_child": payload.get("wr_child"),
        "mean_r_base": payload.get("mean_r_base"),
        "mean_r_child": payload.get("mean_r_child"),
        "n_H_base": int(payload.get("n_H_base") or 0),
        "n_H_child": int(payload.get("n_H_child") or 0),
        "bars_held_p50_base": payload.get("bars_held_p50_base"),
        "bars_held_p50_child": payload.get("bars_held_p50_child"),
        "delta_mean_r": payload.get("delta_mean_r"),
        "delta_n_H": payload.get("delta_n_H"),
        "HOLE_OK": bool(payload.get("HOLE_OK")),
        "MOVED": bool(payload.get("MOVED")),
        "S_THIN": bool(payload.get("S_THIN")),
        "S_HARM": bool(payload.get("S_HARM")),
        "S_MISSING": bool(payload.get("S_MISSING")),
    }


def table_t3_license(licensed: dict[str, Any]) -> dict[str, Any]:
    return {
        "tag": str(licensed.get("tag") or ""),
        "law": str(licensed.get("law") or "NONE"),
        "licensed_next_family": str(licensed.get("licensed_next_family") or "H_NONE"),
        "MOVED_A": bool(licensed.get("MOVED_A")),
        "MOVED_B": bool(licensed.get("MOVED_B")),
        "GENESIS_EYES_OK": False,
        "Proof": False,
        "REAL": "no",
        "floor_waived": False,
        "guard_bypassed": False,
        "world_engineering_closed": True,
        "honesty": HONESTY_PARAGRAPH,
    }


__all__ = ["HONESTY_PARAGRAPH", "table_t0_identity", "table_t1_honesty", "table_t2_leg", "table_t3_license"]
