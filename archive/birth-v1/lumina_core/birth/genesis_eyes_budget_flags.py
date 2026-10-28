"""G3 license for GENESIS_EYES_BUDGET. #27 algebra. Floor 150. GENESIS_EYES_OK stays false."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.awakening_mark_eyes import FAMILY, LAW_NONE, LAW_SHADOW
from lumina_core.birth.awakening_mark_eyes_flags import flag_s_harm_eyes
from lumina_core.birth.awakening_path_exit_k3_flags import flag_hole_moved
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import G6_TAG
from lumina_core.birth.genesis_eyes_budget import (
    BUDGET_FIXTURE_SEED,
    STUDENT_BIRTH_SHA256,
    STUDENT_EYES_SHA256,
)

TAG_BUDGET_OK = "BUDGET_OK"
TAG_BUDGET_THIN = "BUDGET_THIN"
TAG_BUDGET_FAIL = "BUDGET_FAIL"
TAG_S_HARM = "S_HARM"
TAG_S_MISSING = "S_MISSING"
FAMILY_H_NONE = "H_NONE"
OVERALL = "GENESIS_EYES_BUDGET SHADOW_MEASURE"


def empty_leg() -> dict[str, Any]:
    return {
        "n_policy_birth": 0,
        "n_policy_child": 0,
        "n_H_birth": 0,
        "n_H_child": 0,
        "n_W_birth": 0,
        "n_W_child": 0,
        "wr_birth": 0.0,
        "wr_child": 0.0,
        "mean_r_birth": 0.0,
        "mean_r_child": 0.0,
        "bars_held_p50_birth": 0.0,
        "bars_held_p50_child": 0.0,
        "HOLE_MOVED": False,
        "S_THIN": False,
        "S_HARM": False,
        "S_MISSING": False,
    }


def empty_budget_flags() -> dict[str, Any]:
    return {
        "source": "genesis_eyes_budget",
        "fixture_seed": BUDGET_FIXTURE_SEED,
        "fixture_train_hash": "",
        "holdout_tick_count": 0,
        "ticks_per_leg": [0, 0],
        "student_birth_sha256": STUDENT_BIRTH_SHA256,
        "student_eyes_sha256": STUDENT_EYES_SHA256,
        "learn_called": False,
        "optimizer_steps": 0,
        "A": empty_leg(),
        "B": empty_leg(),
        "tag": TAG_S_MISSING,
        "HOLE_MOVED_A": False,
        "HOLE_MOVED_B": False,
        "GENESIS_EYES_OK": False,
        "law": LAW_NONE,
        "licensed_next_family": FAMILY_H_NONE,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "playground": False,
        "hook_default": False,
        "used_old_path_early": False,
        "used_g5_halves_as_exam": False,
        "real_data_pct": 0.0,
        "G6_tag": G6_TAG,
        "overall": OVERALL,
    }


def compute_budget_leg(
    birth: dict[str, Any],
    child: dict[str, Any],
    *,
    missing: bool = False,
) -> dict[str, Any]:
    n_b = int(birth.get("n_policy") or 0)
    n_c = int(child.get("n_policy") or 0)
    n_h_b = int(birth.get("n_H") or 0)
    n_h_c = int(child.get("n_H") or 0)
    mean_b = float(birth.get("mean_r") or 0.0)
    mean_c = float(child.get("mean_r") or 0.0)
    miss = bool(missing) or bool(birth.get("S_MISSING")) or bool(child.get("S_MISSING"))
    s_thin = (n_b < int(POLICY_EDGE_MIN_TRADES)) or (n_c < int(POLICY_EDGE_MIN_TRADES))
    s_harm = flag_s_harm_eyes(
        n_h_child=n_h_c, n_h_base=n_h_b, mean_r_child=mean_c, mean_r_base=mean_b
    )
    moved = False
    if (not miss) and (not s_thin) and (not s_harm):
        moved = bool(
            flag_hole_moved(
                s_missing_hook=False,
                s_harm=False,
                n_h_shadow=n_h_c,
                n_h_base=n_h_b,
                mean_r_policy_shadow=mean_c,
                mean_r_policy_base=mean_b,
            )
        )
    return {
        "n_policy_birth": n_b,
        "n_policy_child": n_c,
        "n_H_birth": n_h_b,
        "n_H_child": n_h_c,
        "n_W_birth": int(birth.get("n_W") or 0),
        "n_W_child": int(child.get("n_W") or 0),
        "wr_birth": float(birth.get("wr") or 0.0),
        "wr_child": float(child.get("wr") or 0.0),
        "mean_r_birth": mean_b,
        "mean_r_child": mean_c,
        "bars_held_p50_birth": float(birth.get("bars_held_p50") or 0.0),
        "bars_held_p50_child": float(child.get("bars_held_p50") or 0.0),
        "HOLE_MOVED": bool(moved),
        "S_THIN": bool(s_thin) and not miss,
        "S_HARM": bool(s_harm) and not miss,
        "S_MISSING": bool(miss),
    }


def license_budget(
    leg_a: dict[str, Any],
    leg_b: dict[str, Any],
    *,
    missing: bool = False,
) -> dict[str, Any]:
    miss = bool(missing) or bool(leg_a.get("S_MISSING")) or bool(leg_b.get("S_MISSING"))
    harm = bool(leg_a.get("S_HARM")) or bool(leg_b.get("S_HARM"))
    thin = bool(leg_a.get("S_THIN")) or bool(leg_b.get("S_THIN"))
    moved_a = bool(leg_a.get("HOLE_MOVED"))
    moved_b = bool(leg_b.get("HOLE_MOVED"))
    if miss:
        tag, law, family = TAG_S_MISSING, LAW_NONE, FAMILY_H_NONE
    elif harm:
        tag, law, family = TAG_S_HARM, LAW_NONE, FAMILY_H_NONE
    elif thin:
        tag, law, family = TAG_BUDGET_THIN, LAW_NONE, FAMILY_H_NONE  # license refuses BUDGET_OK when a leg is thin
    elif moved_a and moved_b:
        tag, law, family = TAG_BUDGET_OK, LAW_SHADOW, FAMILY
    else:
        tag, law, family = TAG_BUDGET_FAIL, LAW_NONE, FAMILY_H_NONE
    return {
        "tag": tag,
        "law": law,
        "licensed_next_family": family,
        "HOLE_MOVED_A": moved_a,
        "HOLE_MOVED_B": moved_b,
        "GENESIS_EYES_OK": False,
        "evolution_proof_stamped": False,
    }


def compose_budget_flags(payload: dict[str, Any]) -> dict[str, Any]:
    flags = empty_budget_flags()
    flags.update(dict(payload))
    flags["GENESIS_EYES_OK"] = False  # GENESIS_EYES_OK forced false
    flags["learn_called"] = False
    flags["optimizer_steps"] = 0
    flags["evolution_proof_stamped"] = False
    flags["REAL"] = "no"
    flags["playground"] = False
    flags["hook_default"] = False
    flags["used_old_path_early"] = False
    flags["used_g5_halves_as_exam"] = False
    flags["G6_tag"] = G6_TAG
    flags["overall"] = OVERALL
    if str(flags.get("tag")) == TAG_BUDGET_OK and not (
        bool(flags.get("HOLE_MOVED_A")) and bool(flags.get("HOLE_MOVED_B"))
    ):
        flags["tag"] = TAG_BUDGET_FAIL
        flags["law"] = LAW_NONE
        flags["licensed_next_family"] = FAMILY_H_NONE
    return flags


__all__ = [
    "FAMILY_H_NONE",
    "OVERALL",
    "TAG_BUDGET_FAIL",
    "TAG_BUDGET_OK",
    "TAG_BUDGET_THIN",
    "TAG_S_HARM",
    "TAG_S_MISSING",
    "compose_budget_flags",
    "compute_budget_leg",
    "empty_budget_flags",
    "empty_leg",
    "license_budget",
]
