"""G6 license for AWAKENING_PHYSICAL_DRIFT. Floor 150. Both-leg. Guard intact."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_conv_enrich import PHYSICS_SLOPE_ABS, PROD_SLOPE_ABS
from lumina_core.birth.awakening_drift_tape import BASELINE_SHA256, DRIFT_RTH, NQ_MAX, NQ_MIN, PHASE_BLOCKS
from lumina_core.birth.awakening_mark_eyes import LAW_NONE, LAW_SHADOW, MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_strat_split import SPLITTER_NAME
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import G6_TAG

SOURCE = "awakening_physical_drift"
FAMILY = "AWAKENING_MARK_EYES"
FAMILY_H_NONE = "H_NONE"
OVERALL = "AWAKENING_PHYSICAL_DRIFT SHADOW_MEASURE"
TAG_DRIFT_OK = "DRIFT_OK"
TAG_DRIFT_BODY = "DRIFT_BODY"
TAG_DRIFT_THIN = "DRIFT_THIN"
TAG_DRIFT_HARM = "DRIFT_HARM"
TAG_DRIFT_ENRICH_FAIL = "DRIFT_ENRICH_FAIL"
TAG_DRIFT_WORLD_FAIL = "DRIFT_WORLD_FAIL"
TAG_S_MISSING = "S_MISSING"
DELTA_MEAN_R_MIN = 0.05
HOLE_BLOW_MAX = 5


def empty_leg() -> dict[str, Any]:
    return {
        "n_policy_base": 0,
        "n_policy_child": 0,
        "mean_r_base": 0.0,
        "mean_r_child": 0.0,
        "n_H_base": 0,
        "n_H_child": 0,
        "wr_base": 0.0,
        "wr_child": 0.0,
        "n_W_base": 0,
        "n_W_child": 0,
        "bars_held_p50_base": 0.0,
        "bars_held_p50_child": 0.0,
        "delta_mean_r": 0.0,
        "delta_n_H": 0,
        "HOLE_OK": False,
        "MOVED": False,
        "S_THIN": False,
        "S_HARM": False,
        "S_MISSING": False,
    }


def empty_drift_flags() -> dict[str, Any]:
    return {
        "source": SOURCE,
        "drift_rth": float(DRIFT_RTH),
        "phase_blocks": int(PHASE_BLOCKS),
        "nq_min": float(NQ_MIN),
        "nq_max": float(NQ_MAX),
        "seed_used": 0,
        "attempts": [],
        "price_min": 0.0,
        "price_max": 0.0,
        "in_band": False,
        "world_ok": False,
        "slope_abs_used": float(PHYSICS_SLOPE_ABS),
        "prod_slope_abs": float(PROD_SLOPE_ABS),
        "train_force_open": False,
        "eval_force_open": False,
        "baseline_sha256": BASELINE_SHA256,
        "child_sha256": "",
        "init_policy": "scratch",
        "learn_called": False,
        "actual_timesteps": 0,
        "A": empty_leg(),
        "B": empty_leg(),
        "tag": TAG_S_MISSING,
        "GENESIS_EYES_OK": False,
        "law": LAW_NONE,
        "licensed_next_family": FAMILY_H_NONE,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "playground": False,
        "hook_default": False,
        "oracle_regime": False,
        "guard_bypassed": False,
        "floor_waived": False,
        "used_old_drift_00024": False,
        "real_data_pct": 0.0,
        "G6_tag": G6_TAG,
        "overall": OVERALL,
    }


def compute_drift_leg(
    base: dict[str, Any],
    child: dict[str, Any],
    *,
    missing: bool = False,
) -> dict[str, Any]:
    n_b = int(base.get("n_policy") or 0)
    n_c = int(child.get("n_policy") or 0)
    n_h_b = int(base.get("n_H") or 0)
    n_h_c = int(child.get("n_H") or 0)
    mean_b = float(base.get("mean_r") or 0.0)
    mean_c = float(child.get("mean_r") or 0.0)
    delta = mean_c - mean_b
    miss = bool(missing) or bool(base.get("S_MISSING")) or bool(child.get("S_MISSING"))
    s_thin = (n_b < int(POLICY_EDGE_MIN_TRADES)) or (n_c < int(POLICY_EDGE_MIN_TRADES))
    s_harm = bool(mean_c <= mean_b - float(DELTA_MEAN_R_MIN))
    hole_ok = bool(n_h_c <= n_h_b + int(HOLE_BLOW_MAX))
    moved = False
    if (not miss) and (not s_thin) and (not s_harm) and (delta >= float(DELTA_MEAN_R_MIN)) and hole_ok:
        moved = True
    return {
        "n_policy_base": n_b,
        "n_policy_child": n_c,
        "mean_r_base": mean_b,
        "mean_r_child": mean_c,
        "n_H_base": n_h_b,
        "n_H_child": n_h_c,
        "wr_base": float(base.get("wr") or 0.0),
        "wr_child": float(child.get("wr") or 0.0),
        "n_W_base": int(base.get("n_W") or 0),
        "n_W_child": int(child.get("n_W") or 0),
        "bars_held_p50_base": float(base.get("bars_held_p50") or 0.0),
        "bars_held_p50_child": float(child.get("bars_held_p50") or 0.0),
        "delta_mean_r": float(delta),
        "delta_n_H": int(n_h_b) - int(n_h_c),
        "HOLE_OK": bool(hole_ok) and not miss,
        "MOVED": bool(moved),
        "S_THIN": bool(s_thin) and not miss,
        "S_HARM": bool(s_harm) and not miss,
        "S_MISSING": bool(miss),
    }


def _child_thin(leg: dict[str, Any]) -> bool:
    return int(leg.get("n_policy_child") or 0) < int(POLICY_EDGE_MIN_TRADES)


def _base_thin(leg: dict[str, Any]) -> bool:
    return int(leg.get("n_policy_base") or 0) < int(POLICY_EDGE_MIN_TRADES)


def license_drift(
    leg_a: dict[str, Any],
    leg_b: dict[str, Any],
    *,
    missing: bool = False,
    world_fail: bool = False,
    enrich_fail: bool = False,
) -> dict[str, Any]:
    miss = bool(missing) or bool(leg_a.get("S_MISSING")) or bool(leg_b.get("S_MISSING"))
    harm = bool(leg_a.get("S_HARM")) or bool(leg_b.get("S_HARM"))
    child_thin = _child_thin(leg_a) or _child_thin(leg_b)
    child_thick = (not _child_thin(leg_a)) and (not _child_thin(leg_b))
    base_thin = _base_thin(leg_a) or _base_thin(leg_b)
    moved_a = bool(leg_a.get("MOVED"))
    moved_b = bool(leg_b.get("MOVED"))
    if world_fail:
        tag, law, family = TAG_DRIFT_WORLD_FAIL, LAW_NONE, FAMILY_H_NONE
    elif enrich_fail:
        tag, law, family = TAG_DRIFT_ENRICH_FAIL, LAW_NONE, FAMILY_H_NONE
    elif miss:
        tag, law, family = TAG_S_MISSING, LAW_NONE, FAMILY_H_NONE
    elif harm:
        tag, law, family = TAG_DRIFT_HARM, LAW_NONE, FAMILY_H_NONE
    elif child_thin:
        tag, law, family = TAG_DRIFT_THIN, LAW_NONE, FAMILY_H_NONE
    elif base_thin and child_thick and not (moved_a and moved_b):
        tag, law, family = TAG_DRIFT_BODY, LAW_NONE, FAMILY_H_NONE
    elif moved_a and moved_b:
        tag, law, family = TAG_DRIFT_OK, LAW_SHADOW, FAMILY  # both-leg license
    else:
        tag, law, family = TAG_DRIFT_BODY, LAW_NONE, FAMILY_H_NONE
    return {
        "tag": tag,
        "law": law,
        "licensed_next_family": family,
        "MOVED_A": moved_a,
        "MOVED_B": moved_b,
        "GENESIS_EYES_OK": False,  # GENESIS_EYES_OK false
        "evolution_proof_stamped": False,
        "floor_waived": False,
        "guard_bypassed": False,
    }


def compose_drift_flags(payload: dict[str, Any]) -> dict[str, Any]:
    flags = empty_drift_flags()
    flags.update(dict(payload))
    flags["GENESIS_EYES_OK"] = False
    flags["evolution_proof_stamped"] = False
    flags["REAL"] = "no"
    flags["playground"] = False
    flags["hook_default"] = False
    flags["oracle_regime"] = False
    flags["floor_waived"] = False
    flags["guard_bypassed"] = False
    flags["eval_force_open"] = False
    flags["used_old_drift_00024"] = False
    flags["G6_tag"] = G6_TAG
    flags["overall"] = OVERALL
    flags["init_policy"] = "scratch"
    flags["obs_dim"] = int(MARK_EYES_OBS_DIM)
    flags["splitter"] = SPLITTER_NAME
    flags["source"] = SOURCE
    flags["drift_rth"] = float(DRIFT_RTH)
    flags["phase_blocks"] = int(PHASE_BLOCKS)
    flags["nq_min"] = float(NQ_MIN)
    flags["nq_max"] = float(NQ_MAX)
    flags["slope_abs_used"] = float(PHYSICS_SLOPE_ABS)
    flags["prod_slope_abs"] = float(PROD_SLOPE_ABS)
    if str(flags.get("tag")) == TAG_DRIFT_OK and not (bool(flags.get("MOVED_A")) and bool(flags.get("MOVED_B"))):
        flags["tag"] = TAG_DRIFT_BODY
        flags["law"] = LAW_NONE
        flags["licensed_next_family"] = FAMILY_H_NONE
    return flags


__all__ = [
    "DELTA_MEAN_R_MIN",
    "FAMILY",
    "FAMILY_H_NONE",
    "HOLE_BLOW_MAX",
    "OVERALL",
    "SOURCE",
    "TAG_DRIFT_BODY",
    "TAG_DRIFT_ENRICH_FAIL",
    "TAG_DRIFT_HARM",
    "TAG_DRIFT_OK",
    "TAG_DRIFT_THIN",
    "TAG_DRIFT_WORLD_FAIL",
    "TAG_S_MISSING",
    "compose_drift_flags",
    "compute_drift_leg",
    "empty_drift_flags",
    "empty_leg",
    "license_drift",
]
