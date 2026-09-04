"""G6 license for AWAKENING_STRATIFIED_SPLIT. Vs G4 a9ffa852 books. Floor 150."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_mark_eyes import LAW_NONE, LAW_SHADOW, MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_strat_split import SPLITTER_NAME, STRAT_HOLD_PCT
from lumina_core.birth.awakening_strat_tape import (
    BASELINE_SHA256,
    DELTA_MEAN_R_MIN,
    FAMILY,
    HOLE_BLOW_MAX,
    SOURCE,
    STRAT_PHASE_BLOCKS,
    STRAT_SEED,
)
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import G6_TAG

TAG_STRAT_OK = "STRAT_OK"
TAG_STRAT_BODY = "STRAT_BODY"
TAG_STRAT_WORLD_FAIL = "STRAT_WORLD_FAIL"
TAG_STRAT_THIN = "STRAT_THIN"
TAG_S_HARM = "S_HARM"
TAG_S_MISSING = "S_MISSING"
FAMILY_H_NONE = "H_NONE"
OVERALL = "AWAKENING_STRATIFIED_SPLIT SHADOW_MEASURE"


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


def empty_strat_flags() -> dict[str, Any]:
    return {
        "source": SOURCE,
        "splitter": SPLITTER_NAME,
        "phase_blocks": int(STRAT_PHASE_BLOCKS),
        "gen_up": 0,
        "gen_down": 0,
        "gen_range": 0,
        "train_gen_up": 0,
        "train_gen_down": 0,
        "hold_gen_up": 0,
        "hold_gen_down": 0,
        "train_up_frac": 0.0,
        "train_down_frac": 0.0,
        "hold_up_frac": 0.0,
        "hold_down_frac": 0.0,
        "world_ok": False,
        "fixture_seed": STRAT_SEED,
        "fixture_train_hash": "",
        "baseline_sha256": BASELINE_SHA256,
        "child_sha256": "",
        "init_policy": "scratch",
        "obs_dim": int(MARK_EYES_OBS_DIM),
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
        "chronological_tail": False,
        "real_data_pct": 0.0,
        "G6_tag": G6_TAG,
        "overall": OVERALL,
        "hold_pct": float(STRAT_HOLD_PCT),
    }


def compute_strat_leg(
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


def license_strat(
    leg_a: dict[str, Any],
    leg_b: dict[str, Any],
    *,
    missing: bool = False,
    world_ok: bool = True,
) -> dict[str, Any]:
    if not world_ok:
        return {
            "tag": TAG_STRAT_WORLD_FAIL,
            "law": LAW_NONE,
            "licensed_next_family": FAMILY_H_NONE,
            "MOVED_A": False,
            "MOVED_B": False,
            "GENESIS_EYES_OK": False,
            "evolution_proof_stamped": False,
        }
    miss = bool(missing) or bool(leg_a.get("S_MISSING")) or bool(leg_b.get("S_MISSING"))
    harm = bool(leg_a.get("S_HARM")) or bool(leg_b.get("S_HARM"))
    thin = bool(leg_a.get("S_THIN")) or bool(leg_b.get("S_THIN"))
    moved_a = bool(leg_a.get("MOVED"))
    moved_b = bool(leg_b.get("MOVED"))
    if miss:
        tag, law, family = TAG_S_MISSING, LAW_NONE, FAMILY_H_NONE
    elif harm:
        tag, law, family = TAG_S_HARM, LAW_NONE, FAMILY_H_NONE
    elif thin:
        tag, law, family = TAG_STRAT_THIN, LAW_NONE, FAMILY_H_NONE
    elif moved_a and moved_b:
        tag, law, family = TAG_STRAT_OK, LAW_SHADOW, FAMILY  # both-leg license
    else:
        tag, law, family = TAG_STRAT_BODY, LAW_NONE, FAMILY_H_NONE
    return {
        "tag": tag,
        "law": law,
        "licensed_next_family": family,
        "MOVED_A": moved_a,
        "MOVED_B": moved_b,
        "GENESIS_EYES_OK": False,  # GENESIS_EYES_OK false
        "evolution_proof_stamped": False,
    }


def compose_strat_flags(payload: dict[str, Any]) -> dict[str, Any]:
    flags = empty_strat_flags()
    flags.update(dict(payload))
    flags["GENESIS_EYES_OK"] = False
    flags["evolution_proof_stamped"] = False
    flags["REAL"] = "no"
    flags["playground"] = False
    flags["hook_default"] = False
    flags["oracle_regime"] = False
    flags["chronological_tail"] = False
    flags["G6_tag"] = G6_TAG
    flags["overall"] = OVERALL
    flags["init_policy"] = "scratch"
    flags["obs_dim"] = int(MARK_EYES_OBS_DIM)
    flags["splitter"] = SPLITTER_NAME
    flags["source"] = SOURCE
    world_ok = bool(flags.get("world_ok"))
    if not world_ok:
        flags["tag"] = TAG_STRAT_WORLD_FAIL
        flags["law"] = LAW_NONE
        flags["licensed_next_family"] = FAMILY_H_NONE
        flags["learn_called"] = False
        flags["child_sha256"] = ""
        flags["actual_timesteps"] = 0
        return flags
    if str(flags.get("tag")) == TAG_STRAT_OK and not (bool(flags.get("MOVED_A")) and bool(flags.get("MOVED_B"))):
        flags["tag"] = TAG_STRAT_BODY
        flags["law"] = LAW_NONE
        flags["licensed_next_family"] = FAMILY_H_NONE
    return flags


__all__ = [
    "FAMILY_H_NONE",
    "OVERALL",
    "TAG_STRAT_BODY",
    "TAG_STRAT_OK",
    "TAG_STRAT_THIN",
    "TAG_STRAT_WORLD_FAIL",
    "TAG_S_HARM",
    "TAG_S_MISSING",
    "compose_strat_flags",
    "compute_strat_leg",
    "empty_leg",
    "empty_strat_flags",
    "license_strat",
]
