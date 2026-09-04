"""G5 license for AWAKENING_OBJECTIVE_TRADE. Floor 150. FORCE_OPEN train-only."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_conv_enrich import PHYSICS_SLOPE_ABS, PROD_SLOPE_ABS
from lumina_core.birth.awakening_mark_eyes import LAW_NONE, LAW_SHADOW, MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_obj_tape import BASELINE_SHA256, OBJ_SEED
from lumina_core.birth.awakening_strat_split import SPLITTER_NAME
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import G6_TAG

SOURCE = "awakening_objective_trade"
FAMILY = "AWAKENING_MARK_EYES"
FAMILY_H_NONE = "H_NONE"
OVERALL = "AWAKENING_OBJECTIVE_TRADE SHADOW_MEASURE"
TAG_OBJ_OK = "OBJ_OK"
TAG_OBJ_BODY = "OBJ_BODY"
TAG_OBJ_THIN = "OBJ_THIN"
TAG_OBJ_HARM = "OBJ_HARM"
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


def empty_obj_flags() -> dict[str, Any]:
    return {
        "source": SOURCE,
        "train_force_open": False,
        "eval_force_open": False,
        "slope_abs_used": float(PHYSICS_SLOPE_ABS),
        "prod_slope_abs": float(PROD_SLOPE_ABS),
        "world_ok": False,
        "fixture_seed": int(OBJ_SEED),
        "fixture_train_hash": "",
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
        "floor_waived": False,
        "real_data_pct": 0.0,
        "G6_tag": G6_TAG,
        "overall": OVERALL,
    }


def compute_obj_leg(
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


def license_obj(
    leg_a: dict[str, Any],
    leg_b: dict[str, Any],
    *,
    missing: bool = False,
) -> dict[str, Any]:
    miss = bool(missing) or bool(leg_a.get("S_MISSING")) or bool(leg_b.get("S_MISSING"))
    harm = bool(leg_a.get("S_HARM")) or bool(leg_b.get("S_HARM"))
    child_thin = _child_thin(leg_a) or _child_thin(leg_b)
    child_thick = (not _child_thin(leg_a)) and (not _child_thin(leg_b))
    base_thin = _base_thin(leg_a) or _base_thin(leg_b)
    moved_a = bool(leg_a.get("MOVED"))
    moved_b = bool(leg_b.get("MOVED"))
    if miss:
        tag, law, family = TAG_S_MISSING, LAW_NONE, FAMILY_H_NONE
    elif harm:
        tag, law, family = TAG_OBJ_HARM, LAW_NONE, FAMILY_H_NONE
    elif child_thin:
        tag, law, family = TAG_OBJ_THIN, LAW_NONE, FAMILY_H_NONE
    elif base_thin and child_thick and not (moved_a and moved_b):
        tag, law, family = TAG_OBJ_BODY, LAW_NONE, FAMILY_H_NONE
    elif moved_a and moved_b:
        tag, law, family = TAG_OBJ_OK, LAW_SHADOW, FAMILY  # both-leg license
    else:
        tag, law, family = TAG_OBJ_BODY, LAW_NONE, FAMILY_H_NONE
    return {
        "tag": tag,
        "law": law,
        "licensed_next_family": family,
        "MOVED_A": moved_a,
        "MOVED_B": moved_b,
        "GENESIS_EYES_OK": False,  # GENESIS_EYES_OK false
        "evolution_proof_stamped": False,
        "floor_waived": False,
    }


def compose_obj_flags(payload: dict[str, Any]) -> dict[str, Any]:
    flags = empty_obj_flags()
    flags.update(dict(payload))
    flags["GENESIS_EYES_OK"] = False
    flags["evolution_proof_stamped"] = False
    flags["REAL"] = "no"
    flags["playground"] = False
    flags["hook_default"] = False
    flags["oracle_regime"] = False
    flags["floor_waived"] = False
    flags["eval_force_open"] = False
    flags["G6_tag"] = G6_TAG
    flags["overall"] = OVERALL
    flags["init_policy"] = "scratch"
    flags["obs_dim"] = int(MARK_EYES_OBS_DIM)
    flags["splitter"] = SPLITTER_NAME
    flags["source"] = SOURCE
    flags["slope_abs_used"] = float(PHYSICS_SLOPE_ABS)
    flags["prod_slope_abs"] = float(PROD_SLOPE_ABS)
    if str(flags.get("tag")) == TAG_OBJ_OK and not (bool(flags.get("MOVED_A")) and bool(flags.get("MOVED_B"))):
        flags["tag"] = TAG_OBJ_BODY
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
    "TAG_OBJ_BODY",
    "TAG_OBJ_HARM",
    "TAG_OBJ_OK",
    "TAG_OBJ_THIN",
    "TAG_S_MISSING",
    "compose_obj_flags",
    "compute_obj_leg",
    "empty_leg",
    "empty_obj_flags",
    "license_obj",
]
